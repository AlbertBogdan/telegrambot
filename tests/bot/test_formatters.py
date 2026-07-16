"""Tests for formatters.py — SKILL.md step 2.

Covers: "Сегодня" view renders exceeded-nutrient flags and exhaustion
message correctly for fixture data.
"""

from datetime import date

from nutribot.bot.formatters import (
    _fmt_grams,
    _fmt_kcal,
    format_day_detail,
    format_input_error,
    format_limit_exhausted,
    format_no_data,
    format_today,
)
from nutribot.domain.calculator import compensate, kcal
from nutribot.domain.models import DailyLog, MacroTotals, UserProfile

_JULY15 = date(2026, 7, 15)


class TestFormatToday:
    def test_no_overage(self):
        """Normal day — no exceeded flags, no exhaustion message."""
        profile = UserProfile(user_id=1, norm_b=120, norm_j=60, norm_u=250)
        log = DailyLog(
            user_id=1, date=_JULY15, totals=MacroTotals(b=40, j=20, u=100)
        )
        comp = compensate(
            profile.norm_b, profile.norm_j, profile.norm_u,
            log.totals.b, log.totals.j, log.totals.u,
        )
        output = format_today(profile, log, comp)
        assert "ПЕРЕБОР!" not in output
        assert "исчерпан" not in output
        assert "📈" in output
        assert "Б:" in output
        assert "Ж:" in output
        assert "У:" in output
        assert "Калории" in output

    def test_protein_exceeded_flag(self):
        """When protein is exceeded, (ПЕРЕБОР!) appears for Б."""
        profile = UserProfile(user_id=1, norm_b=120, norm_j=60, norm_u=250)
        log = DailyLog(
            user_id=1, date=_JULY15, totals=MacroTotals(b=130, j=20, u=100)
        )
        comp = compensate(
            profile.norm_b, profile.norm_j, profile.norm_u,
            log.totals.b, log.totals.j, log.totals.u,
        )
        output = format_today(profile, log, comp)
        assert "ПЕРЕБОР!" in output
        lines = output.split("\n")
        b_line = [ln for ln in lines if ln.startswith("Б:")][0]
        assert "ПЕРЕБОР!" in b_line

    def test_day_exhausted_message(self):
        """When day_exhausted is True, the exhaustion message appears."""
        profile = UserProfile(user_id=1, norm_b=120, norm_j=60, norm_u=250)
        log = DailyLog(
            user_id=1, date=_JULY15, totals=MacroTotals(b=130, j=70, u=260)
        )
        comp = compensate(
            profile.norm_b, profile.norm_j, profile.norm_u,
            log.totals.b, log.totals.j, log.totals.u,
        )
        output = format_today(profile, log, comp)
        assert comp.day_exhausted
        assert "исчерпан" in output

    def test_remaining_shown_for_non_exceeded(self):
        """Remaining grams are shown for non-exceeded nutrients."""
        profile = UserProfile(user_id=1, norm_b=120, norm_j=60, norm_u=250)
        log = DailyLog(
            user_id=1, date=_JULY15, totals=MacroTotals(b=40, j=20, u=100)
        )
        comp = compensate(
            profile.norm_b, profile.norm_j, profile.norm_u,
            log.totals.b, log.totals.j, log.totals.u,
        )
        output = format_today(profile, log, comp)
        assert "Осталось:" in output

    def test_calories_display(self):
        """Calories line shows kcal_fact/kcal_norm."""
        profile = UserProfile(user_id=1, norm_b=120, norm_j=60, norm_u=250)
        log = DailyLog(
            user_id=1, date=_JULY15, totals=MacroTotals(b=40, j=20, u=100)
        )
        comp = compensate(
            profile.norm_b, profile.norm_j, profile.norm_u,
            log.totals.b, log.totals.j, log.totals.u,
        )
        output = format_today(profile, log, comp)
        # kcal_fact=740, kcal_norm=2020
        assert "740" in output
        assert "2020" in output


class TestFormatDayDetail:
    def test_day_detail(self):
        log = DailyLog(
            user_id=1, date=_JULY15, totals=MacroTotals(b=50, j=30, u=120)
        )
        output = format_day_detail(log, kcal(log.totals))
        assert "2026-07-15" in output
        assert "Б:" in output
        assert "Ж:" in output
        assert "У:" in output


class TestFormatNoData:
    def test_no_data(self):
        output = format_no_data("2026-07-15")
        assert "2026-07-15" in output
        assert "Нет данных" in output


class TestFormatHelpers:
    def test_fmt_grams_whole(self):
        assert _fmt_grams(100.0) == "100г"

    def test_fmt_grams_decimal(self):
        assert _fmt_grams(7.5) == "7.5г"

    def test_fmt_kcal_whole(self):
        assert _fmt_kcal(2020.0) == "2020"

    def test_fmt_kcal_decimal(self):
        assert _fmt_kcal(123.4) == "123.4"


class TestFormatMessages:
    def test_input_error(self):
        output = format_input_error()
        assert "Неверный формат" in output
        assert "3 числа" in output
        assert "4 числа" in output

    def test_limit_exhausted(self):
        output = format_limit_exhausted()
        assert "Лимит" in output
        assert "исчерпан" in output
