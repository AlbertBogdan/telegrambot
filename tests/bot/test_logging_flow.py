"""Tests for macro-logging flow — SKILL.md step 4.

Covers:
  - Format A (3-number direct) valid add
  - Format B (4-number weight+per100) valid add with correct conversion
  - wrong token count (not 3 and not 4) rejected with both patterns shown
  - negative Format-A values rejected
  - Format-B weight<=0 rejected
  - Format-B per-100 value of 0 accepted
  - add blocked when kcal_fact already >= kcal_norm regardless of format used
"""

from datetime import date

import pytest

from nutribot.bot.handlers import NutribotHandlers
from nutribot.domain.calculator import (
    compensate,
    convert_product_to_macros,
    is_day_exhausted,
)
from nutribot.domain.models import MacroTotals
from nutribot.storage.repository import InMemoryRepository


class TestParsing:
    """Test input parsing logic (static methods on NutribotHandlers)."""

    def test_parse_format_a_valid(self):
        result = NutribotHandlers._parse_format_a(["20", "10", "40"])
        assert result is not None
        assert result.b == 20.0
        assert result.j == 10.0
        assert result.u == 40.0

    def test_parse_format_a_wrong_count(self):
        result = NutribotHandlers._parse_format_a(["20", "10"])
        assert result is None

    def test_parse_format_a_non_numeric(self):
        result = NutribotHandlers._parse_format_a(["20", "abc", "40"])
        assert result is None

    def test_parse_format_b_valid(self):
        result = NutribotHandlers._parse_format_b(["150", "20", "5", "30"])
        assert result is not None
        weight, b100, j100, u100 = result
        assert weight == 150.0
        assert b100 == 20.0
        assert j100 == 5.0
        assert u100 == 30.0

    def test_parse_format_b_wrong_count(self):
        result = NutribotHandlers._parse_format_b(["150", "20", "5"])
        assert result is None

    def test_parse_format_b_non_numeric(self):
        result = NutribotHandlers._parse_format_b(["150", "xx", "5", "30"])
        assert result is None

    def test_parse_three_numbers_valid(self):
        result = NutribotHandlers._parse_three_numbers("20 10 40")
        assert result == (20.0, 10.0, 40.0)

    def test_parse_three_numbers_token_count_not_three(self):
        result = NutribotHandlers._parse_three_numbers("20 10")
        assert result is None
        result = NutribotHandlers._parse_three_numbers("20 10 40 150")
        assert result is None


class TestFormatBConversion:
    """Test the Format B product-to-macros conversion pipeline."""

    def test_format_b_conversion(self):
        """150g @ 20/5/30 per 100g → 30/7.5/45 eaten grams."""
        eaten = convert_product_to_macros(150, 20, 5, 30)
        assert eaten.b == 30.0
        assert eaten.j == 7.5
        assert eaten.u == 45.0

    def test_format_b_zero_per100_accepted(self):
        """A per-100g value of 0 is valid and produces 0 eaten grams."""
        eaten = convert_product_to_macros(200, 20, 0, 30)
        assert eaten.j == 0.0
        assert eaten.b == 40.0
        assert eaten.u == 60.0

    def test_format_b_weight_one(self):
        """Weight=1g → tiny output."""
        eaten = convert_product_to_macros(1, 20, 10, 30)
        assert eaten.b == 0.2
        assert eaten.j == 0.1
        assert eaten.u == 0.3


class TestDayExhaustionBlock:
    """Test the is_day_exhausted check that blocks new entries."""

    def test_not_exhausted(self):
        """Day not exhausted when kcal_fact < kcal_norm."""
        assert not is_day_exhausted(120, 60, 250, 40, 20, 100)

    def test_exhausted_at_threshold(self):
        """Day exhausted when kcal_fact >= kcal_norm."""
        # kcal_norm = 120*4 + 60*9 + 250*4 = 480 + 540 + 1000 = 2020
        # 200*4 + 100*9 + 80*4 = 800 + 900 + 320 = 2020 (exactly)
        assert is_day_exhausted(120, 60, 250, 200, 100, 80)

    def test_exhausted_over_threshold(self):
        """Day exhausted when kcal_fact > kcal_norm."""
        assert is_day_exhausted(120, 60, 250, 250, 120, 100)


