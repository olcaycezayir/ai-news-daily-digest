"""sinks/console.py — print the digest to stdout.

Used with `--sink console`. No network call, always safe to run.
"""
from __future__ import annotations

from typing import Any


def send(payload: dict[str, Any]) -> dict[str, Any]:
    text = payload.get("text", "")
    print(text)
    return {"sink": "console", "ok": True, "chars_written": len(text)}
