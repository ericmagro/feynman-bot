import asyncio
import discord
from discord.ext import commands, tasks
import anthropic
import os
import sys
import json
import logging
from datetime import datetime, time, timezone
from pathlib import Path
import random

# =============================================================================
# CONFIGURATION
# =============================================================================

VERSION = "1.1.0"

# Validate required environment variables
def get_required_env(key: str) -> str:
    """Get required environment variable or exit with helpful error."""
    value = os.environ.get(key)
    if not value:
        print(f"ERROR: Missing required environment variable: {key}")
        print(f"Please set {key} in your environment or .env file")
        sys.exit(1)
    return value

DISCORD_TOKEN = get_required_env("DISCORD_TOKEN")
ANTHROPIC_API_KEY = get_required_env("ANTHROPIC_API_KEY")
CHANNEL_ID = int(get_required_env("FACT_CHANNEL_ID"))
HISTORY_FILE = Path(os.environ.get("HISTORY_FILE", "fact_history.json"))

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("feynman")

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Claude client
claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# =============================================================================
# CONTENT CONFIGURATION
# =============================================================================

# Types of wonder (per Martin Gardner)
WONDER_TYPES = [
    "something that seems impossible but is mathematically proven true",
    "a simple question with a surprisingly complex or unsolved answer",
    "a pattern that appears unexpectedly across unrelated domains",
    "a problem that stumped mathematicians or physicists for decades (or centuries)",
    "something proven to exist but never directly observed",
    "two seemingly unrelated things that turn out to be mathematically equivalent",
    "a result that contradicts everyday intuition about how the world works",
    "a physical phenomenon that has no complete explanation yet",
    "an everyday object or experience that hides deep mathematical structure",
    "a limit or bound that nature seems to respect for mysterious reasons",
]

# Topics to explore
TOPICS = [
    "quantum mechanics", "number theory", "thermodynamics", "topology",
    "special or general relativity", "probability paradoxes", "chaos theory",
    "electromagnetism", "group theory and symmetry", "fluid dynamics",
    "prime numbers", "cosmology and the early universe", "game theory",
    "optics and light", "combinatorics", "statistical mechanics",
    "black holes", "wave phenomena", "graph theory", "orbital mechanics",
]

# Weekly digest posts on Friday (weekday 4)
POSTING_DAY = 4  # Friday

# Maximum posts to keep in history (prevents unbounded growth)
MAX_HISTORY_POSTS = 500

# Model configuration: source of truth is models.json (committed to repo).
# Env vars still win if set, useful for local experimentation without
# editing the committed file. To upgrade models in prod, edit models.json
# and push — Railway auto-deploys.
_MODELS_FILE = Path(__file__).parent / "models.json"
with open(_MODELS_FILE) as _f:
    _models = json.load(_f)
GENERATION_MODEL = os.environ.get("GENERATION_MODEL", _models["generation_model"])
SUMMARY_MODEL = os.environ.get("SUMMARY_MODEL", _models["summary_model"])

# Content variety settings
RECENT_WONDERS_MEMORY = 5   # Avoid repeating wonder types within ~2 weeks
RECENT_TOPICS_MEMORY = 8    # Avoid repeating topics within ~4 weeks
CALLBACK_PROBABILITY = 0.3  # ~30% chance to reference old post

# =============================================================================
# HISTORY MANAGEMENT
# =============================================================================

# Serializes read-modify-write sequences against the history file.
# Multiple writers (weekly task, !puzzle's temp_answer) can otherwise clobber
# each other since each loads, mutates, and saves a separate dict copy.
HISTORY_LOCK = asyncio.Lock()


def load_history() -> dict:
    """Load posting history from JSON file."""
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Corrupted history file, starting fresh")
            return _empty_history()
    return _empty_history()


def _empty_history() -> dict:
    """Return empty history structure."""
    return {
        "posts": [],
        "used_wonders": [],
        "used_topics": [],
    }


def save_history(history: dict) -> None:
    """Save posting history to JSON file atomically."""
    # Write to temp file first, then rename (atomic on POSIX)
    temp_file = HISTORY_FILE.with_suffix(".tmp")
    with open(temp_file, "w") as f:
        json.dump(history, f, indent=2, default=str)
    temp_file.rename(HISTORY_FILE)