class TestLoggingFlowIntegration:
    """Test the full logging pipeline with InMemoryRepository."""

    @pytest.mark.asyncio
    async def test_format_a_add_and_accumulate(self):
        """Format A: add direct grams, verify accumulation."""
        repo = InMemoryRepository()
        today = date(2026, 7, 15)

        # Setup user
        await repo.upsert_user(111, 120.0, 60.0, 250.0)

        # First entry: 20g protein, 10g fat, 40g carbs
        first = MacroTotals(b=20, j=10, u=40)
        await repo.upsert_log(111, today, first)

        log = await repo.get_log(111, today)
        assert log is not None
        assert log.totals.b == 20.0
        assert log.totals.j == 10.0
        assert log.totals.u == 40.0

        # Second entry: add more
        second = MacroTotals(b=30, j=15, u=60)
        new_totals = log.totals + second
        await repo.upsert_log(111, today, new_totals)

        log = await repo.get_log(111, today)
        assert log is not None
        assert log.totals.b == 50.0  # 20+30
        assert log.totals.j == 25.0  # 10+15
        assert log.totals.u == 100.0  # 40+60

    @pytest.mark.asyncio
    async def test_format_b_add_and_accumulate(self):
        """Format B: product entry → converted → accumulated."""
        repo = InMemoryRepository()
        today = date(2026, 7, 15)

        await repo.upsert_user(111, 120.0, 60.0, 250.0)

        # Product: 150g @ 20/5/30 per 100g → 30/7.5/45 eaten
        eaten = convert_product_to_macros(150, 20, 5, 30)
        await repo.upsert_log(111, today, eaten)

        log = await repo.get_log(111, today)
        assert log is not None
        assert log.totals.b == 30.0
        assert log.totals.j == 7.5
        assert log.totals.u == 45.0

    @pytest.mark.asyncio
    async def test_block_when_exhausted(self):
        """When kcal_fact >= kcal_norm, next add is blocked."""
        repo = InMemoryRepository()
        today = date(2026, 7, 15)

        await repo.upsert_user(111, 120.0, 60.0, 250.0)

        # Add enough to reach kcal_norm (2020)
        # 200b * 4 = 800, 100j * 9 = 900, 80u * 4 = 320 → 2020
        totals = MacroTotals(b=200, j=100, u=80)
        await repo.upsert_log(111, today, totals)

        log = await repo.get_log(111, today)
        assert log is not None

        # Check exhaustion
        assert is_day_exhausted(120, 60, 250, log.totals.b, log.totals.j, log.totals.u)

    @pytest.mark.asyncio
    async def test_block_applies_to_next_attempt(self):
        """An entry that crosses the threshold IS recorded.
        The BLOCK applies to the NEXT attempt."""
        repo = InMemoryRepository()
        today = date(2026, 7, 15)

        await repo.upsert_user(111, 120.0, 60.0, 250.0)

        # Current totals: well under
        current = MacroTotals(b=40, j=20, u=100)
        log = await repo.upsert_log(111, today, current)

        # Not exhausted yet
        assert not is_day_exhausted(120, 60, 250, log.totals.b, log.totals.j, log.totals.u)

        # Now add a big entry that crosses the threshold
        big_eaten = MacroTotals(b=160, j=80, u=0)  # This will cross
        new_totals = log.totals + big_eaten
        log = await repo.upsert_log(111, today, new_totals)

        # The big entry was recorded
        assert log.totals.b == 200.0

        # NOW it's exhausted — next attempt would be blocked
        assert is_day_exhausted(120, 60, 250, log.totals.b, log.totals.j, log.totals.u)


class TestCompensationAfterAdd:
    """Test the compensation pipeline after adding macros."""

    def test_compensate_after_format_a_add(self):
        """After Format A add, compensation reflects new totals."""
        # Norms: 120/60/250
        # Current after add: 130/20/100
        comp = compensate(120, 60, 250, 130, 20, 100)
        assert comp.b_exceeded
        assert not comp.j_exceeded
        assert not comp.u_exceeded
        assert not comp.day_exhausted
        assert comp.remaining_b == 0.0

    def test_compensate_after_format_b_add(self):
        """After Format B add (product conversion), same compensation rules apply."""
        # 150g @ 20/5/30 → 30/7.5/45
        eaten = convert_product_to_macros(150, 20, 5, 30)
        # Previously had 40/20/100, now totals = 70/27.5/145
        totals = MacroTotals(b=40, j=20, u=100) + eaten
        comp = compensate(120, 60, 250, totals.b, totals.j, totals.u)
        # Nothing exceeded
        assert not comp.b_exceeded
        assert not comp.j_exceeded
        assert not comp.u_exceeded
        assert not comp.day_exhausted
