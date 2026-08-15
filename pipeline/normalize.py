"""pipeline/normalize.py — reshape raw feed entries into a canonical schema.

No n8n node equivalent by itself; it's the schema-cleanup step implicitly
done by field access throughout the original workflow (title/link/pubDate
are read as-is from rssFeedRead output). Pure transform, no network calls.
"""
from __future__ import annotations

from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Any


def normalize_item(raw: dict[str, Any]) -> dict[str, Any]:
    """Reshape one raw feed entry into the canonical news-item schema:
    {source, title, link, pubDate (ISO-8601 UTC), content, id}."""
    return {
        "source": raw.get("source"),
        "title": (raw.get("title") or "").strip(),
        "link": raw.get("link"),
        "pubDate": _normalize_date(raw.get("pubDate")),
        "content": (raw.get("content") or "").strip() or None,
        "id": raw.get("id") or raw.get("link"),
    }


def normalize_items(raw_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [normalize_item(item) for item in raw_items]


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return value  # keep the raw string if it can't be parsed
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()
