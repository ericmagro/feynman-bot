# TODO

Prioritized improvements identified during January 2025 audit.

## Completed (v1.1.0)

- [x] **Unit test suite** — 29 tests for history, deduplication, utilities (`test_bot.py`)
- [x] **Pinned dependency versions** — Upper bounds prevent breaking changes
- [x] **Configurable models** — `GENERATION_MODEL` and `SUMMARY_MODEL` env vars
- [x] **Named constants** — Replaced magic numbers with `RECENT_WONDERS_MEMORY`, etc.
- [x] **Testing guide** — When/what/how to test in `CLAUDE.md`

## Medium Priority (Next Up)

### Add retry logic for transient API errors
**Location:** `bot.py` `call_claude()` function (~line 195)

Transient errors (rate limits, connection timeouts) currently cause complete failures. Add exponential backoff retry for `RateLimitError` and `APIConnectionError`.

```python
# Pseudocode
@retry(max_attempts=3, backoff_factor=2)
async def call_claude(...):
    ...
```

### Add history file locking
**Location:** `bot.py` `add_to_history()` function (~line 125)

Parallel generation (`asyncio.gather` in `generate_weekly_digest`) could cause race conditions when both tasks update history simultaneously. Last-write-wins currently, which may lose tracking data.

```python
# Pseudocode
history_lock = asyncio.Lock()

async def safe_add_to_history(history, post_data):
    async with history_lock:
        history = load_history()  # Re-read latest
        add_to_history(history, post_data)
```

### Create operations runbook
**New file:** `OPERATIONS.md`

Document what to do when:
- Daily cron fails silently (task loop crashed)
- History file becomes corrupted
- Anthropic API goes down
- How to manually trigger a post
- How to monitor logs on Railway

## Nice to Have

### Health check HTTP endpoint
Add a simple HTTP server for Railway health monitoring (auto-restart if unhealthy). Currently requires Discord or logs to verify bot health.

### Improve puzzle parsing robustness
**Location:** `bot.py` `generate_puzzle()` (~line 361)

Add debug logging when Claude's response is missing the `ANSWER:` separator.

### Add metrics/analytics logging
Track which topics/wonders are most generated, callback success rate, etc. Periodic logging to help understand content patterns.

### Standardize to named constants
A few magic numbers remain (e.g., cooldown durations, history count limits in commands). Could extract to config section for consistency.

---

*Last updated: January 2025 (v1.1.0)*
