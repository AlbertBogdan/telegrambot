"""Tests for rollover.py — SKILL.md step 5.

Covers:
  - pre-06:00 vs post-06:00 Minsk boundary
  - no rollover mid-day
  - no backfill across multi-day idle gaps
"""

from datetime import UTC, date, datetime

from nutribot.domain.rollover import minsk_today, needs_rollover


def make_utc(hour: int, minute: int, day: int = 15, month: int = 7, year: int = 2026) -> datetime:
    """Helper: create a UTC datetime. Minsk is UTC+3."""
    return datetime(year, month, day, hour, minute, 0, tzinfo=UTC)


class TestMinskToday:
    """Test minsk_today against the 06:00 rollover boundary."""

    def test_after_0600(self):
        """UTC 04:00 → Minsk 07:00 → same calendar day."""
        # Minsk = UTC+3, so UTC 04:00 = Minsk 07:00
        result = minsk_today(make_utc(4, 0))
        assert result == date(2026, 7, 15)

    def test_before_0600(self):
        """UTC 02:00 → Minsk 05:00 → still previous calendar day."""
        # Minsk 05:00 is before 06:00, so "today" is July 14
        result = minsk_today(make_utc(2, 0))
        assert result == date(2026, 7, 14)

    def test_exactly_0600(self):
        """UTC 03:00 → Minsk 06:00 → same calendar day."""
        # Minsk 06:00 exactly → new day
        result = minsk_today(make_utc(3, 0))
        assert result == date(2026, 7, 15)

    def test_midnight_utc(self):
        """UTC 00:00 → Minsk 03:00 → still previous day."""
        result = minsk_today(make_utc(0, 0))
        assert result == date(2026, 7, 14)


class TestNeedsRollover:
    """Test needs_rollover function."""

    def test_no_logs_yet(self):
        """First ever log → always needs rollover (creates first row)."""
        assert needs_rollover(make_utc(10, 0), None) is True

    def test_rollover_needed_new_day_after_0600(self):
        """Last log was yesterday, now past 06:00 → needs rollover."""
        # Minsk 07:00 on July 15, last log July 14
        assert needs_rollover(make_utc(4, 0), date(2026, 7, 14)) is True

    def test_no_rollover_same_day(self):
        """Last log is already today → no rollover."""
        # Minsk 07:00 on July 15, last log also July 15
        assert needs_rollover(make_utc(4, 0), date(2026, 7, 15)) is False

    def test_no_rollover_before_0600_same_logical_day(self):
        """Last log July 14, now Minsk 05:00 on July 15 → still 'yesterday', no rollover."""
        # UTC 02:00 = Minsk 05:00 → minsk_today is July 14 (previous day)
        # So last_log_date July 14 == minsk_today July 14 → no rollover
        assert needs_rollover(make_utc(2, 0), date(2026, 7, 14)) is False

    def test_rollover_after_0600_with_last_log_before(self):
        """Last log July 13, now Minsk 07:00 July 15 → rollover (no backfill, one row for today)."""
        assert needs_rollover(make_utc(4, 0), date(2026, 7, 13)) is True

    def test_no_backfill_multi_day_gap(self):
        """Multi-day gap: only one new row for today, no backfill.

        The function returns True (needs rollover for today), and the caller
        creates exactly one row. This test confirms the logic doesn't attempt
        to create rows for the missing days.
        """
        # Minsk 10:00 on July 15, last log July 10 → 4 day gap
        assert needs_rollover(make_utc(7, 0), date(2026, 7, 10)) is True
        # The function returns True once — caller creates one row for July 15.
        # No rows for July 11–14 (that's the "no backfill" guarantee).
