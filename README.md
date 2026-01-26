# Feynman Bot

A Discord bot that delivers weekly doses of physics and math wonder, designed to break your intuition and make you see the world differently.

Named after Richard Feynman, who believed that the beauty of nature lies in its surprising depth. Built with insights from a panel of science communicators: Feynman's playfulness, Gardner's puzzle-mindedness, Munroe's absurdist rigor, and more.

## How It Works

Every **Friday at 7pm UTC**, the bot posts a digest with two items:

| Content Type | Description |
|--------------|-------------|
| **Fact** | A surprising truth that breaks intuition, with vivid analogies and everyday connections |
| **What If?** | An absurd hypothetical answered with real physics, Randall Munroe style |

### Example Output

```
┌─────────────────────────────────────────────────┐
│  Friday Wonder                                  │
├─────────────────────────────────────────────────┤
│  Fact: Quantum Mechanics                        │
│                                                 │
│  Your body emits about 100 watts of infrared   │
│  radiation right now—enough to power a bright  │
│  light bulb. You're literally glowing, just in │
│  wavelengths your eyes can't see. Thermal      │
│  cameras don't "see heat"—they see YOU,        │
│  shining like a dim star...                    │
│                                                 │
├─────────────────────────────────────────────────┤
│  What If...?                                    │
│                                                 │
│  What if you tried to cook a turkey by         │
│  slapping it? You'd need to slap it at about   │
│  1,665 mph—faster than a bullet—to deliver     │
│  enough kinetic energy in one hit...           │
└─────────────────────────────────────────────────┘
```

## Features

### Smart Content Generation

The bot uses Claude (Sonnet) to generate content with several intelligent features:

- **Topic cycling** — Rotates through 20 physics/math topics (quantum mechanics, topology, chaos theory, etc.) avoiding recent repeats
- **Wonder type rotation** — Cycles through 10 "types of wonder" (things proven but never observed, patterns across domains, etc.)
- **Callback system** — ~30% chance to reference and connect to a fact from 1-2 weeks ago, reinforcing learning
- **Deduplication** — Tracks all past posts to avoid repetition

### On-Demand Commands

Use these anytime to get content outside the weekly schedule:

| Command | Description |
|---------|-------------|
| `!fact [topic]` | Get a surprising fact (optionally specify a topic like `!fact black holes`) |
| `!whatif` | Get an absurd hypothetical with real physics |
| `!puzzle` | Get a brain-teaser or paradox |
| `!answer` | Reveal the answer to the last `!puzzle` |
| `!history [n]` | Show last n posts (default 5, max 20) |
| `!schedule` | Show the posting schedule |
| `!status` | Show bot version and health |
| `!help` | Show all commands |

**Note:** Content commands (`!fact`, `!whatif`, `!puzzle`) have a 30-second cooldown per user to prevent API cost abuse.

### Topics Covered

The bot explores: quantum mechanics, number theory, thermodynamics, topology, relativity, probability paradoxes, chaos theory, electromagnetism, group theory, fluid dynamics, prime numbers, cosmology, game theory, optics, combinatorics, statistical mechanics, black holes, wave phenomena, graph theory, and orbital mechanics.

### Types of Wonder

Content rotates through different flavors of mathematical/physical beauty:

- Something that seems impossible but is mathematically proven true
- A simple question with a surprisingly complex or unsolved answer
- A pattern that appears unexpectedly across unrelated domains
- A problem that stumped scientists for decades (or centuries)
- Something proven to exist but never directly observed
- Two seemingly unrelated things that turn out to be equivalent
- A result that contradicts everyday intuition
- A physical phenomenon with no complete explanation yet
- An everyday object hiding deep mathematical structure
- A limit or bound that nature seems to respect mysteriously

## Setup

### Prerequisites

