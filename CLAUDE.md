# CLAUDE.md

Discord bot that posts weekly physics/math content. Single-file Python app (~700 lines), deployed to Railway.

## Quick Reference

| What | Where |
|------|-------|
| All code | `bot.py` (sections marked with `# ===` headers) |
| Setup & features | `README.md` |
| Design rationale | `DESIGN.md` (why weekly, why fact+what-if, production decisions) |
| Version history | `CHANGELOG.md` |

## When to Read What

- **"How do I set this up?"** → README.md
- **"Why does it work this way?"** → DESIGN.md
- **"What changed in version X?"** → CHANGELOG.md
- **"How do I modify the code?"** → Keep reading below

## Code Structure (bot.py)

```
Lines 13-82:   Configuration (env vars, constants, topics, wonder types)
Lines 84-182:  History management (JSON persistence, deduplication, callbacks)
Lines 184-394: Content generation (Claude API calls, prompts, parallel generation)
Lines 396-490: Discord bot core (events, scheduled task, error handling)
Lines 492-700: Commands (!fact, !whatif, !puzzle, !help, !status, etc.)
```

## Development Workflow

```bash
# 1. Set up environment
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Create .env (not committed)
DISCORD_TOKEN=your_token
ANTHROPIC_API_KEY=your_key
FACT_CHANNEL_ID=your_channel
HISTORY_FILE=./fact_history.json

# 3. Run locally
export $(cat .env | xargs) && python bot.py

# 4. Test via Discord commands: !status, !fact, !whatif, !puzzle

# 5. Deploy: git push (Railway auto-deploys from main)
```

## What You'll Break: Prompt Engineering

The content generation prompts (lines 265-323) encode design decisions that aren't obvious. Modify carefully.

### Fact Prompt Structure (lines 265-280)

| Instruction | Why It Exists |
|-------------|---------------|
| "Lead with the surprise" | Feynman principle: hook first, context second |
| "Include a vivid analogy" | Vi Hart influence: ground abstract in concrete |
| "Connect to daily life" | Makes facts memorable and shareable |
| "End with question/challenge" | Drives engagement, not passive reading |
| "No preamble" | Without this, Claude adds "Here's an interesting fact..." |
| "Close with one emoji" | Consistent formatting, signals completion |
| "Do NOT repeat from recent_posts" | Deduplication—context block enables this |

### What-If Prompt Structure (lines 300-323)

| Instruction | Why It Exists |
|-------------|---------------|
| "Silly premise, rigorous analysis" | Munroe's What-If style |
| "Use specific numbers" | Vague answers feel lazy; specifics feel researched |
| "Examples of good premises" | Guides Claude toward absurdist-but-answerable |

### Breaking Changes to Avoid

- **Removing "No preamble"** → Inconsistent output format
- **Removing "Do NOT repeat"** → Content repetition within weeks
- **Lowering max_tokens below 512** → Truncated thoughts mid-sentence
- **Adding complex formatting** → May exceed Discord's 1024-char field limit
- **Removing emoji instruction** → Inconsistent visual closure

### Callback System (lines 248-263)

~30% chance to reference a fact from 1-2 weeks ago. The prompt says "if there's a natural link... if no natural link, ignore." This prevents forced connections while enabling spaced repetition.

## Async Pattern Note

The `call_claude()` function (line 192) uses `asyncio.to_thread()` because the Anthropic SDK is synchronous. Without this wrapper, API calls would block the Discord event loop, freezing the bot during generation. Don't remove it.

---

*Last reviewed: January 2025*
