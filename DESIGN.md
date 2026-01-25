# Design Decisions

This document captures the reasoning behind key design choices for Feynman Bot, so future redesigns don't start from scratch.

## The Problem (January 2025)

**Original setup:** Daily posts, 7 days a week, with different content types each day:
- Mon, Tue, Thu, Sat: Facts
- Wed: What-If
- Fri: Puzzle (answer revealed Saturday)
- Sun: Connections (weekly synthesis)

**What went wrong:** The channel got flooded with unread messages. The content was good when read, but the volume led to ignoring it entirely. The bot became background noise rather than something to look forward to.

> "Daily messages is just too much, I end up ignoring it... the channel is flooded with unread messages"

---

## Expert Panel: Reducing to Something You'll Actually Read

We convened a hypothetical panel of science communicators to think through the redesign:

### Barbara Oakley (Learning How to Learn)
> "Daily is counterproductive. The science says spaced repetition works best with gaps. If you're ignoring messages, you're getting *zero* retention. Three posts per week with proper spacing will beat seven posts you scroll past."

### Randall Munroe (xkcd, What If?)
> "The What-If format works because it's an *event*. If I posted daily, people would tune out. Scarcity creates anticipation. Make each post feel like something arrived, not like the channel is a firehose."

### Richard Feynman
> "The best learning happens when you're curious, not when you're obligated. If the channel feels like homework, it's already failed. Make them *want* to check it."

### Consensus
Less frequent posting preserves the feeling of each post being special. Weekly is better than daily for a single-person audience.

---

## Cadence Options Considered

| Option | Schedule | Pros | Cons |
|--------|----------|------|------|
| **3x/week** | Mon, Wed, Fri | Maintains variety, breathing room | Still might be too much |
| **2x/week** | Tue, Sat | Minimal, high-signal | Loses some content types |
| **Weekly digest** | One day, multiple items | Single touchpoint, never floods | Less frequent |

**Decision:** Start with weekly. Can always increase if it feels too sparse. Can't un-flood a channel.

---

## Expert Panel: Content Pairing

With weekly posting, we needed to decide what goes in each digest.

### On Puzzles

**Martin Gardner:** Keep them. A puzzle that sits with you for two days is worth ten facts. The gap between puzzle and answer is when the subconscious works.

**Vi Hart:** Drop them. Puzzles work with community discussion. A single person reading? It's just homework with a delayed grade.

**Feynman:** The puzzle question is really asking: do you want *engagement* or *delight*? For a once-weekly touchpoint, optimize for delight.

**Decision:** Drop puzzles from scheduled posts. They're still available via `!puzzle` command for on-demand use.

### On Connections (Weekly Synthesis)

The "connections" post tied together the week's content. But with only one post per week, there's nothing to connect.

**Decision:** Remove connections entirely.

### On Pairing

**Barbara Oakley:** Two items is right. More causes cognitive overload. Contrast helps memory—a concrete fact alongside an absurd what-if gives two different hooks.

**Randall Munroe:** Fact + what-if gives grounded wonder plus playful absurdity. Good pairing.

**Decision:** Every Friday = 1 fact + 1 what-if. Consistent, complementary, no decision fatigue.

---

## Final Design

| Aspect | Before | After |
|--------|--------|-------|
| Frequency | Daily (7/week) | Weekly (1/week) |
| Posts per week | 7 separate messages | 1 message with 2 items |
| Content types | Fact, What-If, Puzzle, Connections | Fact + What-If only |
| Puzzle answers | Auto-revealed next day | On-demand via `!puzzle`/`!answer` |
| Posting day | Every day | Friday |
| Posting time | 7pm UTC | 7pm UTC (unchanged) |

### Why Friday?
- Ends the work week on a fun note
- Weekend gives time to sit with the content
- "Friday Wonder" has a nice ring to it

### Why 7pm UTC?
- 2pm Eastern, 11am Pacific — reasonable US hours
- Evening in Europe
- Kept from original design

---

## What We Kept

1. **Smart history tracking** — Still avoids repetition, still cycles through topics/wonder types
2. **Callback system** — ~30% chance to reference facts from 1-2 weeks ago
3. **On-demand commands** — `!fact`, `!whatif`, `!puzzle` still work anytime
4. **Haiku summaries** — Each post still gets a summary for history context
5. **The prompts** — Content generation prompts unchanged (they were good)

---

## What We Removed

1. **MODE_SCHEDULE dict** — No longer routing by day of week
2. **generate_connections()** — Nothing to connect with weekly posting
3. **Puzzle auto-reveal** — No `pending_puzzle_answer` in scheduled flow
4. **Daily task loop** — Now checks `weekday == 4` and returns early otherwise

---

## Cost Impact

| Before | After |
|--------|-------|
| ~$3-5/month | ~$1/month |

7x fewer scheduled API calls.

---

## If Reconsidering Later

### Signs weekly is too sparse:
- You find yourself wanting more
- You use `!fact` and `!whatif` commands frequently between Fridays
- The channel feels dead

### Upgrade path:
1. **Twice weekly:** Add Tuesday. Fact on Tue, What-If + Fact on Fri.
2. **Three times:** Mon/Wed/Fri with rotating content.
3. **Back to daily:** Only if there's a community, not a single reader.

### Signs weekly is still too much:
- Still ignoring messages
- Posts feel like obligation

### Downgrade path:
1. **Biweekly:** Every other Friday
2. **On-demand only:** Remove scheduled posting, just use commands

---

## The Core Insight

**Volume and engagement are inversely related for a single-person audience.**

A community can sustain daily content because there's discussion, reactions, shared discovery. A single person reading alone needs scarcity to maintain the feeling that each post is worth their attention.

The goal isn't maximum content—it's maximum *impact per content*.

---

## Production Hardening (v1.0.0)

Before publishing, we ran an expert panel audit covering security, reliability, UX, and code quality.

### Security Decisions

| Issue | Decision | Rationale |
|-------|----------|-----------|
| Commands can be spammed | 30s cooldown per user | Prevents API cost abuse |
| `!debug_history` exposes data | Removed entirely | No need in production |
| User input in prompts | Truncate to 100 chars | Basic sanitization |

### Reliability Decisions

| Issue | Decision | Rationale |
|-------|----------|-----------|
| Sync API calls block event loop | `asyncio.to_thread()` wrapper | Non-blocking I/O |
| File writes can corrupt on crash | Atomic writes (temp + rename) | Data integrity |
| History grows forever | Auto-prune at 500 posts | Bounded storage |
| Discord embed limit (1024 chars) | `truncate_for_embed()` | Graceful degradation |
| Corrupted JSON file | Catch and start fresh | Self-healing |

### Observability Decisions

| Feature | Implementation | Why |
|---------|----------------|-----|
| Logging | `logging` module, not `print()` | Structured, timestamped |
| Version | `VERSION = "1.0.0"` | Track deployments |
| Health check | `!status` command | Monitor without logs |
| Bot presence | "Watching for !help" | Shows bot is alive |

### UX Decisions

| Issue | Decision | Rationale |
|-------|----------|-----------|
| Default help is ugly | Custom `!help` | Cleaner, grouped |
| Errors show tracebacks | Global error handler | Friendly messages |
| Missing env vars crash | Validate at startup | Helpful error messages |

### What We Kept Simple

- **Single file:** No need for multi-file architecture at this scale
- **No database:** JSON file is sufficient for ~500 posts
- **No admin commands:** Single-user bot doesn't need role checks
- **No web dashboard:** Overkill for personal use

---

*Document created: January 2025*
*Last updated: January 2025*
