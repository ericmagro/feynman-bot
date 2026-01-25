# Changelog

All notable changes to Feynman Bot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-25

First stable release after production hardening audit.

### Changed
- **Breaking:** Switched from daily posts (7/week) to weekly digest (Fridays)
- Each digest contains 1 fact + 1 what-if in a single message
- Removed puzzle and connections modes from scheduled posts (still available on-demand)

### Added
- `!help` - Custom help command with grouped commands
- `!status` - Health check showing version and post count
- Command cooldowns (30s) to prevent API cost abuse
- Proper logging with timestamps
- Atomic file writes to prevent history corruption
- Auto-pruning of history at 500 posts
- Embed truncation to respect Discord's 1024 char limit
- Bot presence ("Watching for !help")
- Global error handler with friendly messages
- Startup validation of environment variables
- MIT LICENSE file
- DESIGN.md documenting architectural decisions
- CHANGELOG.md (this file)

### Removed
- `!debug_history` command (security: exposed raw data)
- Daily posting schedule
- `generate_connections()` function (nothing to connect with weekly posting)

### Fixed
- `datetime.utcnow()` deprecation (now uses `datetime.now(timezone.utc)`)
- Synchronous API calls blocking event loop (now uses `asyncio.to_thread()`)
- Potential file corruption on concurrent writes

### Security
- Added 30-second cooldown on content commands
- User-provided topics truncated to 100 characters
- Removed debug command that exposed history file

## [0.1.0] - 2025-01-24

Initial release (pre-audit).

### Added
- Daily posting with rotating content types (fact, what-if, puzzle, connections)
- Smart history tracking to avoid repetition
- Topic and wonder type cycling
- Callback system (~30% chance to reference old posts)
- On-demand commands: `!fact`, `!whatif`, `!puzzle`, `!answer`, `!history`, `!schedule`
- Claude Sonnet for content generation, Haiku for summaries
