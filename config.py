"""config.py — environment configuration and feed list.

Maps to no single n8n node; it's shared config consumed by the nodes that
need credentials or the RSS feed list (Google News AI, Hacker News AI,
Limit Google to 10, Send to Telegram). See docs/SPEC.md section 3.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)


@dataclass(frozen=True)
class Feed:
    name: str
    url: str


# Mirrors "Google News AI" and "Hacker News AI" node URLs, verbatim from
# reference/n8n_workflow.json.
FEEDS: tuple[Feed, Feed] = (
    Feed(
        name="google_news",
        url=(
            "https://news.google.com/rss/topics/"
            "CAAqIAgKIhpDQkFTRFFvSEwyMHZNRzFyZWhJQ1pXNG9BQVAB"
            "?hl=en-US&gl=US&ceid=US:en"
        ),
    ),
    Feed(name="hacker_news", url="https://hnrss.org/newest?q=ai&points=10&count=10"),
)

# Mirrors the "Limit Google to 10" node's maxItems parameter.
GOOGLE_NEWS_LIMIT = 10


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    anthropic_api_key: str | None
    langfuse_public_key: str | None
    langfuse_secret_key: str | None
    langfuse_base_url: str | None
    http_timeout_seconds: float
    http_max_retries: int
    llm_timeout_seconds: float
    llm_max_retries: int


def load_config() -> Config:
    return Config(
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        langfuse_public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
        langfuse_secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
        langfuse_base_url=os.environ.get("LANGFUSE_BASE_URL"),
        http_timeout_seconds=float(os.environ.get("HTTP_TIMEOUT_SECONDS", "10")),
        http_max_retries=int(os.environ.get("HTTP_MAX_RETRIES", "3")),
        # LLM generations are much slower than RSS/Telegram calls, so they get
        # their own, more generous timeout instead of reusing http_timeout_seconds.
        # Measured: curating ~18 articles takes ~60s real wall-clock time, so
        # 60s left no safety margin and timed out consistently — 120s instead.
        llm_timeout_seconds=float(os.environ.get("LLM_TIMEOUT_SECONDS", "120")),
        llm_max_retries=int(os.environ.get("LLM_MAX_RETRIES", "3")),
    )
