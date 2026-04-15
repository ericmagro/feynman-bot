"""Unit tests for Feynman Bot.

Run with: pytest test_bot.py -v
"""

import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the functions we want to test
import bot


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def empty_history():
    """Return an empty history structure."""
    return {
        "posts": [],
        "used_wonders": [],
        "used_topics": [],
    }


@pytest.fixture
def sample_history():
    """Return history with sample posts."""
    now = datetime.now(timezone.utc)
    return {
        "posts": [
            {
                "date": (now - timedelta(days=14)).isoformat(),
                "mode": "fact",
                "topic": "quantum mechanics",
                "summary": "Quantum entanglement is spooky.",
                "wonder_type": "something proven to exist but never directly observed",
            },
            {
                "date": (now - timedelta(days=7)).isoformat(),
                "mode": "fact",
                "topic": "thermodynamics",
                "summary": "Entropy always increases.",
                "wonder_type": "a result that contradicts everyday intuition",
            },
            {
                "date": (now - timedelta(days=3)).isoformat(),
                "mode": "what_if",
                "topic": "cosmology",
                "summary": "What if the sun disappeared?",
            },
        ],
        "used_wonders": ["something proven to exist but never directly observed", "a result that contradicts everyday intuition"],
        "used_topics": ["quantum mechanics", "thermodynamics", "cosmology"],
    }


@pytest.fixture
def temp_history_file(tmp_path):
    """Create a temporary history file path."""
    return tmp_path / "test_history.json"


# =============================================================================
# HISTORY MANAGEMENT TESTS
# =============================================================================

class TestLoadHistory:
    """Tests for load_history()."""

    def test_returns_empty_when_file_missing(self, temp_history_file):
        """Should return empty history when file doesn't exist."""
        with patch.object(bot, 'HISTORY_FILE', temp_history_file):
            result = bot.load_history()

        assert result == {"posts": [], "used_wonders": [], "used_topics": []}

    def test_loads_existing_file(self, temp_history_file, sample_history):
        """Should load and return existing history."""
        temp_history_file.write_text(json.dumps(sample_history))

        with patch.object(bot, 'HISTORY_FILE', temp_history_file):
            result = bot.load_history()

        assert len(result["posts"]) == 3
        assert result["posts"][0]["topic"] == "quantum mechanics"

    def test_handles_corrupted_json(self, temp_history_file):
        """Should return empty history when JSON is corrupted."""
        temp_history_file.write_text("{ invalid json }")

        with patch.object(bot, 'HISTORY_FILE', temp_history_file):
            result = bot.load_history()

        assert result == {"posts": [], "used_wonders": [], "used_topics": []}


class TestSaveHistory:
    """Tests for save_history()."""

    def test_saves_history_to_file(self, temp_history_file, sample_history):
        """Should save history to JSON file."""
        with patch.object(bot, 'HISTORY_FILE', temp_history_file):
            bot.save_history(sample_history)

        assert temp_history_file.exists()
        loaded = json.loads(temp_history_file.read_text())
        assert len(loaded["posts"]) == 3

    def test_atomic_write(self, temp_history_file, sample_history):
        """Should use atomic write (no .tmp file left behind)."""
        with patch.object(bot, 'HISTORY_FILE', temp_history_file):
            bot.save_history(sample_history)

        tmp_file = temp_history_file.with_suffix(".tmp")
        assert not tmp_file.exists()


