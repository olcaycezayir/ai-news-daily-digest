"""observability.py — Langfuse client bootstrap.

One client per process, built from .env config. After init_langfuse() runs
once (in runner.py), every other module reaches the same client via
`from langfuse import get_client`. Langfuse's OTel-based context makes any
start_as_current_observation() call nest under whatever span is currently
open, however deep in the call stack — so node modules (agents/, sinks/)
don't need a span/trace object threaded through their function signatures.
Maps to docs/SPEC.md section 5 (trace tree).
"""
from __future__ import annotations

from langfuse import Langfuse

from config import Config


def init_langfuse(config: Config) -> Langfuse:
    return Langfuse(
        public_key=config.langfuse_public_key,
        secret_key=config.langfuse_secret_key,
        base_url=config.langfuse_base_url,
    )
