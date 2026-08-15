"""llm_client.py — thin Anthropic Messages API wrapper with retry + timeout.

Maps to the "OpenAI Chat Model" n8n node's role: provides the LLM connection
used by agents/curator.py, agents/summarizer.py, agents/editor.py.
CLAUDE.md mandates Anthropic (claude-sonnet-4-6) over the original OpenAI
gpt-4.1-mini.

Each call is wrapped in a Langfuse "generation" observation (docs/SPEC.md
section 5) — nests automatically under whatever span/trace is currently open
in the calling process (see observability.py).
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import anthropic
import json_repair
from langfuse import get_client

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"


def call_json(
    api_key: str | None,
    system: str,
    user: str,
    *,
    name: str = "llm-call",
    max_tokens: int = 4096,
    timeout: float = 120.0,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Call the Anthropic Messages API and parse the reply as JSON.
    Retries with exponential backoff on transient failures. Records a single
    Langfuse generation observation (named `name`) covering all attempts."""
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured in .env")

    langfuse = get_client()
    # max_retries=0 on the SDK client: its own internal retry would otherwise
    # stack with our retry loop below, multiplying wait time on every failure.
    client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=0)

    with langfuse.start_as_current_observation(
        as_type="generation",
        name=name,
        model=MODEL,
        input={"system": system, "user": user},
    ) as generation:
        last_exc: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                raw_text = "".join(
                    block.text for block in response.content if getattr(block, "type", None) == "text"
                )
                parsed = _extract_json(raw_text)
                generation.update(
                    output=parsed,
                    usage_details={
                        "input": response.usage.input_tokens,
                        "output": response.usage.output_tokens,
                    },
                    metadata={"stop_reason": response.stop_reason, "attempts": attempt},
                )
                return parsed
            except (anthropic.APIError, ValueError) as exc:
                last_exc = exc
                logger.warning(
                    "llm_client.call_json(%s) attempt %d/%d failed: %s", name, attempt, max_retries, exc
                )
                if attempt < max_retries:
                    time.sleep(2 ** (attempt - 1))

        generation.update(
            output=None,
            metadata={"error": str(last_exc), "attempts": max_retries, "failed": True},
        )
        raise RuntimeError(f"llm_client.call_json({name}) failed after {max_retries} attempts") from last_exc


def _extract_json(text: str) -> dict[str, Any]:
    """Strip markdown code fences if the model added them, then parse JSON.
    Falls back to a tolerant repair pass (json_repair) for almost-valid JSON
    -- e.g. a stray unescaped quote inside a title -- before giving up. This
    is deterministic and cheaper than a blind retry, which reproduces the
    same malformed output for the same input often enough to matter."""
    stripped = text.strip()
    match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.DOTALL)
    candidate = match.group(1) if match else stripped
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    try:
        repaired = json_repair.loads(candidate)
    except Exception as exc:
        raise ValueError(f"LLM response was not valid JSON: {text[:300]!r}") from exc
    if not isinstance(repaired, dict):
        raise ValueError(f"repaired JSON was not an object ({type(repaired).__name__}): {text[:300]!r}")
    return repaired
