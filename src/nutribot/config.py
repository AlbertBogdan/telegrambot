"""Configuration from environment variables."""

import os


def _require(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value


BOT_TOKEN = _require("BOT_TOKEN")
SUPABASE_URL = _require("SUPABASE_URL")
SUPABASE_KEY = _require("SUPABASE_KEY")
