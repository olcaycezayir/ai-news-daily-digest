"""tests/test_editor.py — unit tests for agents/editor.py's pure helpers.

Only tests _enforce_char_limit and _score_quality (no LLM/Langfuse call).
"""
from __future__ import annotations

from agents.editor import MAX_CHARS, _enforce_char_limit, _score_quality


def test_enforce_char_limit_leaves_short_text_untouched():
    text = "short digest"
    result, truncated = _enforce_char_limit(text)
    assert result == text
    assert truncated is False


def test_enforce_char_limit_truncates_long_text():
    text = "x" * (MAX_CHARS + 500)
    result, truncated = _enforce_char_limit(text)
    assert truncated is True
    assert len(result) == MAX_CHARS
    assert result.endswith("…")


def _summarized(google=None, hacker=None):
    return {"date": "2026-08-14", "googleNews": google or [], "hackerNews": hacker or []}


def test_score_quality_perfect_case():
    articles = [{"title": f"t{i}", "summary": "s", "link": "https://x.com"} for i in range(10)]
    summarized = _summarized(google=articles)
    score, breakdown = _score_quality(summarized, "x" * 1000)
    assert score == 1.0
    assert breakdown["article_count"] == 10
    assert breakdown["link_coverage"] == 1.0


def test_score_quality_zero_articles_scores_low():
    summarized = _summarized()
    score, breakdown = _score_quality(summarized, "x" * 1000)
    assert breakdown["article_count"] == 0
    assert breakdown["link_coverage"] == 0.0
    assert score < 0.5


def test_score_quality_missing_links_lowers_score():
    with_links = [{"title": "t", "summary": "s", "link": "https://x.com"}] * 10
    without_links = [{"title": "t", "summary": "s", "link": None}] * 10
    score_with, _ = _score_quality(_summarized(google=with_links), "x" * 1000)
    score_without, _ = _score_quality(_summarized(google=without_links), "x" * 1000)
    assert score_without < score_with


def test_score_quality_over_budget_text_scores_zero_length():
    articles = [{"title": "t", "summary": "s", "link": "https://x.com"}] * 10
    _, breakdown = _score_quality(_summarized(google=articles), "x" * (MAX_CHARS + 1))
    assert breakdown["length_score"] == 0.0
