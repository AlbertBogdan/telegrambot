"""Vercel serverless entrypoint — imports the Flask app from nutribot."""

from nutribot.api.webhook import app  # noqa: F401
