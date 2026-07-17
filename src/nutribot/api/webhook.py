"""Vercel serverless entrypoint for the Telegram bot webhook.

Exposes a Flask app that handles POST /api/webhook from Telegram.
Uses SupabaseRepository for persistence. The Telebot instance is
created once per cold start and reused across invocations.
"""

import logging
import sys

import telebot
from flask import Flask, request

from nutribot.bot.handlers import NutribotHandlers
from nutribot.config import BOT_TOKEN, SUPABASE_KEY, SUPABASE_URL
from nutribot.storage.repository import SupabaseRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Telebot instance (created once per cold start)
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# Repository (Supabase)
repo = SupabaseRepository(SUPABASE_URL, SUPABASE_KEY)

# Register handlers
handlers = NutribotHandlers(bot, repo)

# Register bot commands for the Telegram side panel (runs once per cold start)
try:
    bot.set_my_commands([
        telebot.types.BotCommand("/start", "Начать или перенастроить нормы БЖУ"),
        telebot.types.BotCommand("/help", "Как пользоваться ботом"),
    ])
except Exception:
    logger.exception("Failed to set bot commands")


@app.route("/api/webhook", methods=["POST"])
def webhook() -> tuple[str, int]:
    """Handle incoming Telegram webhook updates.

    Always returns 200 so Telegram doesn't retry, even on internal errors.
    Errors are logged to stderr for debugging.
    """
    try:
        json_data = request.get_json(force=True)
        update = telebot.types.Update.de_json(json_data)
        bot.process_new_updates([update])
    except Exception:
        logger.exception("Error processing webhook update")
    return "OK", 200


@app.route("/api/health", methods=["GET"])
def health() -> tuple[str, int]:
    """Health check endpoint."""
    return "OK", 200


# For local development: run Flask dev server
if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    app.run(host="0.0.0.0", port=port, debug=True)