def add_to_history(history: dict, post_data: dict) -> None:
    """Add a new post to history."""
    history["posts"].append(post_data)

    # Prune old posts if over limit
    if len(history["posts"]) > MAX_HISTORY_POSTS:
        history["posts"] = history["posts"][-MAX_HISTORY_POSTS:]

    # Track what we've used recently
    if post_data.get("wonder_type"):
        history["used_wonders"].append(post_data["wonder_type"])
        history["used_wonders"] = history["used_wonders"][-RECENT_WONDERS_MEMORY:]

    if post_data.get("topic"):
        history["used_topics"].append(post_data["topic"])
        history["used_topics"] = history["used_topics"][-RECENT_TOPICS_MEMORY:]

    save_history(history)


def get_callback_candidate(history: dict) -> dict | None:
    """Find a good post from 1-2 weeks ago to callback to."""
    if len(history["posts"]) < 7:
        return None

    now = datetime.now(timezone.utc)
    candidates = []

    for post in history["posts"]:
        try:
            post_date = datetime.fromisoformat(post["date"]).replace(tzinfo=timezone.utc)
            days_ago = (now - post_date).days

            if 7 <= days_ago <= 21 and post.get("mode") == "fact":
                candidates.append(post)
        except (KeyError, ValueError):
            continue

    return random.choice(candidates) if candidates else None


def get_recent_posts(history: dict, days: int = 7) -> list:
    """Get posts from the last N days."""
    if not history["posts"]:
        return []

    now = datetime.now(timezone.utc)
    recent = []

    for post in history["posts"]:
        try:
            post_date = datetime.fromisoformat(post["date"]).replace(tzinfo=timezone.utc)
            if (now - post_date).days <= days:
                recent.append(post)
        except (KeyError, ValueError):
            continue

    return recent


def pick_fresh(options: list, recently_used: list) -> str:
    """Pick an option we haven't used recently, or random if all used."""
    fresh = [o for o in options if o not in recently_used]
    return random.choice(fresh) if fresh else random.choice(options)


# =============================================================================
# CONTENT GENERATION
# =============================================================================

async def call_claude(model: str, max_tokens: int, prompt: str) -> str:
    """Call Claude API with error handling.

    Uses asyncio.to_thread() because the Anthropic SDK is synchronous.
    Without this, API calls would block the Discord event loop, freezing
    the bot during content generation (can't respond to commands, etc.).
    """
    try:
        def _call():
            return claude.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )

        message = await asyncio.to_thread(_call)
        return message.content[0].text
    except anthropic.APIConnectionError:
        logger.error("Failed to connect to Anthropic API")
        raise
    except anthropic.RateLimitError:
        logger.error("Anthropic API rate limit exceeded")
        raise
    except anthropic.APIStatusError as e:
        logger.error(f"Anthropic API error: {e.status_code} - {e.message}")
        raise


async def generate_summary(content: str) -> str:
    """Generate a concise summary of a post using Haiku."""
    prompt = f"Summarize this in 1 sentence (under 100 words), focusing on the core concept or question:\n\n{content}"
    response = await call_claude(SUMMARY_MODEL, 100, prompt)
    return response.strip()


def build_context_block(history: dict) -> str:
    """Build context from history to send to Claude."""
    recent = get_recent_posts(history, days=14)

    if not recent:
        return ""

    lines = ["<recent_posts>"]
    for post in recent[-10:]:
        date = post.get("date", "")[:10]
        mode = post.get("mode", "fact")
        topic = post.get("topic", "unknown")
        summary = post.get("summary", "")[:200]
        lines.append(f"[{date}] ({mode}) {topic}: {summary}")
    lines.append("</recent_posts>")

    return "\n".join(lines)


