"""
Unit tests for FeedFetcher._calculate_priority_score().
"""
import sys
import queue
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path for direct imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pytest
from feed_fetcher import FeedFetcher


def create_article(
    url="http://example.com/test",
    display_count=0,
    last_displayed_cycle=0,
    first_seen=None,
    category="Default",
):
    """Helper to create an article dict with sensible defaults."""
    return {
        'display_text': f"Test article for {url}",
        'url': url,
        'description': "Test description",
        'category': category,
        'first_seen': first_seen or datetime.now(),
        'display_count': display_count,
        'last_displayed_cycle': last_displayed_cycle,
    }


@pytest.fixture
def fetcher():
    """Create a FeedFetcher with a dummy queue."""
    return FeedFetcher(queue.Queue())


# ------------------------------------------------------------------ #
# Test new article scoring
# ------------------------------------------------------------------ #

class TestNewArticleScoring:
    """Fresh articles (display_count == 0) should get high scores."""

    def test_very_fresh_article(self, fetcher):
        """Articles < 30 minutes old get full NEW_ARTICLE_PRIORITY."""
        article = create_article(first_seen=datetime.now() - timedelta(minutes=10))
        score = fetcher._calculate_priority_score(article)
        assert score >= 90, f"Very fresh article should score high, got {score}"

    def test_recent_article(self, fetcher):
        """Articles < 2 hours old get 90% of priority."""
        article = create_article(first_seen=datetime.now() - timedelta(hours=1))
        score = fetcher._calculate_priority_score(article)
        assert 70 <= score <= 100, f"Recent article should score moderately high, got {score}"

    def test_older_unseen_article(self, fetcher):
        """Articles > 2 hours old but never shown get 70% of priority."""
        article = create_article(first_seen=datetime.now() - timedelta(hours=5))
        score = fetcher._calculate_priority_score(article)
        assert 50 <= score <= 80, f"Older unseen article should score medium-high, got {score}"

    def test_fresh_beats_old(self, fetcher):
        """A very fresh article should outscore a 5-hour-old unseen one."""
        fresh = create_article(url="http://a.com/1", first_seen=datetime.now() - timedelta(minutes=5))
        old = create_article(url="http://a.com/2", first_seen=datetime.now() - timedelta(hours=5))
        assert fetcher._calculate_priority_score(fresh) > fetcher._calculate_priority_score(old)


# ------------------------------------------------------------------ #
# Test cooldown scoring
# ------------------------------------------------------------------ #

class TestCooldownScoring:
    """Articles recently displayed should be in cooldown (score == 0)."""

    def test_article_in_cooldown_returns_zero(self, fetcher):
        """An article shown last cycle should have score 0."""
        fetcher.display_cycle_count = 10
        article = create_article(display_count=1, last_displayed_cycle=10)
        score = fetcher._calculate_priority_score(article)
        assert score == 0, f"Article in cooldown should score 0, got {score}"

    def test_article_just_inside_cooldown(self, fetcher):
        """An article shown 4 cycles ago (MIN_COOLDOWN=5) is still in cooldown."""
        fetcher.display_cycle_count = 10
        article = create_article(display_count=1, last_displayed_cycle=7)
        score = fetcher._calculate_priority_score(article)
        assert score == 0, f"Article at cycle boundary should score 0, got {score}"

    def test_article_at_cooldown_boundary(self, fetcher):
        """An article shown exactly MIN_COOLDOWN_CYCLES ago should have score > 0."""
        from config import MIN_COOLDOWN_CYCLES
        fetcher.display_cycle_count = 10
        article = create_article(display_count=1, last_displayed_cycle=10 - MIN_COOLDOWN_CYCLES)
        score = fetcher._calculate_priority_score(article)
        assert score > 0, f"Article past cooldown should score > 0, got {score}"


# ------------------------------------------------------------------ #
# Test recycled article scoring
# ------------------------------------------------------------------ #

class TestRecycledScoring:
    """Articles past cooldown get gradual priority recovery."""

    def test_longer_wait_higher_score(self, fetcher):
        """Articles that waited longer past cooldown should score higher."""
        fetcher.display_cycle_count = 30
        recent = create_article(url="http://a.com/1", display_count=1, last_displayed_cycle=22)
        old = create_article(url="http://a.com/2", display_count=1, last_displayed_cycle=10)
        score_recent = fetcher._calculate_priority_score(recent)
        score_old = fetcher._calculate_priority_score(old)
        assert score_old > score_recent, f"Longer-waited article should score higher: {score_old} vs {score_recent}"

    def test_recycled_has_minimum_score(self, fetcher):
        """Recycled articles should never drop below minimum priority."""
        fetcher.display_cycle_count = 100
        article = create_article(
            display_count=5,
            last_displayed_cycle=0,
            first_seen=datetime.now() - timedelta(hours=10)
        )
        score = fetcher._calculate_priority_score(article)
        assert score >= 5, f"Recycled article should have minimum score, got {score}"


# ------------------------------------------------------------------ #
# Test adaptive mode
# ------------------------------------------------------------------ #

class TestAdaptiveMode:
    """Adaptive mode reduces effective cooldown by 1."""

    def test_adaptive_reduces_cooldown(self, fetcher):
        """An article in cooldown normally but available in adaptive mode."""
        from config import MIN_COOLDOWN_CYCLES
        fetcher.display_cycle_count = 10
        # Show at cycle that puts it 1 less than normal cooldown
        article = create_article(
            display_count=1,
            last_displayed_cycle=10 - MIN_COOLDOWN_CYCLES + 1
        )
        normal_score = fetcher._calculate_priority_score(article, adaptive_mode=False)
        adaptive_score = fetcher._calculate_priority_score(article, adaptive_mode=True)
        assert normal_score == 0, "Should be in cooldown normally"
        assert adaptive_score > 0, "Should be available in adaptive mode"


# ------------------------------------------------------------------ #
# Test edge cases
# ------------------------------------------------------------------ #

class TestEdgeCases:
    """Edge cases for the scoring function."""

    def test_very_old_article(self, fetcher):
        """An article from days ago that was never shown should still score."""
        article = create_article(first_seen=datetime.now() - timedelta(days=3))
        score = fetcher._calculate_priority_score(article)
        assert score > 0, f"Very old unseen article should have positive score, got {score}"

    def test_zero_cycle_count(self, fetcher):
        """Scoring works when display_cycle_count is 0."""
        fetcher.display_cycle_count = 0
        article = create_article()
        score = fetcher._calculate_priority_score(article)
        assert score > 0, f"Score should work with cycle 0, got {score}"

    def test_article_shown_many_times(self, fetcher):
        """An article shown many times still gets a score after cooldown."""
        fetcher.display_cycle_count = 100
        article = create_article(display_count=20, last_displayed_cycle=50)
        score = fetcher._calculate_priority_score(article)
        assert score > 0, f"Heavily shown article past cooldown should still score, got {score}"
