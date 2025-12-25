# Daily Wonder Bot 🌌

A Discord bot that posts surprising physics and math content daily, designed to break your intuition and make you see the world differently.

Built with insights from a panel of science communicators: Feynman's playfulness, Gardner's puzzle-mindedness, Munroe's absurdist rigor, and more.

## Features

### Content Modes
- **Facts** (Mon, Tue, Thu, Sat) — Surprising truths that break intuition, with vivid analogies and everyday connections
- **What If?** (Wed) — Absurd hypotheticals answered with real physics, Randall Munroe style
- **Puzzles** (Fri) — Intriguing paradoxes with answers revealed the next day  
- **Connections** (Sun) — Weekly synthesis tying the week's content together

### Smart History
- Tracks all posts to avoid repetition
- Cycles through "types of wonder" (things that seem impossible but are true, patterns that appear unexpectedly, etc.)
- Spaced repetition callbacks to facts from 1-2 weeks ago (~30% of posts)
- Puzzle answers automatically revealed the following day

### Commands
| Command | Description |
|---------|-------------|
| `!fact [topic]` | Get a fact (optionally about a specific topic) |
| `!whatif` | Get an absurd hypothetical |
| `!puzzle` | Get a puzzle |
| `!answer` | Reveal answer to last `!puzzle` |
| `!history [n]` | Show last n posts (default 5) |
| `!schedule` | Show the weekly posting schedule |

## Setup

### 1. Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" → name it → Create
3. Go to "Bot" tab → "Add Bot"
4. Enable **Message Content Intent** under Privileged Gateway Intents
5. Copy your bot token
6. Go to "OAuth2" → "URL Generator"
   - Scopes: `bot`
   - Permissions: `Send Messages`, `Embed Links`
7. Open the generated URL to invite the bot

### 2. Get Your Channel ID

1. Enable Developer Mode in Discord (Settings → Advanced)
2. Right-click your target channel → "Copy Channel ID"

### 3. Deploy to Railway

1. Push this repo to GitHub
2. Go to [Railway](https://railway.app) → New Project → Deploy from GitHub
3. **Important:** Add a persistent volume for history:
   - Go to your service → Settings → Add Volume
   - Mount path: `/data`
4. Add environment variables:

| Variable | Value |
|----------|-------|
| `DISCORD_TOKEN` | Your bot token |
| `ANTHROPIC_API_KEY` | Your Claude API key |
| `FACT_CHANNEL_ID` | Channel ID |
| `HISTORY_FILE` | `/data/fact_history.json` |

5. Deploy! Check logs for "Logged in as..."

## Configuration

### Change posting time
Edit the `time=time(hour=9, minute=0)` in `bot.py` (UTC timezone).

### Change schedule
Modify `MODE_SCHEDULE` dict:
```python
MODE_SCHEDULE = {
    0: "fact",       # Monday
    1: "fact",       # Tuesday
    2: "what_if",    # Wednesday
    3: "fact",       # Thursday
    4: "puzzle",     # Friday
    5: "fact",       # Saturday
    6: "connections", # Sunday
}
```

### Add topics or wonder types
Append to `TOPICS` or `WONDER_TYPES` lists in `bot.py`.

### Reduce costs
Change `claude-sonnet-4-20250514` to `claude-haiku-4-5-20251001` (~10x cheaper).

## History File Structure

The bot maintains `fact_history.json`:

```json
{
  "posts": [
    {
      "date": "2025-01-15T09:00:00",
      "mode": "fact",
      "topic": "quantum mechanics",
      "wonder_type": "something that seems impossible but is proven true",
      "summary": "The first 300 chars of the post...",
      "content": "Full post content..."
    }
  ],
  "used_wonders": ["last", "five", "wonder", "types", "used"],
  "used_topics": ["last", "eight", "topics"],
  "pending_puzzle_answer": "Answer to reveal tomorrow, if any"
}
```

The history is sent to Claude as context to prevent repetition and enable callbacks.

## Local Development

```bash
# Create .env (don't commit this)
cat > .env << EOF
DISCORD_TOKEN=your_token
ANTHROPIC_API_KEY=your_key
FACT_CHANNEL_ID=your_channel_id
HISTORY_FILE=./fact_history.json
EOF

# Load env and run
export $(cat .env | xargs)
pip install -r requirements.txt
python bot.py
```

## Design Philosophy

This bot is designed around insights from science communicators:

- **Break intuition first** (Feynman) — Lead with the surprise, not the setup
- **Types of wonder** (Gardner) — Rotate through different flavors of mathematical beauty
- **Ground in the everyday** (Vi Hart) — Connect abstract facts to coffee, traffic, phone screens
- **Absurdist rigor** (Munroe) — Silly questions deserve serious physics
- **Spaced repetition** (Oakley) — Callbacks to old facts help them stick
- **See the connections** (Sagan) — Weekly synthesis shows where facts fit in the larger tapestry

## Cost Estimate

~$2-5/month with Sonnet, ~$0.20-0.50/month with Haiku.