async def generate_fact(history: dict) -> dict:
    """Generate a surprising fact."""
    topic = pick_fresh(TOPICS, history.get("used_topics", []))
    wonder = pick_fresh(WONDER_TYPES, history.get("used_wonders", []))
    context = build_context_block(history)

    # Check for callback opportunity (~30% chance if available)
    callback = None
    callback_text = ""
    if random.random() < CALLBACK_PROBABILITY:
        callback = get_callback_candidate(history)
        if callback:
            try:
                post_date = datetime.fromisoformat(callback["date"]).replace(tzinfo=timezone.utc)
                days_ago = (datetime.now(timezone.utc) - post_date).days
                callback_text = f"""
CALLBACK OPPORTUNITY: About {days_ago} days ago,
you shared this: "{callback.get('summary', '')}"
Consider briefly connecting today's fact to this earlier one if there's a natural link.
If no natural link, ignore this and just share a fresh fact."""
            except (KeyError, ValueError):
                callback = None

    prompt = f"""{context}

TASK: Share a genuinely surprising fact about {topic}.
TYPE OF WONDER: {wonder}
{callback_text}

Requirements:
- Lead with the surprise—the thing that breaks intuition, that seems wrong but isn't
- Include a vivid, unexpected analogy ("It's like..." or "Imagine...")
- Connect it to something people encounter in daily life when possible
- Use concrete scale comparisons for large/small numbers (not "billions of miles" but "light takes X minutes")
- End with a question, mini-challenge, or "next time you see X, notice..."
- 3-5 sentences total
- Do NOT repeat or closely echo anything from <recent_posts>
- No preamble—start directly with the surprising content
- Close with one relevant emoji"""

    content = await call_claude(GENERATION_MODEL, 1024, prompt)
    summary = await generate_summary(content)

    return {
        "content": content,
        "mode": "fact",
        "topic": topic,
        "wonder_type": wonder,
        "summary": summary,
        "had_callback": callback is not None,
    }


async def generate_what_if(history: dict) -> dict:
    """Generate an absurd hypothetical answered with real physics/math."""
    topic = pick_fresh(TOPICS, history.get("used_topics", []))
    context = build_context_block(history)

    prompt = f"""{context}

TASK: Ask an absurd hypothetical question and answer it with real physics or math.

Think like Randall Munroe's "What If?" — silly premise, rigorous analysis.

Examples of good premises:
- "What if you stirred your coffee at the speed of sound?"
- "What if Earth's gravity doubled for just one second?"
- "What if you could walk on the surface of the sun wearing a perfect reflective suit?"
- "What if every human jumped at the same time?"
- "What if you tried to build a bridge to the moon?"

Related topic to draw from (but get creative): {topic}

Requirements:
- Pose the absurd question, then walk through what would actually happen
- Use specific numbers and consequences—be concrete
- The physics/math should be real even though the premise is silly
- Maintain a playful but genuinely curious tone
- 4-6 sentences total
- Do NOT repeat premises from <recent_posts>
- No preamble—start with the hypothetical question directly
- Close with one relevant emoji"""

    content = await call_claude(GENERATION_MODEL, 1024, prompt)
    summary = await generate_summary(content)

    return {
        "content": content,
        "mode": "what_if",
        "topic": topic,
        "summary": summary,
    }


async def generate_puzzle(history: dict) -> dict:
    """Generate an intriguing puzzle."""
    topic = pick_fresh(TOPICS, history.get("used_topics", []))
    context = build_context_block(history)

    prompt = f"""{context}

TASK: Pose an intriguing puzzle or paradox from {topic}.

Requirements:
- The puzzle should be accessible but not trivial
- It should have a real, satisfying answer (you'll provide it separately)
- Classic brain-teasers and famous paradoxes are fine if not recently used
- State the puzzle clearly
- Do NOT give the answer—end with "Think about it..." or similar
- 2-4 sentences for the puzzle
- Do NOT repeat puzzles from <recent_posts>
- No preamble—start with the puzzle directly
- Close with 🤔

After the puzzle, provide the answer in a SEPARATE section marked ANSWER: that will be posted tomorrow."""

    full_response = await call_claude(GENERATION_MODEL, 1024, prompt)

    # Parse out puzzle and answer
    if "ANSWER:" in full_response:
        parts = full_response.split("ANSWER:", 1)
        puzzle = parts[0].strip()
        answer = parts[1].strip()
    else:
        puzzle = full_response
        answer = "(Answer not available)"

    summary = await generate_summary(puzzle)

    return {
        "content": puzzle,
        "mode": "puzzle",
        "topic": topic,
        "summary": summary,
        "answer": answer,
    }


async def generate_weekly_digest(history: dict) -> tuple[dict, dict]:
    """Generate a fact and what-if for the weekly digest."""
    fact_result, whatif_result = await asyncio.gather(
        generate_fact(history),
        generate_what_if(history)
    )
    return fact_result, whatif_result


