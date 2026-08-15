"""agents/editor.py — assemble the final Markdown digest + quality score.

Split out of the original "AI News Summarizer" n8n node's prompt
(docs/SPEC.md section 4.3). LLM call via llm_client (Anthropic) for
formatting; the 4000-char budget and quality score are enforced/computed
deterministically in Python afterwards (LLMs are unreliable at exact
counting, and count/link/length are objective, countable properties).
"""
from __future__ import annotations

import json
from typing import Any

from langfuse import get_client

from llm_client import call_json

MAX_CHARS = 4000

SYSTEM_PROMPT = (
    "You are an editor assembling a daily digest. Using the given summarized "
    "articles, produce a Markdown digest with EXACTLY this structure:\n"
    "# AI News Daily Digest – [date]\n\n"
    "## Google News\n"
    "## Hacker News\n\n"
    "Under each subheading, list articles as:\n"
    "- **Title:** [title]  \\n  **Summary:** [summary]\n\n"
    "Do not include any filler text before the heading. Keep the entire "
    "digest under 4000 characters -- if needed, drop the least important "
    "articles to stay under the limit. Respond with JSON only, no prose, no "
    'markdown fences: {"text": "<the full markdown digest>"}'
)


def edit(
    summarized: dict[str, Any],
    *,
    api_key: str | None = None,
    dry_run: bool = False,
    timeout: float = 30.0,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Input: summarizer output (docs/SPEC.md 4.2 output, extended with link).
    Output (docs/SPEC.md 4.3 output, extended with quality scoring):
    {"text", "char_count", "truncated", "quality_score", "quality_breakdown"}.
    In --dry-run mode, no LLM call is made; the digest is assembled with
    plain string formatting instead."""
    if dry_run:
        langfuse = get_client()
        with langfuse.start_as_current_observation(
            as_type="span", name="editor", input=summarized, metadata={"dry_run": True}
        ) as span:
            text = _fake_markdown(summarized)
            span.update(output={"text": text})
    else:
        user_prompt = f"Summarized articles:\n{json.dumps(summarized, ensure_ascii=False)}"
        result = call_json(
            api_key, SYSTEM_PROMPT, user_prompt, name="editor", timeout=timeout, max_retries=max_retries
        )
        text = result.get("text", "")

    text, truncated = _enforce_char_limit(text)
    quality_score, breakdown = _score_quality(summarized, text)

    return {
        "text": text,
        "char_count": len(text),
        "truncated": truncated,
        "quality_score": quality_score,
        "quality_breakdown": breakdown,
    }


def _fake_markdown(summarized: dict[str, Any]) -> str:
    """--dry-run stand-in: deterministic formatting, no LLM call."""
    lines = [f"# AI News Daily Digest – {summarized.get('date', '')}", ""]
    for heading, key in (("Google News", "googleNews"), ("Hacker News", "hackerNews")):
        lines.append(f"## {heading}")
        for item in summarized.get(key, []):
            lines.append(f"- **Title:** {item.get('title')}  ")
            lines.append(f"  **Summary:** {item.get('summary')}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _enforce_char_limit(text: str) -> tuple[str, bool]:
    """Ground-truth enforcement of the 4000-char budget."""
    if len(text) <= MAX_CHARS:
        return text, False
    return text[: MAX_CHARS - 1].rstrip() + "…", True


def _score_quality(summarized: dict[str, Any], text: str) -> tuple[float, dict[str, Any]]:
    """0-1 quality score from: article count, link coverage, length fit.
    Weights: 0.4 length + 0.3 count + 0.3 link coverage."""
    articles = summarized.get("googleNews", []) + summarized.get("hackerNews", [])
    article_count = len(articles)

    count_score = min(article_count / 10, 1.0)

    with_link = sum(1 for item in articles if item.get("link"))
    link_score = (with_link / article_count) if article_count else 0.0

    char_count = len(text)
    if char_count == 0 or char_count > MAX_CHARS:
        length_score = 0.0
    elif char_count < 200:
        length_score = char_count / 200
    else:
        length_score = 1.0

    quality_score = round(0.4 * length_score + 0.3 * count_score + 0.3 * link_score, 3)

    return quality_score, {
        "article_count": article_count,
        "count_score": round(count_score, 3),
        "link_coverage": round(link_score, 3),
        "length_score": round(length_score, 3),
        "char_count": char_count,
    }
