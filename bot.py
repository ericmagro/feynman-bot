import asyncio
import discord
from discord.ext import commands, tasks
import anthropic
import os
import json
from datetime import datetime, time, timedelta
from pathlib import Path
import random

# Configuration
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
CHANNEL_ID = int(os.environ["FACT_CHANNEL_ID"])
HISTORY_FILE = Path(os.environ.get("HISTORY_FILE", "fact_history.json"))

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Claude client
claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ============================================================================
# CONTENT CONFIGURATION
# ============================================================================

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

# ============================================================================
# HISTORY MANAGEMENT
# ============================================================================

def load_history():
    """Load posting history from JSON file."""
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return {
        "posts": [],           # All posts with full details
        "used_wonders": [],    # Recently used wonder types (reset periodically)
        "used_topics": [],     # Recently used topics (reset periodically)
    }


def save_history(history):
    """Save posting history to JSON file."""
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2, default=str)


def add_to_history(history, post_data):
    """Add a new post to history."""
    history["posts"].append(post_data)

    # Track what we've used recently
    if post_data.get("wonder_type"):
        history["used_wonders"].append(post_data["wonder_type"])
        # Keep only last 5 to allow cycling
        history["used_wonders"] = history["used_wonders"][-5:]

    if post_data.get("topic"):
        history["used_topics"].append(post_data["topic"])
        # Keep only last 8 to allow cycling
        history["used_topics"] = history["used_topics"][-8:]

    save_history(history)


def get_callback_candidate(history):
    """Find a good post from 1-2 weeks ago to callback to."""
    if len(history["posts"]) < 7:
        return None

    now = datetime.utcnow()
    candidates = []

    for post in history["posts"]:
        post_date = datetime.fromisoformat(post["date"])
        days_ago = (now - post_date).days

        # Look for posts 7-21 days old that were facts (not puzzles/what-ifs)
        if 7 <= days_ago <= 21 and post.get("mode") == "fact":
            candidates.append(post)

    return random.choice(candidates) if candidates else None


def get_recent_posts(history, days=7):
    """Get posts from the last N days."""
    if not history["posts"]:
        return []

    now = datetime.utcnow()
    recent = []

    for post in history["posts"]:
        post_date = datetime.fromisoformat(post["date"])
        if (now - post_date).days <= days:
            recent.append(post)

    return recent


def pick_fresh(options, recently_used):
    """Pick an option we haven't used recently, or random if all used."""
    fresh = [o for o in options if o not in recently_used]
    return random.choice(fresh) if fresh else random.choice(options)


# ============================================================================
# CONTENT GENERATION
# ============================================================================

async def generate_summary(content):
    """Generate a concise summary of a post using Haiku."""
    message = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": f"Summarize this in 1 sentence (under 100 words), focusing on the core concept or question:\n\n{content}"
        }]
    )
    return message.content[0].text.strip()


def build_context_block(history):
    """Build context from history to send to Claude."""
    recent = get_recent_posts(history, days=14)

    if not recent:
        return ""

    lines = ["<recent_posts>"]
    for post in recent[-10:]:  # Last 10 posts max
        date = post["date"][:10]
        mode = post.get("mode", "fact")
        topic = post.get("topic", "unknown")
        summary = post.get("summary", "")[:200]
        lines.append(f"[{date}] ({mode}) {topic}: {summary}")
    lines.append("</recent_posts>")

    return "\n".join(lines)


async def generate_fact(history):
    """Generate a surprising fact."""
    topic = pick_fresh(TOPICS, history.get("used_topics", []))
    wonder = pick_fresh(WONDER_TYPES, history.get("used_wonders", []))
    context = build_context_block(history)

    # Check for callback opportunity (~30% chance if available)
    callback = None
    callback_text = ""
    if random.random() < 0.3:
        callback = get_callback_candidate(history)
        if callback:
            callback_text = f"""
CALLBACK OPPORTUNITY: About {(datetime.utcnow() - datetime.fromisoformat(callback['date'])).days} days ago,
you shared this: "{callback.get('summary', '')}"
Consider briefly connecting today's fact to this earlier one if there's a natural link.
If no natural link, ignore this and just share a fresh fact."""

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

    message = claude.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    content = message.content[0].text
    summary = await generate_summary(content)

    return {
        "content": content,
        "mode": "fact",
        "topic": topic,
        "wonder_type": wonder,
        "summary": summary,
        "had_callback": callback is not None,
    }


async def generate_what_if(history):
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

    message = claude.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    content = message.content[0].text
    summary = await generate_summary(content)

    return {
        "content": content,
        "mode": "what_if",
        "topic": topic,
        "summary": summary,
    }


async def generate_puzzle(history):
    """Generate an intriguing puzzle to be answered tomorrow."""
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

    message = claude.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    full_response = message.content[0].text

    # Parse out puzzle and answer
    if "ANSWER:" in full_response:
        parts = full_response.split("ANSWER:", 1)
        puzzle = parts[0].strip()
        answer = parts[1].strip()
    else:
        puzzle = full_response
        answer = "(Answer coming tomorrow)"

    summary = await generate_summary(puzzle)

    return {
        "content": puzzle,
        "mode": "puzzle",
        "topic": topic,
        "summary": summary,
        "answer": answer,
    }