def truncate_for_embed(text: str, max_length: int = 1024) -> str:
    """Truncate text to fit Discord embed field limits."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


# =============================================================================
# DISCORD BOT
# =============================================================================

@bot.event
async def on_ready():
    """Called when bot is connected and ready."""
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    logger.info(f"Version {VERSION}")

    # Set bot presence
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="for !help"
        )
    )

    if not weekly_post.is_running():
        weekly_post.start()
        logger.info("Weekly post task started")


@bot.event
async def on_command_error(ctx, error):
    """Global error handler for commands."""
    if isinstance(error, commands.CommandNotFound):
        return  # Ignore unknown commands
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"Please wait {error.retry_after:.0f}s before using this command again.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")
    else:
        logger.error(f"Command error: {error}")
        await ctx.send("Something went wrong. Please try again later.")


@tasks.loop(time=time(hour=19, minute=0, tzinfo=timezone.utc))
async def weekly_post():
    """Post weekly digest to the designated channel (Fridays only)."""
    # Only post on Friday
    if datetime.now(timezone.utc).weekday() != POSTING_DAY:
        return

    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        logger.error(f"Could not find channel {CHANNEL_ID}")
        return

    try:
        logger.info("Generating weekly digest...")
        history = load_history()

        # Generate both items
        fact, whatif = await generate_weekly_digest(history)

        # Build the embed with both items
        embed = discord.Embed(
            title="Friday Wonder",
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(
            name=f"Fact: {fact.get('topic', 'Physics & Math').title()}",
            value=truncate_for_embed(fact["content"]),
            inline=False
        )
        embed.add_field(
            name="What If...?",
            value=truncate_for_embed(whatif["content"]),
            inline=False
        )
        embed.set_footer(text="Powered by Claude")

        await channel.send(embed=embed)
        logger.info(f"Posted weekly digest: fact about {fact.get('topic')}, what-if about {whatif.get('topic')}")

        # Save both to history (re-load under lock to avoid clobbering
        # concurrent writers like !puzzle's temp_answer).
        now = datetime.now(timezone.utc).isoformat()
        fact["date"] = now
        whatif["date"] = now
        async with HISTORY_LOCK:
            history = load_history()
            add_to_history(history, fact)
            add_to_history(history, whatif)

    except anthropic.APIError as e:
        logger.error(f"API error during weekly post: {e}")
    except Exception as e:
        logger.error(f"Error posting weekly digest: {e}", exc_info=True)


@weekly_post.before_loop
async def before_weekly_post():
    """Wait for bot to be ready before starting task."""
    await bot.wait_until_ready()


# =============================================================================
# COMMANDS
# =============================================================================

@bot.command(name="help")
async def help_command(ctx):
    """Show available commands."""
    embed = discord.Embed(
        title="Feynman Bot Commands",
        description="Weekly physics & math wonder, plus on-demand content",
        color=0x5865F2
    )
    embed.add_field(
        name="Content Commands",
        value=(
            "`!fact [topic]` — Get a surprising fact\n"
            "`!whatif` — Absurd hypothetical with real physics\n"
            "`!puzzle` — Get a brain-teaser\n"
            "`!answer` — Reveal last puzzle's answer"
        ),
        inline=False
    )
    embed.add_field(
        name="Info Commands",
        value=(
            "`!schedule` — Show posting schedule\n"
            "`!history [n]` — Show last n posts\n"
            "`!help` — This message"
        ),
        inline=False
    )
    embed.set_footer(text=f"v{VERSION} • Posts every Friday at 7pm UTC")
    await ctx.send(embed=embed)


@bot.command(name="fact")
@commands.cooldown(1, 30, commands.BucketType.user)
async def get_fact(ctx, *, topic: str = None):
    """Get a fact on demand. Optionally specify a topic."""
    async with ctx.typing():
        try:
            history = load_history()

            if topic:
                # Sanitize topic (basic length limit)
                topic = topic[:100]
                prompt = f"""Share a genuinely surprising fact about {topic}.

