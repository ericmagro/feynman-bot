# CLAUDE.md

Discord bot that posts weekly physics/math content. Single-file Python app (~700 lines), deployed to Railway.

## Quick Reference

| What | Where |
|------|-------|
| All code | `bot.py` (sections marked with `# ===` headers) |
| Unit tests | `test_bot.py` (history, deduplication, utilities) |
| Pytest config | `pyproject.toml` |
| Setup & features | `README.md` |
| Design rationale | `DESIGN.md` (why weekly, why fact+what-if, production decisions) |
| Version history | `CHANGELOG.md` |
| Remaining work | `TODO.md` (prioritized improvements) |

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
# Optional: override default models
GENERATION_MODEL=claude-sonnet-4-6
SUMMARY_MODEL=claude-haiku-4-5-20251001

# 3. Run locally
export $(cat .env | xargs) && python bot.py

# 4. Run unit tests
pytest test_bot.py -v

# 5. Test via Discord commands: !status, !fact, !whatif, !puzzle

# 6. Deploy: git push (Railway auto-deploys from main)
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

## Testing Guide

### When to Write Tests

| Change Type | Test Required? | Why |
|-------------|----------------|-----|
| New pure function | Yes | Fast, high value, catch edge cases |
| New `generate_*` function | Yes | Core functionality, test with mocked Claude |
| Bug fix | Yes | Regression test prevents recurrence |
| Prompt modification | Optional | Characterization test if behavior matters |
| New Discord command | No | Test extracted logic, not Discord glue |
| Config/constant change | No | Unless it affects logic (like `MAX_HISTORY_POSTS`) |

### What to Test (Priority Order)

1. **Pure functions** — `pick_fresh`, `truncate_for_embed`, history helpers
2. **Async generation** — Mock Claude, verify prompt structure and response parsing
3. **Error handling** — API failures, malformed data, edge cases
4. **File I/O** — Atomic writes, corruption recovery

Skip: Discord event handlers, logging, exact prompt wording

### Test Patterns by Component Type

**Pure Functions** (simplest):
```python
def test_avoids_recently_used(self):
    result = bot.pick_fresh(["a", "b", "c"], ["a", "b"])
    assert result == "c"
```

**File I/O** (use `tmp_path` fixture):
```python
def test_save_load_roundtrip(tmp_path):
    with patch.object(bot, 'HISTORY_FILE', tmp_path / "history.json"):
        bot.save_history({"posts": [], "used_wonders": [], "used_topics": []})
        result = bot.load_history()
    assert result["posts"] == []
```

**Async API Calls** (mock `call_claude`):
```python
@pytest.mark.asyncio
async def test_generate_fact_structure(empty_history):
    with patch.object(bot, 'call_claude', new_callable=AsyncMock) as mock:
        mock.return_value = "Surprising fact. 🔬"
        result = await bot.generate_fact(empty_history)

    assert result["mode"] == "fact"
    assert "topic" in result
```

**Chained Async Calls** (fact + summary):
```python
@pytest.mark.asyncio
async def test_generate_fact_includes_summary(empty_history):
    with patch.object(bot, 'call_claude', new_callable=AsyncMock) as mock:
        mock.side_effect = ["The fact. 🌟", "Brief summary."]
        result = await bot.generate_fact(empty_history)

    assert result["summary"] == "Brief summary."
    assert mock.call_count == 2
```

**Error Handling**:
```python
@pytest.mark.asyncio
async def test_handles_rate_limit():
    with patch.object(bot.claude.messages, 'create') as mock:
        mock.side_effect = anthropic.RateLimitError(...)
        with pytest.raises(anthropic.RateLimitError):
            await bot.call_claude("model", 100, "prompt")
```

### Running Tests

```bash
pytest test_bot.py -v                    # Full suite
pytest test_bot.py::TestPickFresh -v     # Specific class
pytest test_bot.py --cov=bot             # With coverage
```

### Adding pytest-asyncio Config

Add to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["test_bot.py"]
```

## Async Pattern Note

The `call_claude()` function (line 192) uses `asyncio.to_thread()` because the Anthropic SDK is synchronous. Without this wrapper, API calls would block the Discord event loop, freezing the bot during generation. Don't remove it.

---

*Last reviewed: January 2025*
