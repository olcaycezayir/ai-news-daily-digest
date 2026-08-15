"""runner.py — CLI entrypoint wiring the pipeline together.

Pipeline: fetch -> normalize -> filter -> curator -> summarizer -> editor -> sink.
In --dry-run mode: RSS fetches still run for real; curator/summarizer/editor
skip the Anthropic call and return fake data; the sink never calls Telegram
for real (docs/SPEC.md section 6).

Every run is one Langfuse trace ("ai-news-daily-digest"), with each pipeline
step as its own span/generation (docs/SPEC.md section 5).

Usage:
    python runner.py --dry-run --sink console
    python runner.py --sink telegram
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from typing import Any

from langfuse import propagate_attributes

from agents.curator import curate
from agents.editor import edit
from agents.summarizer import summarize
from collectors.rss import fetch_feed
from config import FEEDS, GOOGLE_NEWS_LIMIT, load_config
from observability import init_langfuse
from pipeline.filter import build_news_object, limit_top_n
from pipeline.normalize import normalize_items
from sinks import console as console_sink
from sinks import telegram as telegram_sink

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("runner")

QUALITY_SCORE_WARN_THRESHOLD = 0.5


def run(dry_run: bool, sink: str) -> dict[str, Any]:
    config = load_config()
    langfuse = init_langfuse(config)
    google_feed, hacker_feed = FEEDS
    run_date = date.today().isoformat()

    with langfuse.start_as_current_observation(
        as_type="span",
        name="ai-news-daily-digest",
        input={"dry_run": dry_run, "sink": sink},
    ) as root:
        with propagate_attributes(
            trace_name="ai-news-daily-digest",
            metadata={"dry_run": dry_run, "sink": sink, "run_date": run_date},
        ):
            # RSS fetches always run for real, even in --dry-run (docs/SPEC.md
            # section 6: only LLM and Telegram calls are skipped in dry-run).
            with root.start_as_current_observation(
                as_type="span", name="fetch_google_news", input={"url": google_feed.url}
            ) as sp:
                raw_google = fetch_feed(
                    google_feed, timeout=config.http_timeout_seconds, max_retries=config.http_max_retries
                )
                sp.update(output={"item_count": len(raw_google)})

            with root.start_as_current_observation(
                as_type="span", name="fetch_hacker_news", input={"url": hacker_feed.url}
            ) as sp:
                raw_hacker = fetch_feed(
                    hacker_feed, timeout=config.http_timeout_seconds, max_retries=config.http_max_retries
                )
                sp.update(output={"item_count": len(raw_hacker)})

            with root.start_as_current_observation(
                as_type="span",
                name="limit_google_news",
                input={"raw_count": len(raw_google), "limit": GOOGLE_NEWS_LIMIT},
            ) as sp:
                google_items = limit_top_n(normalize_items(raw_google), GOOGLE_NEWS_LIMIT)
                sp.update(output={"item_count": len(google_items)})

            hacker_items = normalize_items(raw_hacker)

            with root.start_as_current_observation(
                as_type="span",
                name="create_news_object",
                input={"google_count": len(google_items), "hacker_count": len(hacker_items)},
            ) as sp:
                news_object = build_news_object(google_items, hacker_items)
                sp.update(
                    output={
                        "google_count": len(news_object["googleNews"]),
                        "hacker_count": len(news_object["hackerNews"]),
                    }
                )

            # curator / summarizer / editor each record their own
            # generation (real) or span (--dry-run) observation internally
            # (see agents/*.py and llm_client.py) -- no wrapping needed here.
            llm_kwargs = dict(
                api_key=config.anthropic_api_key,
                dry_run=dry_run,
                timeout=config.llm_timeout_seconds,
                max_retries=config.llm_max_retries,
            )
            curated = curate(news_object, **llm_kwargs)
            summarized = summarize(curated, **llm_kwargs)
            digest = edit(summarized, **llm_kwargs)

            # Quality gate: doesn't block sending (a flawed digest still beats
            # a silent gap in the daily run) but makes low-quality runs
            # visible in logs + Langfuse metadata instead of passing quietly.
            if digest["quality_score"] < QUALITY_SCORE_WARN_THRESHOLD:
                logger.warning(
                    "digest quality_score %.2f is below threshold %.2f: %s",
                    digest["quality_score"],
                    QUALITY_SCORE_WARN_THRESHOLD,
                    digest["quality_breakdown"],
                )

            sink_name = f"send_{sink}"
            with root.start_as_current_observation(
                as_type="span", name=sink_name, input={"char_count": digest["char_count"]}
            ) as sp:
                if sink == "console":
                    sink_result = console_sink.send(digest)
                elif sink == "telegram":
                    if dry_run:
                        logger.info("dry-run: skipping real Telegram call. Digest:\n%s", digest["text"])
                        sink_result = {"sink": "telegram", "ok": True, "dry_run": True}
                    else:
                        sink_result = telegram_sink.send(
                            digest,
                            bot_token=config.telegram_bot_token,
                            chat_id=config.telegram_chat_id,
                            timeout=config.http_timeout_seconds,
                            max_retries=config.http_max_retries,
                        )
                else:
                    raise ValueError(f"unknown sink: {sink}")
                sp.update(output=sink_result)

            root.update(output={"digest": digest, "sink_result": sink_result})

    langfuse.flush()

    return {
        "news_object": news_object,
        "curated": curated,
        "summarized": summarized,
        "digest": digest,
        "sink_result": sink_result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="AI News Daily Digest runner.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip real Anthropic + Telegram calls (fake data used instead).",
    )
    parser.add_argument("--sink", choices=["console", "telegram"], default="console")
    args = parser.parse_args()

    result = run(dry_run=args.dry_run, sink=args.sink)
    logger.info(
        "run complete: %s",
        json.dumps(
            {
                "sink": args.sink,
                "dry_run": args.dry_run,
                "quality_score": result["digest"]["quality_score"],
                "char_count": result["digest"]["char_count"],
                "sink_result": result["sink_result"],
            }
        ),
    )


if __name__ == "__main__":
    main()
