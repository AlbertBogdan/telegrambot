"""Tests for calculator.py — SKILL.md step 1.

Covers:
  - no-overage case
  - single-nutrient overage
  - two-nutrient overage (carbs absorbs, per confirmed rule)
  - three-nutrient overage (fully blocked)
  - zero-remaining edge
  - convert_product_to_macros() — normal weight, weight=1,
    a per-100g value of 0, and factor scaling correctness
    (e.g. 150g @ 20/5/30 per 100g → 30/7.5/45 eaten grams).
"""


import pytest

from nutribot.domain.calculator import (
    compensate,
    convert_product_to_macros,
    is_day_exhausted,
    kcal,
)
from nutribot.domain.models import MacroTotals

# --- kcal ---

def test_kcal_zero():
    assert kcal(MacroTotals(0, 0, 0)) == 0.0


def test_kcal_basic():
    # 100g protein, 50g fat, 200g carbs
    # = 100*4 + 50*9 + 200*4 = 400 + 450 + 800 = 1650
    assert kcal(MacroTotals(100, 50, 200)) == 1650.0


# --- convert_product_to_macros ---

def test_convert_normal_weight():
    """150g @ 20/5/30 per 100g → 30/7.5/45 eaten grams."""
    result = convert_product_to_macros(150, 20, 5, 30)
    assert result.b == 30.0
    assert result.j == 7.5
    assert result.u == 45.0


def test_convert_weight_one():
    """weight=1 → factor=0.01, very small output."""
    result = convert_product_to_macros(1, 20, 10, 30)
    assert result.b == 0.2
    assert result.j == 0.1
    assert result.u == 0.3


def test_convert_per100_zero():
    """A per-100g value of 0 → eaten grams for that nutrient is 0."""
    result = convert_product_to_macros(200, 20, 0, 30)
    assert result.b == 40.0
    assert result.j == 0.0
    assert result.u == 60.0


def test_convert_factor_scaling():
    """Verify factor scaling: 250g of 10/8/40 per 100g → 25/20/100."""
    result = convert_product_to_macros(250, 10, 8, 40)
    assert result.b == 25.0
    assert result.j == 20.0
    assert result.u == 100.0


# --- compensate: no overage ---

def test_compensate_no_overage():
    """When nothing is exceeded, remaining = norm - fact unchanged."""
    result = compensate(
        norm_b=120, norm_j=60, norm_u=250,
        fact_b=40, fact_j=20, fact_u=100,
    )
    assert not result.b_exceeded
    assert not result.j_exceeded
    assert not result.u_exceeded
    assert not result.day_exhausted

    # kcal_norm = 120*4 + 60*9 + 250*4 = 480 + 540 + 1000 = 2020
    assert result.kcal_norm == 2020.0
    # kcal_fact = 40*4 + 20*9 + 100*4 = 160 + 180 + 400 = 740
    assert result.kcal_fact == 740.0

    # No overage → scale should be 1.0, remaining = raw difference
    assert result.remaining_b == pytest.approx(80.0)  # 120 - 40
    assert result.remaining_j == pytest.approx(40.0)  # 60 - 20
    assert result.remaining_u == pytest.approx(150.0)  # 250 - 100


# --- compensate: single-nutrient overage ---

def test_compensate_single_overage_protein():
    """Protein exceeded → its excess kcal is subtracted from fat+carbs budget."""
    result = compensate(
        norm_b=120, norm_j=60, norm_u=250,
        fact_b=130, fact_j=20, fact_u=100,  # protein 10g over
    )
    assert result.b_exceeded
    assert not result.j_exceeded
    assert not result.u_exceeded
    assert not result.day_exhausted

    # excess_kcal = (130-120)*4 = 40 kcal
    # raw_remaining_kcal from non-exceeded = (60-20)*9 + (250-100)*4 = 360 + 600 = 960
    # budget = 960 - 40 = 920
    # scale = 920 / 960 = 0.95833...
    # remaining_j = (60-20) * scale = 40 * 0.95833... ≈ 38.333
    # remaining_u = (250-100) * scale = 150 * 0.95833... ≈ 143.75
    assert result.remaining_b == 0.0  # exceeded
    assert result.remaining_j == pytest.approx(40 * 920 / 960)
    assert result.remaining_u == pytest.approx(150 * 920 / 960)


def test_compensate_single_overage_fat():
    """Fat exceeded → its excess kcal is subtracted from protein+carbs budget."""
    result = compensate(
        norm_b=120, norm_j=60, norm_u=250,
        fact_b=40, fact_j=70, fact_u=100,  # fat 10g over
    )
    assert not result.b_exceeded
    assert result.j_exceeded
    assert not result.u_exceeded
    assert not result.day_exhausted

    # excess_kcal = (70-60)*9 = 90 kcal
    # raw_remaining = (120-40)*4 + (250-100)*4 = 320 + 600 = 920
    # budget = 920 - 90 = 830
    # scale = 830 / 920
    assert result.remaining_j == 0.0  # exceeded
    assert result.remaining_b == pytest.approx(80 * 830 / 920)
    assert result.remaining_u == pytest.approx(150 * 830 / 920)


