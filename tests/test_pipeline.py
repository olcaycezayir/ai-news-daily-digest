"""tests/test_pipeline.py — unit tests for pipeline/filter.py and normalize.py.

Pure functions, no network/LLM/Langfuse involved.
"""
from __future__ import annotations

from pipeline.filter import build_news_object, filter_ai_relevant, limit_top_n
from pipeline.normalize import normalize_item


def _item(title: str, **overrides) -> dict:
    base = {"source": "google_news", "title": title, "link": "https://x.com", "pubDate": None, "content": None, "id": "1"}
    base.update(overrides)
    return base


def test_limit_top_n_keeps_first_n():
    items = [_item(f"t{i}") for i in range(15)]
    assert limit_top_n(items, 10) == items[:10]


def test_limit_top_n_shorter_than_n_returns_all():
    items = [_item("a"), _item("b")]
    assert limit_top_n(items, 10) == items


def test_filter_ai_relevant_keeps_only_ai_titles():
    items = [_item("New AI model released"), _item("Weather forecast today"), _item("ai lowercase doesn't count")]
    result = filter_ai_relevant(items)
    assert [i["title"] for i in result] == ["New AI model released"]


def test_filter_ai_relevant_skips_items_without_title():
    items = [{"title": None, "link": "x"}, _item("AI breakthrough")]
    result = filter_ai_relevant(items)
    assert len(result) == 1


def test_build_news_object_filters_each_source_independently():
    google_items = [_item("AI news 1"), _item("Sports news")]
    hacker_items = [_item("Not relevant"), _item("Show HN: AI tool")]
    result = build_news_object(google_items, hacker_items)
    assert [i["title"] for i in result["googleNews"]] == ["AI news 1"]
    assert [i["title"] for i in result["hackerNews"]] == ["Show HN: AI tool"]


def test_normalize_item_strips_whitespace_and_defaults():
    raw = {"source": "hacker_news", "title": "  AI Thing  ", "link": "https://x.com", "pubDate": None, "content": "  ", "id": None}
    result = normalize_item(raw)
    assert result["title"] == "AI Thing"
    assert result["content"] is None  # blank content collapses to None
    assert result["id"] == "https://x.com"  # falls back to link


def test_normalize_item_parses_rfc822_date_to_iso_utc():
    raw = {"title": "x", "pubDate": "Fri, 14 Aug 2026 09:02:24 GMT"}
    result = normalize_item(raw)
    assert result["pubDate"] == "2026-08-14T09:02:24+00:00"


def test_normalize_item_keeps_unparsable_date_as_is():
    raw = {"title": "x", "pubDate": "not-a-date"}
    result = normalize_item(raw)
    assert result["pubDate"] == "not-a-date"
