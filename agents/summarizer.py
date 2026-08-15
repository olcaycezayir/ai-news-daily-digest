"""agents/summarizer.py — write short summaries for curated articles.

Split out of the original "AI News Summarizer" n8n node's prompt
(docs/SPEC.md section 4.2). LLM call via llm_client (Anthropic).

NOTE: extends the SPEC.md 4.2 output schema with a "link" field per item
(carried through unchanged from curator output) so agents/editor.py can
score link coverage without re-fetching curator's output.
"""
from __future__ import annotations

import json
from typing import Any

from langfuse import get_client

from llm_client import call_json

SYSTEM_PROMPT = (
    "You are an AI news analyst. For each article below, write a short, "
    "professional summary of its key points/insights. Maintain a neutral, "
    "concise tone highlighting trends, debates, or important developments. "
    "Respond with JSON only, no prose, no markdown fences, matching exactly "
    "this schema:\n"
    '{"date": "...", '
    '"googleNews": [{"title": "...", "summary": "...", "link": "..."}], '
    '"hackerNews": [{"title": "...", "summary": "...", "link": "..."}]}\n'
    "Keep the same title and link for each article as given in the input; "
    "only add a summary."
)


def summarize(
    curated: dict[str, Any],
    *,
    api_key: str | None = None,
    dry_run: bool = False,
    timeout: float = 30.0,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Input: curator output (docs/SPEC.md 4.1 output).
    Output: {"date", "googleNews": [{title,summary,link}], "hackerNews": [...]}
    (docs/SPEC.md 4.2 output, extended with link). In --dry-run mode, no LLM
    call is made."""
    if dry_run:
        langfuse = get_client()
        with langfuse.start_as_current_observation(
            as_type="span", name="summarizer", input=curated, metadata={"dry_run": True}
        ) as span:
            result = _fake_output(curated)
            span.update(output=result)
        return result

    user_prompt = f"Curated articles:\n{json.dumps(curated, ensure_ascii=False)}"
    return call_json(
        api_key, SYSTEM_PROMPT, user_prompt, name="summarizer", timeout=timeout, max_retries=max_retries
    )


def _fake_output(curated: dict[str, Any]) -> dict[str, Any]:
    """--dry-run stand-in: placeholder summary text, no LLM call."""

    def _tag(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "title": item.get("title"),
                "summary": "(dry-run placeholder summary)",
                "link": item.get("link"),
            }
            for item in items
        ]

    return {
        "date": curated.get("date"),
        "googleNews": _tag(curated.get("googleNews", [])),
        "hackerNews": _tag(curated.get("hackerNews", [])),
    }
