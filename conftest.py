"""Pytest configuration - sets up environment for testing."""

import os
import sys

# Set required environment variables BEFORE importing bot
# These are dummy values for testing - the bot won't actually connect
os.environ.setdefault("DISCORD_TOKEN", "test_token")
os.environ.setdefault("ANTHROPIC_API_KEY", "test_key")
os.environ.setdefault("FACT_CHANNEL_ID", "123456789")
os.environ.setdefault("HISTORY_FILE", "/tmp/test_history.json")