- Python 3.9+
- A Discord account
- An Anthropic API key ([console.anthropic.com](https://console.anthropic.com))

### 1. Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** → name it → Create
3. Go to **Bot** tab → **Add Bot**
4. Under **Privileged Gateway Intents**, enable:
   - **Message Content Intent** (required for commands)
5. Click **Reset Token** and copy your bot token (save it securely)
6. Go to **OAuth2** → **URL Generator**:
   - Scopes: `bot`
   - Bot Permissions: `Send Messages`, `Embed Links`
7. Copy the generated URL and open it to invite the bot to your server

### 2. Get Your Channel ID

1. In Discord, go to **Settings** → **Advanced** → Enable **Developer Mode**
2. Right-click your target channel → **Copy Channel ID**

### 3. Deploy to Railway

1. Fork or push this repo to GitHub

2. Go to [Railway](https://railway.app) → **New Project** → **Deploy from GitHub**

3. **Add a persistent volume** (critical for history):
   - Click **+ Create** in top right → **Volume**
   - Select your worker service
   - Mount path: `/data`

   > Without this, your posting history will reset on every deploy!

4. Add environment variables in Railway:

   | Variable | Value | Description |
   |----------|-------|-------------|
   | `DISCORD_TOKEN` | `your_token_here` | Bot token from Discord Developer Portal |
   | `ANTHROPIC_API_KEY` | `sk-ant-...` | API key from Anthropic Console |
   | `FACT_CHANNEL_ID` | `123456789` | Channel ID where bot posts |
   | `HISTORY_FILE` | `/data/fact_history.json` | Path for persistent history |

5. Deploy and check logs for `Logged in as YourBotName#1234`

### Alternative: Run Locally

```bash
# Clone the repo
git clone https://github.com/yourusername/feynman-bot.git
cd feynman-bot

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file (don't commit this!)
cat > .env << 'EOF'
DISCORD_TOKEN=your_bot_token
ANTHROPIC_API_KEY=your_anthropic_key
FACT_CHANNEL_ID=your_channel_id
HISTORY_FILE=./fact_history.json
EOF

# Load environment and run
export $(cat .env | xargs)  # On Windows, set each variable manually
python bot.py
```

## Configuration

### Change Posting Schedule

Edit these values in `bot.py`:

```python
# Line ~79: Which day to post (0=Monday, 4=Friday, 6=Sunday)
POSTING_DAY = 4  # Friday

# Line ~433: What time to post (UTC)
@tasks.loop(time=time(hour=19, minute=0))  # 7pm UTC = 2pm EST = 11am PST
```

### Customize Topics

Add or modify the `TOPICS` list in `bot.py` (line ~69):

```python
TOPICS = [
    "quantum mechanics", "number theory", "thermodynamics",
    # Add your own topics here...
]
```

### Customize Wonder Types

Modify the `WONDER_TYPES` list in `bot.py` (line ~55) to change the flavors of content.

### Reduce API Costs

Replace `claude-sonnet-4-20250514` with `claude-haiku-4-5-20251001` in the code for ~10x cheaper generation (with lower quality).

## Architecture

```
bot.py (single file, ~700 lines)
├── Configuration
│   ├── Environment validation (fails fast with helpful errors)
│   ├── Logging setup (structured logs with timestamps)
│   └── Topics and wonder types
├── History Management
│   ├── Atomic file writes (prevents corruption)
│   ├── Auto-pruning (keeps last 500 posts)
│   └── Corrupted file recovery
├── Content Generation
│   ├── Async Claude API calls (non-blocking)
│   ├── Error handling with retries
│   └── Embed truncation (respects Discord limits)
├── Discord Bot
│   ├── Custom help command
│   ├── Command cooldowns (30s per user)
│   ├── Global error handler
│   └── Bot presence/status
└── Entry Point
```

### Data Flow

1. **Weekly trigger** → Check if Friday → Load history
2. **Generate content** → Pick fresh topic/wonder type → Build context from history → Call Claude API
3. **Post to Discord** → Format as embed → Send to channel
4. **Save to history** → Update JSON file with new post + summary

### History File Structure

The bot maintains `fact_history.json`:

```json
{
  "posts": [
    {
      "date": "2025-01-24T19:00:00",
      "mode": "fact",
      "topic": "quantum mechanics",
      "wonder_type": "something that seems impossible but is proven true",
      "summary": "Your body constantly emits infrared radiation...",
      "content": "Full post content here...",
      "had_callback": false
    }
  ],
  "used_wonders": ["wonder1", "wonder2", "..."],
  "used_topics": ["topic1", "topic2", "..."],
  "temp_answer": "Answer to last !puzzle command"
}
```

## Troubleshooting

### Bot won't start

- Check logs for `ERROR: Missing required environment variable`
- Ensure all four env vars are set: `DISCORD_TOKEN`, `ANTHROPIC_API_KEY`, `FACT_CHANNEL_ID`, `HISTORY_FILE`

### Bot doesn't post on schedule

- Check that `POSTING_DAY` matches your expected day (0=Monday, 6=Sunday)
- Verify the time is in UTC (not your local timezone)
- Check Railway logs for errors
- Ensure the bot has permission to send messages in the channel
- Use `!status` to verify the bot is running

### History resets after deploy

- You need a **persistent volume** mounted at `/data`
- Set `HISTORY_FILE=/data/fact_history.json` in environment variables
- Use `!status` to check how many posts are in history

### "Could not find channel" error

- Double-check your `FACT_CHANNEL_ID` is correct
- Ensure the bot has been invited to the server containing that channel
- Verify the bot has `Send Messages` and `Embed Links` permissions

### API errors / "Please try again later"

- Verify your `ANTHROPIC_API_KEY` is valid and has credits
- Check [status.anthropic.com](https://status.anthropic.com) for outages
- Check Railway logs for specific error messages

### "Please wait Xs before using this command"

- Commands have a 30-second cooldown per user to prevent API cost abuse
- This is working as intended

## Cost Estimate

**~$1/month** with weekly posting:

| Component | Model | Cost per Post | Weekly Cost |
|-----------|-------|---------------|-------------|
| Fact generation | Sonnet | ~$0.02 | $0.08/mo |
| What-if generation | Sonnet | ~$0.02 | $0.08/mo |
| Summaries (2x) | Haiku | ~$0.001 | $0.004/mo |

On-demand commands (`!fact`, `!whatif`, `!puzzle`) add ~$0.02 each.

## Design Philosophy

This bot is built around principles from great science communicators:

| Principle | Inspiration | Implementation |
|-----------|-------------|----------------|
| **Break intuition first** | Feynman | Lead with the surprise, not the setup |
| **Types of wonder** | Gardner | Rotate through different flavors of mathematical beauty |
| **Ground in the everyday** | Vi Hart | Connect abstract facts to coffee, traffic, phone screens |
| **Absurdist rigor** | Munroe | Silly questions deserve serious physics |
| **Spaced repetition** | Oakley | Callbacks to old facts help them stick |
| **Less is more** | Oakley | Weekly cadence prevents overwhelm |

## Dependencies

- `discord.py>=2.3.0` — Discord API wrapper
- `anthropic>=0.39.0` — Claude API client

## For Contributors

| Document | Purpose |
|----------|---------|
| `CLAUDE.md` | AI assistant guidance: code structure, dev workflow, prompt documentation |
| `DESIGN.md` | Architectural decisions: why weekly cadence, why fact+what-if, production hardening |
| `CHANGELOG.md` | Version history following Keep a Changelog format |

## License

MIT

---

*"The first principle is that you must not fool yourself—and you are the easiest person to fool."* — Richard Feynman
