"""Day-rollover logic using Europe/Minsk timezone.

The "day" boundary is 06:00 (not midnight). A request arriving
between 00:00 and 06:00 still belongs to the previous calendar date.
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

MINSK_TZ = ZoneInfo("Europe/Minsk")
ROLLOVER_HOUR = 6


def minsk_now(now: datetime | None = None) -> datetime:
    """Return the current time in Europe/Minsk."""
    if now is None:
        now = datetime.now()
    # If now is naive, assume it's UTC; if tz-aware, convert to Minsk.
    if now.tzinfo is None:

        now = now.replace(tzinfo=UTC)
    return now.astimezone(MINSK_TZ)


def minsk_today(now: datetime | None = None) -> date:
    """Return today's date according to the Minsk 06:00 rollover rule.

    If the current Minsk time is before 06:00, "today" is still the previous
    calendar date.
    """
    m = minsk_now(now)
    if m.hour < ROLLOVER_HOUR:
        # Still the previous calendar day
        return (m.date() - date.resolution)  # subtract 1 day  # type: ignore[operator]
    return m.date()


def needs_rollover(now: datetime | None, last_log_date: date | None) -> bool:
    """Determine whether a new daily_log row should be created.

    Args:
        now: Current datetime (or None for actual now). For test injection.
        last_log_date: The `date` of the most recent daily_log row for this user,
                       or None if the user has no logs yet.

    Returns:
        True if a fresh row for today is needed (past 06:00 Minsk and
        no row exists for today's Minsk date).
    """
    today = minsk_today(now)
    if last_log_date is None:
        return True
    return today > last_log_date
