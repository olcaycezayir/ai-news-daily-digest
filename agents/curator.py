"""agents/curator.py — select interesting/important AI articles.

Split out of the original "AI News Summarizer" n8n node's prompt
(docs/SPEC.md section 4.1). LLM call via llm_client (Anthropic).
"""
from __future__ import annotations

import json
from datetime import date as date_cls
from typing import Any

from langfuse import get_client

from llm_client import call_json

SYSTEM_PROMPT = (
    "You are an AI news analyst. From the given Google News and Hacker News "
    "articles, select only the ones that are interesting, important, or "
    "notable -- skip irrelevant or trivial items. Do not write summaries "
    "yet, only curate and order by importance. Respond with JSON only, no "
    "prose, no markdown fences, matching exactly this schema:\n"
    '{"date": "<ISO-8601 date, the most relevant date among the articles>", '
    '"googleNews": [{"title": "...", "link": "...", "pubDate": "...", "reason": "..."}], '
    '"hackerNews": [{"title": "...", "link": "...", "pubDate": "...", "reason": "..."}]}'
)


def curate(
    news_object: dict[str, Any],
    *,
    api_key: str | None = None,
    dry_run: bool = False,
    timeout: float = 30.0,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Input (docs/SPEC.md 4.1): {"googleNews": [...], "hackerNews": [...]}.
    Output (docs/SPEC.md 4.1): {"date", "googleNews": [{title,link,pubDate,reason}],
    "hackerNews": [...]}. In --dry-run mode, no LLM call is made."""
    if dry_run:
        # No LLM call in --dry-run: still record a span (not a generation --
        # no model was actually invoked) so the trace tree stays complete.
        langfuse = get_client()
        with langfuse.start_as_current_observation(
            as_type="span", name="curator", input=news_object, metadata={"dry_run": True}
        ) as span:
            result = _fake_output(news_object)
            span.update(output=result)
        return result

    user_prompt = f"Articles:\n{json.dumps(news_object, ensure_ascii=False)}"
    return call_json(
        api_key, SYSTEM_PROMPT, user_prompt, name="curator", timeout=timeout, max_retries=max_retries
    )


def _fake_output(news_object: dict[str, Any]) -> dict[str, Any]:
    """--dry-run stand-in: keep everything unfiltered, no LLM call."""
    today = date_cls.today().isoformat()

    def _tag(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "title": item.get("title"),
                "link": item.get("link"),
                "pubDate": item.get("pubDate"),
                "reason": "dry-run: unfiltered",
            }
            for item in items
        ]

    return {
        "date": today,
        "googleNews": _tag(news_object.get("googleNews", [])),
        "hackerNews": _tag(news_object.get("hackerNews", [])),
    }
