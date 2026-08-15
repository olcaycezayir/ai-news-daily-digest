"""pipeline/filter.py — business-level filtering.

Maps to "Limit Google to 10" (n8n-nodes-base.limit) and "Create News Object"
(n8n-nodes-base.code). Pure transforms, no network calls.
"""
from __future__ import annotations

from typing import Any


def limit_top_n(items: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    """Keep only the first n items. Maps to "Limit Google to 10"
    (default keep=firstItems)."""
    return items[:n]


def filter_ai_relevant(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only items whose title contains 'AI' (case-sensitive substring
    match) — mirrors the original n8n Code node's `.includes('AI')` check."""
    return [item for item in items if item.get("title") and "AI" in item["title"]]


def build_news_object(
    google_items: list[dict[str, Any]], hacker_items: list[dict[str, Any]]
) -> dict[str, Any]:
    """Maps to "Create News Object". Returns {"googleNews": [...], "hackerNews": [...]}.

    DEVIATION FROM ORIGINAL (see docs/SPEC.md AÇIK SORU #1): the n8n Code
    node filtered BOTH output lists from the same merged input, so
    googleNews and hackerNews ended up identical — almost certainly a bug.
    Here each source list is filtered against itself. Revert to the
    original (buggy) behavior if strict n8n parity is required.
    """
    return {
        "googleNews": filter_ai_relevant(google_items),
        "hackerNews": filter_ai_relevant(hacker_items),
    }