class TestAddToHistory:
    """Tests for add_to_history()."""

    def test_adds_post_to_history(self, temp_history_file, empty_history):
        """Should add a new post to history."""
        with patch.object(bot, 'HISTORY_FILE', temp_history_file):
            post = {
                "mode": "fact",
                "topic": "topology",
                "wonder_type": "a pattern that appears unexpectedly",
                "summary": "Coffee cups and donuts are the same.",
            }
            bot.add_to_history(empty_history, post)

        assert len(empty_history["posts"]) == 1
        assert empty_history["posts"][0]["topic"] == "topology"

    def test_tracks_used_topics(self, temp_history_file, empty_history):
        """Should track used topics."""
        with patch.object(bot, 'HISTORY_FILE', temp_history_file):
            post = {"topic": "topology", "mode": "fact"}
            bot.add_to_history(empty_history, post)

        assert "topology" in empty_history["used_topics"]

    def test_tracks_used_wonders(self, temp_history_file, empty_history):
        """Should track used wonder types."""
        with patch.object(bot, 'HISTORY_FILE', temp_history_file):
            post = {"wonder_type": "a famous paradox", "mode": "fact"}
            bot.add_to_history(empty_history, post)

        assert "a famous paradox" in empty_history["used_wonders"]

    def test_prunes_old_posts_when_over_limit(self, temp_history_file, empty_history):
        """Should prune old posts when over MAX_HISTORY_POSTS."""
        with patch.object(bot, 'HISTORY_FILE', temp_history_file):
            with patch.object(bot, 'MAX_HISTORY_POSTS', 3):
                # Add 5 posts
                for i in range(5):
                    bot.add_to_history(empty_history, {"topic": f"topic_{i}", "mode": "fact"})

        assert len(empty_history["posts"]) == 3
        # Should keep the most recent
        assert empty_history["posts"][0]["topic"] == "topic_2"
        assert empty_history["posts"][2]["topic"] == "topic_4"

    def test_limits_used_wonders_memory(self, temp_history_file, empty_history):
        """Should limit used_wonders to RECENT_WONDERS_MEMORY."""
        with patch.object(bot, 'HISTORY_FILE', temp_history_file):
            with patch.object(bot, 'RECENT_WONDERS_MEMORY', 3):
                for i in range(5):
                    bot.add_to_history(empty_history, {"wonder_type": f"wonder_{i}", "mode": "fact"})

        assert len(empty_history["used_wonders"]) == 3
        assert empty_history["used_wonders"] == ["wonder_2", "wonder_3", "wonder_4"]

    def test_limits_used_topics_memory(self, temp_history_file, empty_history):
        """Should limit used_topics to RECENT_TOPICS_MEMORY."""
        with patch.object(bot, 'HISTORY_FILE', temp_history_file):
            with patch.object(bot, 'RECENT_TOPICS_MEMORY', 3):
                for i in range(5):
                    bot.add_to_history(empty_history, {"topic": f"topic_{i}", "mode": "fact"})

        assert len(empty_history["used_topics"]) == 3
        assert empty_history["used_topics"] == ["topic_2", "topic_3", "topic_4"]


# =============================================================================
# CALLBACK CANDIDATE TESTS
# =============================================================================

class TestGetCallbackCandidate:
    """Tests for get_callback_candidate()."""

    def test_returns_none_with_few_posts(self, empty_history):
        """Should return None when fewer than 7 posts."""
        empty_history["posts"] = [{"date": datetime.now(timezone.utc).isoformat()}] * 5
        result = bot.get_callback_candidate(empty_history)
        assert result is None

    def test_returns_none_when_no_posts_in_range(self):
        """Should return None when no posts are 7-21 days old."""
        now = datetime.now(timezone.utc)
        history = {
            "posts": [
                {"date": (now - timedelta(days=2)).isoformat(), "mode": "fact"},  # Too recent
                {"date": (now - timedelta(days=30)).isoformat(), "mode": "fact"},  # Too old
            ] * 5,
            "used_wonders": [],
            "used_topics": [],
        }
        result = bot.get_callback_candidate(history)
        assert result is None

    def test_finds_candidate_in_range(self):
        """Should find a fact post that's 7-21 days old."""
        now = datetime.now(timezone.utc)
        target_post = {
            "date": (now - timedelta(days=10)).isoformat(),
            "mode": "fact",
            "topic": "topology",
        }
        history = {
            "posts": [
                {"date": (now - timedelta(days=2)).isoformat(), "mode": "fact"},
                {"date": (now - timedelta(days=2)).isoformat(), "mode": "fact"},
                {"date": (now - timedelta(days=2)).isoformat(), "mode": "fact"},
                {"date": (now - timedelta(days=2)).isoformat(), "mode": "fact"},
                {"date": (now - timedelta(days=2)).isoformat(), "mode": "fact"},
                {"date": (now - timedelta(days=2)).isoformat(), "mode": "fact"},
                target_post,
            ],
            "used_wonders": [],
            "used_topics": [],
        }
        result = bot.get_callback_candidate(history)
        assert result == target_post

    def test_ignores_non_fact_posts(self):
        """Should only consider posts with mode='fact'."""
        now = datetime.now(timezone.utc)
        history = {
            "posts": [
                {"date": (now - timedelta(days=10)).isoformat(), "mode": "what_if"},
                {"date": (now - timedelta(days=10)).isoformat(), "mode": "puzzle"},
            ] * 5,
            "used_wonders": [],
            "used_topics": [],
        }
        result = bot.get_callback_candidate(history)
        assert result is None


# =============================================================================
# RECENT POSTS TESTS
# =============================================================================

