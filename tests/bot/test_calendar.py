"""Tests for calendar view — SKILL.md step 6.

Covers: empty-month render, marked vs unmarked days, tap-on-empty-day handling.
"""

from datetime import date

import pytest

from nutribot.bot.formatters import format_day_detail, format_no_data
from nutribot.bot.keyboards import calendar_keyboard
from nutribot.domain.calculator import kcal
from nutribot.domain.models import DailyLog, MacroTotals
from nutribot.storage.repository import InMemoryRepository

_JULY15 = date(2026, 7, 15)


class TestCalendarKeyboard:
    """Test the calendar inline keyboard builder."""

    def test_empty_month_all_unmarked(self):
        """Month with no entries → all days should be unmarked (no ● prefix)."""
        kb = calendar_keyboard(2026, 7, days_with_data=set())

        all_texts: list[str] = []
        for row in kb.keyboard:
            for btn in row:
                all_texts.append(btn.text)

        for text in all_texts:
            assert not text.startswith("●")

        assert any("Июль" in t for t in all_texts)

    def test_marked_days_have_dot(self):
        """Days with data should be prefixed with ●."""
        kb = calendar_keyboard(2026, 7, days_with_data={1, 15, 31})

        all_texts: list[str] = []
        for row in kb.keyboard:
            for btn in row:
                all_texts.append(btn.text)

        assert "●1" in all_texts
        assert "●15" in all_texts
        assert "2" in all_texts
        assert "●2" not in all_texts

    def test_navigation_buttons_present(self):
        """Calendar should have ◀ and ▶ navigation buttons."""
        kb = calendar_keyboard(2026, 7, days_with_data=set())

        all_texts: list[str] = []
        for row in kb.keyboard:
            for btn in row:
                all_texts.append(btn.text)

        assert "◀" in all_texts
        assert "▶" in all_texts

    def test_callback_data_for_navigation(self):
        """Navigation buttons should have cal_nav_ callback data."""
        kb = calendar_keyboard(2026, 7, days_with_data=set())

        nav_cb: list[str] = []
        for row in kb.keyboard:
            for btn in row:
                if btn.text in ("◀", "▶"):
                    nav_cb.append(btn.callback_data)

        for cb_data in nav_cb:
            assert cb_data.startswith("cal_nav_")

    def test_callback_data_for_days(self):
        """Day buttons should have cal_day_ callback data."""
        kb = calendar_keyboard(2026, 7, days_with_data={15})

        day_cb: list[str] = []
        for row in kb.keyboard:
            for btn in row:
                if btn.text.strip() and btn.callback_data:
                    if btn.callback_data.startswith("cal_day_"):
                        day_cb.append(btn.callback_data)

        assert len(day_cb) == 31

    def test_empty_cells_have_space(self):
        """Empty cells (days outside the month) should have a space."""
        kb = calendar_keyboard(2026, 7, days_with_data=set())

        for row in kb.keyboard:
            for btn in row:
                if btn.text.strip() == "" or btn.text == " ":
                    assert btn.callback_data == "cal_noop"

    def test_weekday_headers(self):
        """Calendar should have Russian weekday headers."""
        kb = calendar_keyboard(2026, 7, days_with_data=set())

        all_texts: list[str] = []
        for row in kb.keyboard:
            for btn in row:
                all_texts.append(btn.text)

        for day_name in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]:
            assert day_name in all_texts


class TestDayDetailDisplay:
    """Test the day detail formatter for calendar day taps."""

    def test_format_day_detail(self):
        log = DailyLog(
            user_id=1, date=_JULY15, totals=MacroTotals(b=50, j=30, u=120)
        )
        output = format_day_detail(log, kcal(log.totals))
        assert "2026-07-15" in output
        assert "Б:" in output
        assert "Ж:" in output
        assert "У:" in output
        assert "Калории" in output

    def test_format_no_data(self):
        output = format_no_data("2026-07-15")
        assert "2026-07-15" in output
        assert "Нет данных" in output


class TestCalendarDataFetching:
    """Test the InMemoryRepository get_logs_for_month for calendar rendering."""

    @pytest.mark.asyncio
    async def test_get_logs_for_month(self):
        repo = InMemoryRepository()

        await repo.upsert_log(111, date(2026, 7, 1), MacroTotals(b=10, j=5, u=20))
        await repo.upsert_log(111, date(2026, 7, 15), MacroTotals(b=30, j=15, u=60))
        await repo.upsert_log(111, date(2026, 7, 31), MacroTotals(b=50, j=25, u=100))

        logs = await repo.get_logs_for_month(111, 2026, 7)
        assert len(logs) == 3

        days_with_data = {log.date.day for log in logs}
        assert days_with_data == {1, 15, 31}

    @pytest.mark.asyncio
    async def test_empty_month_no_logs(self):
        repo = InMemoryRepository()
        logs = await repo.get_logs_for_month(111, 2026, 8)
        assert logs == []

    @pytest.mark.asyncio
    async def test_tap_empty_day_handling(self):
        repo = InMemoryRepository()

        await repo.upsert_log(111, date(2026, 7, 1), MacroTotals(b=10, j=5, u=20))

        log = await repo.get_log(111, date(2026, 7, 15))
        assert log is None

        output = format_no_data("2026-07-15")
        assert "Нет данных" in output

    @pytest.mark.asyncio
    async def test_other_user_data_not_visible(self):
        repo = InMemoryRepository()

        await repo.upsert_log(111, date(2026, 7, 1), MacroTotals(b=10, j=5, u=20))
        await repo.upsert_log(222, date(2026, 7, 1), MacroTotals(b=99, j=99, u=99))

        logs_111 = await repo.get_logs_for_month(111, 2026, 7)
        assert len(logs_111) == 1
        assert logs_111[0].totals.b == 10.0

        logs_222 = await repo.get_logs_for_month(222, 2026, 7)
        assert len(logs_222) == 1
        assert logs_222[0].totals.b == 99.0
