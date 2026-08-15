"""sinks/telegram.py — send the digest via the Telegram Bot API.

Maps to the "Send to Telegram" n8n node (n8n-nodes-base.telegram). Used with
`--sink telegram` and NOT called at all when --dry-run is set (runner.py
short-circuits before this module is invoked; see docs/SPEC.md section 6).
"""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send(
    payload: dict[str, Any],
    bot_token: str | None,
    chat_id: str | None,
    timeout: float = 10.0,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Send payload['text'] to a Telegram chat, prefixed exactly like the
    original node's text field. Retries with exponential backoff."""
    if not bot_token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not configured in .env")

    text = f"🤖 AI News Daily Digest\n\n{payload.get('text', '')}"
    url = TELEGRAM_API_URL.format(token=bot_token)
    body = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}

    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, json=body, timeout=timeout)
            response.raise_for_status()
            return {"sink": "telegram", "ok": True, "response": response.json()}
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning("telegram send attempt %d/%d failed: %s", attempt, max_retries, exc)
            if attempt < max_retries:
                time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"telegram send failed after {max_retries} attempts") from last_exc