class TestGetRecentPosts:
    """Tests for get_recent_posts()."""

    def test_returns_empty_list_when_no_posts(self, empty_history):
        """Should return empty list when no posts exist."""
        result = bot.get_recent_posts(empty_history, days=7)
        assert result == []

    def test_filters_by_days(self, sample_history):
        """Should only return posts within the specified days."""
        result = bot.get_recent_posts(sample_history, days=5)
        assert len(result) == 1
        assert result[0]["topic"] == "cosmology"

    def test_returns_all_recent_posts(self, sample_history):
        """Should return all posts within range."""
        result = bot.get_recent_posts(sample_history, days=14)
        assert len(result) == 3  # 14-day, 7-day, and 3-day posts (inclusive)

    def test_handles_malformed_dates(self):
        """Should skip posts with invalid dates."""
        history = {
            "posts": [
                {"date": "invalid-date", "topic": "bad"},
                {"topic": "no-date"},  # Missing date
            ],
            "used_wonders": [],
            "used_topics": [],
        }
        result = bot.get_recent_posts(history, days=7)
        assert result == []


# =============================================================================
# PICK FRESH TESTS
# =============================================================================

class TestPickFresh:
    """Tests for pick_fresh()."""

    def test_picks_unused_option(self):
        """Should pick an option not in recently_used."""
        options = ["a", "b", "c", "d"]
        recently_used = ["a", "b"]

        # Run multiple times to ensure it never picks a or b
        for _ in range(20):
            result = bot.pick_fresh(options, recently_used)
            assert result in ["c", "d"]

    def test_picks_random_when_all_used(self):
        """Should pick randomly when all options are used."""
        options = ["a", "b", "c"]
        recently_used = ["a", "b", "c"]

        result = bot.pick_fresh(options, recently_used)
        assert result in options

    def test_picks_from_full_list_when_none_used(self):
        """Should pick from full list when nothing used recently."""
        options = ["a", "b", "c"]
        recently_used = []

        result = bot.pick_fresh(options, recently_used)
        assert result in options


# =============================================================================
# TRUNCATE FOR EMBED TESTS
# =============================================================================

class TestTruncateForEmbed:
    """Tests for truncate_for_embed()."""

    def test_returns_short_text_unchanged(self):
        """Should return text unchanged if under limit."""
        text = "Short text"
        result = bot.truncate_for_embed(text, max_length=1024)
        assert result == text

    def test_truncates_long_text(self):
        """Should truncate text over limit with ellipsis."""
        text = "a" * 1100
        result = bot.truncate_for_embed(text, max_length=100)
        assert len(result) == 100
        assert result.endswith("...")

    def test_exact_limit_unchanged(self):
        """Should not truncate text exactly at limit."""
        text = "a" * 100
        result = bot.truncate_for_embed(text, max_length=100)
        assert result == text
        assert len(result) == 100


# =============================================================================
# BUILD CONTEXT BLOCK TESTS
# =============================================================================

class TestBuildContextBlock:
    """Tests for build_context_block()."""

    def test_returns_empty_when_no_recent_posts(self, empty_history):
        """Should return empty string when no recent posts."""
        result = bot.build_context_block(empty_history)
        assert result == ""

    def test_includes_recent_posts(self, sample_history):
        """Should include recent posts in context block."""
        result = bot.build_context_block(sample_history)
        assert "<recent_posts>" in result
        assert "</recent_posts>" in result
        assert "cosmology" in result  # 3-day-old post

    def test_limits_to_10_posts(self):
        """Should limit context to most recent 10 posts."""
        now = datetime.now(timezone.utc)
        history = {
            "posts": [
                {"date": now.isoformat(), "mode": "fact", "topic": f"topic_{i}", "summary": f"Summary {i}"}
                for i in range(15)
            ],
            "used_wonders": [],
            "used_topics": [],
        }
        result = bot.build_context_block(history)
        # Should only include posts 5-14 (last 10)
        assert "topic_14" in result
        assert "topic_5" in result
        assert "topic_4" not in result


# =============================================================================
# EMPTY HISTORY TESTS
# =============================================================================

class TestEmptyHistory:
    """Tests for _empty_history()."""

    def test_returns_correct_structure(self):
        """Should return dict with correct keys."""
        result = bot._empty_history()
        assert "posts" in result
        assert "used_wonders" in result
        assert "used_topics" in result
        assert result["posts"] == []
        assert result["used_wonders"] == []
        assert result["used_topics"] == []
