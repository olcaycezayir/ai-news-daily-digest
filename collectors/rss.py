"""collectors/rss.py — fetch and parse an RSS feed.

Maps to the "Google News AI" and "Hacker News AI" n8n nodes
(n8n-nodes-base.rssFeedRead). One generic function, called once per feed in
config.FEEDS, so each call is still one node-equivalent step.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import feedparser
import requests

from config import Feed

logger = logging.getLogger(__name__)


def fetch_feed(feed: Feed, timeout: float = 10.0, max_retries: int = 3) -> list[dict[str, Any]]:
    """Fetch + parse one RSS feed. Retries with exponential backoff on network
    failure or an unparsable response. Returns a JSON-serializable list of
    raw entry dicts (one dict per node.json item, n8n-style)."""
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(feed.url, timeout=timeout)
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
            if parsed.bozo and not parsed.entries:
                raise ValueError(f"unparsable feed response: {parsed.bozo_exception}")
            return [_entry_to_dict(entry, feed.name) for entry in parsed.entries]
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
            logger.warning(
                "fetch_feed(%s) attempt %d/%d failed: %s", feed.name, attempt, max_retries, exc
            )
            if attempt < max_retries:
                time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"fetch_feed({feed.name}) failed after {max_retries} attempts") from last_exc


def _entry_to_dict(entry: Any, source: str) -> dict[str, Any]:
    return {
        "source": source,
        "title": entry.get("title"),
        "link": entry.get("link"),
        "pubDate": entry.get("published") or entry.get("updated"),
        "content": entry.get("summary"),
        "id": entry.get("id") or entry.get("link"),
    }