async def generate_weekly_digest(history):
    """Generate a fact and what-if for the weekly digest."""
    fact_result, whatif_result = await asyncio.gather(
        generate_fact(history),
        generate_what_if(history)
    )
    return fact_result, whatif_result


# ============================================================================
# DISCORD BOT
# ============================================================================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    if not weekly_post.is_running():
        weekly_post.start()


@tasks.loop(time=time(hour=19, minute=0))
async def weekly_post():
    """Post weekly digest to the designated channel (Fridays only)."""
    # Only post on Friday
    if datetime.utcnow().weekday() != POSTING_DAY:
        return

    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print(f"Could not find channel {CHANNEL_ID}")
        return

    try:
        history = load_history()

        # Generate both items
        fact, whatif = await generate_weekly_digest(history)

        # Build the embed with both items
        embed = discord.Embed(
            title="Friday Wonder",
            color=0x5865F2,
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name=f"Fact: {fact.get('topic', 'Physics & Math').title()}",
            value=fact["content"],
            inline=False
        )
        embed.add_field(
            name="What If...?",
            value=whatif["content"],
            inline=False
        )
        embed.set_footer(text="Powered by Claude")

        await channel.send(embed=embed)
        print(f"Posted weekly digest: fact about {fact.get('topic')}, what-if about {whatif.get('topic')}")

        # Save both to history
        now = datetime.utcnow().isoformat()
        fact["date"] = now
        whatif["date"] = now
        add_to_history(history, fact)
        add_to_history(history, whatif)

    except Exception as e:
        print(f"Error posting: {e}")
        import traceback
        traceback.print_exc()


@weekly_post.before_loop
async def before_weekly_post():
    await bot.wait_until_ready()


# ============================================================================
# MANUAL COMMANDS
# ============================================================================

@bot.command(name="debug_history")
async def debug_history(ctx):
    """Show raw history file contents."""
    try:
        with open(HISTORY_FILE, "r") as f:
            content = f.read()

        if len(content) > 1900:
            content = content[:1900] + "\n... (truncated)"

        await ctx.send(f"```json\n{content}\n```")
    except Exception as e:
        await ctx.send(f"Error: {e}")


@bot.command(name="fact")
async def get_fact(ctx, *, topic: str = None):
    """Get a fact on demand. Optionally specify a topic."""
    async with ctx.typing():
        history = load_history()

        if topic:
            # Custom topic - simplified prompt
            prompt = f"""Share a genuinely surprising fact about {topic}.

Requirements:
- Lead with the surprise—the thing that breaks intuition
- Include a vivid analogy
- Connect to everyday experience if possible
- End with a question or "notice this next time..."
- 3-5 sentences
- No preamble
- Close with one emoji"""

            message = claude.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            content = message.content[0].text
            used_topic = topic
        else:
            result = await generate_fact(history)
            content = result["content"]
            used_topic = result.get("topic", "Physics & Math")

        embed = discord.Embed(
            title=f"Fact: {used_topic.title()}",
            description=content,
            color=0x5865F2,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")

        await ctx.send(embed=embed)


@bot.command(name="whatif")
async def get_what_if(ctx):
    """Get an absurd hypothetical answered with real physics."""
    async with ctx.typing():
        history = load_history()
        result = await generate_what_if(history)

        embed = discord.Embed(
            title="What If...?",
            description=result["content"],
            color=0xEB459E,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")

        await ctx.send(embed=embed)


@bot.command(name="puzzle")
async def get_puzzle(ctx):
    """Get a puzzle (answer won't be stored for daily reveal)."""
    async with ctx.typing():
        history = load_history()
        result = await generate_puzzle(history)

        embed = discord.Embed(
            title=f"Puzzle: {result.get('topic', 'Math & Physics').title()}",
            description=result["content"],
            color=0xFEE75C,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name} | Answer: use !answer")

        # Store answer temporarily for !answer command
        history["temp_answer"] = result.get("answer", "No answer available")
        save_history(history)

        await ctx.send(embed=embed)


@bot.command(name="answer")
async def get_answer(ctx):
    """Get the answer to the last !puzzle."""
    history = load_history()
    answer = history.get("temp_answer", "No recent puzzle to answer!")

    embed = discord.Embed(
        title="Puzzle Answer",
        description=answer,
        color=0x57F287
    )
    await ctx.send(embed=embed)


@bot.command(name="history")
async def show_history(ctx, count: int = 5):
    """Show recent posts. Usage: !history [count]"""
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
        value="`!fact [topic]` - Get a fact\n`!whatif` - Absurd hypothetical\n`!puzzle` / `!answer` - Puzzle mode\n`!history [n]` - Recent posts",
        inline=False
    )
    await ctx.send(embed=embed)


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