# --- compensate: two-nutrient overage ---

def test_compensate_two_overage_carbs_absorbs():
    """Two nutrients exceeded (protein + fat), carbs absorbs 100% of compensation.

    Confirmed rule: when two nutrients are exceeded simultaneously,
    the single remaining non-exceeded nutrient absorbs 100% of the compensation.
    """
    result = compensate(
        norm_b=120, norm_j=60, norm_u=250,
        fact_b=130, fact_j=70, fact_u=100,  # protein 10g over, fat 10g over
    )
    assert result.b_exceeded
    assert result.j_exceeded
    assert not result.u_exceeded
    assert not result.day_exhausted

    # excess_kcal = (130-120)*4 + (70-60)*9 = 40 + 90 = 130
    # raw_remaining from carbs only = (250-100)*4 = 600
    # budget = 600 - 130 = 470
    # scale = 470 / 600 = 0.78333...
    # remaining_u = 150 * 470/600 = 117.5
    assert result.remaining_b == 0.0
    assert result.remaining_j == 0.0
    assert result.remaining_u == pytest.approx(150 * 470 / 600)


# --- compensate: three-nutrient overage ---

def test_compensate_three_overage_blocked():
    """All three nutrients exceeded → fully blocked, day_exhausted=True."""
    result = compensate(
        norm_b=120, norm_j=60, norm_u=250,
        fact_b=130, fact_j=70, fact_u=260,  # all over
    )
    assert result.b_exceeded
    assert result.j_exceeded
    assert result.u_exceeded
    assert result.day_exhausted

    # All remaining should be 0
    assert result.remaining_b == 0.0
    assert result.remaining_j == 0.0
    assert result.remaining_u == 0.0


# --- compensate: zero-remaining edge case ---

def test_compensate_excess_equals_remaining():
    """Excess kcal exactly equals raw_remaining_kcal → budget=0, day_exhausted."""
    # Set up so excess_kcal == raw_remaining_kcal
    # norm: 120/60/250, fact: 130/60/250 — protein 10g over = 40kcal excess
    # This leaves fat at exactly norm and carbs under norm
    # raw_remaining from fat=0, from carbs=(250-200)*4=200
    # Oh wait, let me construct a cleaner case.

    # Protein 10g over = 40 kcal excess
    # Fat at norm = 0 remaining
    # Carbs under by 10g = 40 kcal raw_remaining
    # budget = 40 - 40 = 0 → exhausted
    result = compensate(
        norm_b=120, norm_j=60, norm_u=250,
        fact_b=130, fact_j=60, fact_u=240,
    )
    assert result.b_exceeded
    assert not result.j_exceeded  # exactly at norm — "fact_x > norm_x" is False
    assert not result.u_exceeded
    assert result.day_exhausted

    assert result.remaining_b == 0.0
    assert result.remaining_j == 0.0
    assert result.remaining_u == 0.0


def test_compensate_excess_exceeds_remaining():
    """Excess kcal > raw_remaining_kcal → budget negative, day_exhausted."""
    result = compensate(
        norm_b=120, norm_j=60, norm_u=250,
        fact_b=140, fact_j=60, fact_u=240,  # protein 20g over = 80kcal, carbs under 10g = 40kcal
    )
    assert result.b_exceeded
    assert result.day_exhausted
    assert result.remaining_b == 0.0
    assert result.remaining_j == 0.0
    assert result.remaining_u == 0.0


# --- is_day_exhausted ---

def test_is_day_exhausted_false():
    """Day not exhausted when kcal_fact < kcal_norm."""
    assert not is_day_exhausted(120, 60, 250, 40, 20, 100)


def test_is_day_exhausted_true():
    """Day exhausted when kcal_fact >= kcal_norm."""
    # kcal_norm = 120*4 + 60*9 + 250*4 = 480 + 540 + 1000 = 2020
    # Need kcal_fact >= 2020
    # 200*4 + 100*9 + 50*4 = 800 + 900 + 200 = 1900 (not enough)
    # 200*4 + 100*9 + 80*4 = 800 + 900 + 320 = 2020 (exactly)
    assert is_day_exhausted(120, 60, 250, 200, 100, 80)


def test_is_day_exhausted_over():
    """Day exhausted when kcal_fact > kcal_norm."""
    assert is_day_exhausted(120, 60, 250, 250, 120, 100)


# --- MacroTotals addition ---

def test_macro_totals_add():
    a = MacroTotals(10, 20, 30)
    b = MacroTotals(5, 3, 7)
    c = a + b
    assert c.b == 15.0
    assert c.j == 23.0
    assert c.u == 37.0