Requirements:
- Lead with the surprise—the thing that breaks intuition
- Include a vivid analogy
- Connect to everyday experience if possible
- End with a question or "notice this next time..."
- 3-5 sentences
- No preamble
- Close with one emoji"""

                content = await call_claude(GENERATION_MODEL, 1024, prompt)
                used_topic = topic
            else:
                result = await generate_fact(history)
                content = result["content"]
                used_topic = result.get("topic", "Physics & Math")

            embed = discord.Embed(
                title=f"Fact: {used_topic.title()}",
                description=truncate_for_embed(content),
                color=0x5865F2,
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_footer(text=f"Requested by {ctx.author.display_name}")

            await ctx.send(embed=embed)

        except anthropic.APIError:
            await ctx.send("Sorry, I couldn't generate a fact right now. Please try again later.")


@bot.command(name="whatif")
@commands.cooldown(1, 30, commands.BucketType.user)
async def get_what_if(ctx):
    """Get an absurd hypothetical answered with real physics."""
    async with ctx.typing():
        try:
            history = load_history()
            result = await generate_what_if(history)

            embed = discord.Embed(
                title="What If...?",
                description=truncate_for_embed(result["content"]),
                color=0xEB459E,
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_footer(text=f"Requested by {ctx.author.display_name}")

            await ctx.send(embed=embed)

        except anthropic.APIError:
            await ctx.send("Sorry, I couldn't generate a what-if right now. Please try again later.")


@bot.command(name="puzzle")
@commands.cooldown(1, 30, commands.BucketType.user)
async def get_puzzle(ctx):
    """Get a puzzle."""
    async with ctx.typing():
        try:
            history = load_history()
            result = await generate_puzzle(history)

            embed = discord.Embed(
                title=f"Puzzle: {result.get('topic', 'Math & Physics').title()}",
                description=truncate_for_embed(result["content"]),
                color=0xFEE75C,
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_footer(text=f"Requested by {ctx.author.display_name} • Use !answer for solution")

            # Store answer temporarily (re-load under lock so we don't
            # clobber a concurrent weekly-post write).
            async with HISTORY_LOCK:
                history = load_history()
                history["temp_answer"] = result.get("answer", "No answer available")
                save_history(history)

            await ctx.send(embed=embed)

        except anthropic.APIError:
            await ctx.send("Sorry, I couldn't generate a puzzle right now. Please try again later.")


@bot.command(name="answer")
async def get_answer(ctx):
    """Get the answer to the last !puzzle."""
    history = load_history()
    answer = history.get("temp_answer", "No recent puzzle to answer! Use `!puzzle` first.")

    embed = discord.Embed(
        title="Puzzle Answer",
        description=truncate_for_embed(answer),
        color=0x57F287
    )
    await ctx.send(embed=embed)


@bot.command(name="history")
async def show_history(ctx, count: int = 5):
    """Show recent posts. Usage: !history [count]"""
    # Limit count to reasonable range
    count = max(1, min(count, 20))

    history = load_history()
    recent = history.get("posts", [])[-count:]

    if not recent:
        await ctx.send("No posting history yet!")
        return

    lines = []
    for post in reversed(recent):
        date = post.get("date", "")[:10]
        mode = post.get("mode", "fact")
        topic = post.get("topic", "unknown")
        lines.append(f"`{date}` **{mode}**: {topic}")

    embed = discord.Embed(
        title=f"Last {len(recent)} Posts",
        description="\n".join(lines),
        color=0x5865F2
    )
    await ctx.send(embed=embed)


@bot.command(name="schedule")
async def show_schedule(ctx):
    """Show the weekly posting schedule."""
    embed = discord.Embed(
        title="Weekly Schedule",
        description="**Friday** at 7pm UTC: Weekly digest (1 fact + 1 what-if)",
        color=0x5865F2
    )
    embed.add_field(
        name="On-Demand Commands",
        value="`!fact [topic]` — Get a fact\n`!whatif` — Absurd hypothetical\n`!puzzle` / `!answer` — Puzzle mode\n`!history [n]` — Recent posts",
        inline=False
    )
    await ctx.send(embed=embed)


@bot.command(name="status")
async def show_status(ctx):
    """Show bot status (for monitoring)."""
    history = load_history()
    post_count = len(history.get("posts", []))

    embed = discord.Embed(
        title="Bot Status",
        color=0x57F287
    )
    embed.add_field(name="Version", value=VERSION, inline=True)
    embed.add_field(name="Posts in History", value=str(post_count), inline=True)
    embed.add_field(name="Next Post", value="Friday 7pm UTC", inline=True)
    await ctx.send(embed=embed)


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    logger.info(f"Starting Feynman Bot v{VERSION}")
    bot.run(DISCORD_TOKEN)
