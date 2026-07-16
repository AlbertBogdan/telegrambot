# Nutribot — Telegram BJU Nutrition Tracker

Telegram bot for logging daily protein/fat/carb (Б/Ж/У) intake with automatic calorie compensation.

## Setup

```bash
uv sync
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | Telegram Bot API token from @BotFather |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase service role key |

## Running Locally

```bash
# Flask dev server
uv run python -m src.nutribot.api.webhook
```

Or with Vercel CLI:
```bash
vercel dev
```

## Setting the Telegram Webhook

```bash
curl "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=https://your-domain.vercel.app/api/webhook"
```

## Running Tests

```bash
uv run pytest -q
uv run ruff check .
uv run mypy src/
```

## Known Limitations

- Day rollover only creates a row for today; no multi-day backfill for missed days.
- Full month calendar only (no partial-week views).
- No product name capture — numbers only for logging.
- The worked UI example in the original spec ("Б: 5г, У: 30г, 1470/1740") is illustrative rather than exact; the compensation algorithm's own outputs are authoritative.
