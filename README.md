# AI News Daily Digest

Python port of an n8n workflow ("AI News Daily Monitor" — see
`reference/n8n_workflow.json`) that fetches AI news from Google News and
Hacker News, curates/summarizes/edits it with Claude, and sends a daily
Markdown digest to Telegram. Every run is fully traced in Langfuse.

Full design doc: [`docs/SPEC.md`](docs/SPEC.md).

## Pipeline

```
fetch (Google News + Hacker News RSS)
  -> normalize -> filter (top 10 Google + "AI" in title)
  -> curator (LLM: pick the interesting articles)
  -> summarizer (LLM: write short summaries)
  -> editor (LLM: assemble Markdown + enforce 4000-char budget + quality score)
  -> sink (console or Telegram)
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # or requirements-dev.txt to also run tests
cp .env.example .env              # fill in your keys
```

Required `.env` keys: `ANTHROPIC_API_KEY`, `LANGFUSE_PUBLIC_KEY`,
`LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`. Needed only for the `telegram`
sink: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

## Usage

```bash
python runner.py --dry-run --sink console   # free: real RSS, fake LLM, no Telegram
python runner.py --sink console             # real LLM calls, prints to stdout
python runner.py --sink telegram            # real LLM calls + real Telegram send
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Deployment

`.github/workflows/daily-digest.yml` runs the pipeline on a schedule
(05:00 UTC = 08:00 Europe/Istanbul) via GitHub Actions, plus a manual
`workflow_dispatch` trigger. Configure these as repo secrets (Settings →
Secrets and variables → Actions): `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`,
`TELEGRAM_CHAT_ID`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`,
`LANGFUSE_BASE_URL` (must point at a reachable Langfuse instance, e.g.
`https://cloud.langfuse.com` — not `localhost`). `.github/workflows/ci.yml`
runs the test suite on every push/PR.
