"""Pure-function compensation calculator for Б/Ж/У nutrient tracking.

No I/O, no Telegram imports. All functions are referentially transparent.
"""

from dataclasses import dataclass

from nutribot.domain.models import MacroTotals

# kcal per gram for each macronutrient
KCAL_PER_G_B = 4.0
KCAL_PER_G_J = 9.0
KCAL_PER_G_U = 4.0


def kcal(m: MacroTotals) -> float:
    """Compute total kcal for a MacroTotals value."""
    return m.b * KCAL_PER_G_B + m.j * KCAL_PER_G_J + m.u * KCAL_PER_G_U


def convert_product_to_macros(
    weight_g: float,
    b_per_100: float,
    j_per_100: float,
    u_per_100: float,
) -> MacroTotals:
    """Convert a product entry (weight + per-100g values) to eaten grams.

    Precondition (enforced by caller): weight_g > 0 and b_per_100, j_per_100, u_per_100 >= 0.
    This function assumes valid input and does no validation.
    """
    factor = weight_g / 100.0
    return MacroTotals(
        b=b_per_100 * factor,
        j=j_per_100 * factor,
        u=u_per_100 * factor,
    )


@dataclass
class CompensationResult:
    """Output of the compensation calculator."""

    kcal_norm: float
    kcal_fact: float
    # Remaining grams per nutrient after compensation (never negative).
    remaining_b: float
    remaining_j: float
    remaining_u: float
    # Per-nutrient exceeded flag.
    b_exceeded: bool
    j_exceeded: bool
    u_exceeded: bool
    # True when budget_for_non_exceeded <= 0 — day is calorie-exhausted.
    day_exhausted: bool


def compensate(
    norm_b: float,
    norm_j: float,
    norm_u: float,
    fact_b: float,
    fact_j: float,
    fact_u: float,
) -> CompensationResult:
    """Compute compensated remaining grams for each nutrient.

    Algorithm per the documented spec:
      1. kcal_norm = norm_b*4 + norm_j*9 + norm_u*4
         kcal_fact = fact_b*4 + fact_j*9 + fact_u*4
      2. A nutrient is "exceeded" if fact_x > norm_x.
      3. excess_kcal = sum over exceeded of (fact_x - norm_x) * kcal_per_gram_x
      4. raw_remaining_kcal = sum over non-exceeded of (norm_x - fact_x) * kcal_per_gram_x
      5. budget_for_non_exceeded = raw_remaining_kcal - excess_kcal
      6. If budget_for_non_exceeded <= 0: all non-exceeded remaining = 0, day exhausted.
      7. Else: scale = budget_for_non_exceeded / raw_remaining_kcal;
         each non-exceeded remaining = (norm_x - fact_x) * scale.
    """
    kcal_norm = norm_b * KCAL_PER_G_B + norm_j * KCAL_PER_G_J + norm_u * KCAL_PER_G_U
    kcal_fact = fact_b * KCAL_PER_G_B + fact_j * KCAL_PER_G_J + fact_u * KCAL_PER_G_U

    b_exceeded = fact_b > norm_b
    j_exceeded = fact_j > norm_j
    u_exceeded = fact_u > norm_u

    # excess_kcal from exceeded nutrients
    excess_kcal = 0.0
    if b_exceeded:
        excess_kcal += (fact_b - norm_b) * KCAL_PER_G_B
    if j_exceeded:
        excess_kcal += (fact_j - norm_j) * KCAL_PER_G_J
    if u_exceeded:
        excess_kcal += (fact_u - norm_u) * KCAL_PER_G_U

    # raw_remaining_kcal from non-exceeded nutrients
    raw_remaining_kcal = 0.0
    if not b_exceeded:
        raw_remaining_kcal += (norm_b - fact_b) * KCAL_PER_G_B
    if not j_exceeded:
        raw_remaining_kcal += (norm_j - fact_j) * KCAL_PER_G_J
    if not u_exceeded:
        raw_remaining_kcal += (norm_u - fact_u) * KCAL_PER_G_U

    budget_for_non_exceeded = raw_remaining_kcal - excess_kcal

    if budget_for_non_exceeded <= 0:
        remaining_b = 0.0 if not b_exceeded else 0.0
        remaining_j = 0.0 if not j_exceeded else 0.0
        remaining_u = 0.0 if not u_exceeded else 0.0
        return CompensationResult(
            kcal_norm=kcal_norm,
            kcal_fact=kcal_fact,
            remaining_b=remaining_b,
            remaining_j=remaining_j,
            remaining_u=remaining_u,
            b_exceeded=b_exceeded,
            j_exceeded=j_exceeded,
            u_exceeded=u_exceeded,
            day_exhausted=True,
        )

    scale = budget_for_non_exceeded / raw_remaining_kcal

    def _remaining(exceeded: bool, norm: float, fact: float) -> float:
        if exceeded:
            return 0.0
        return (norm - fact) * scale

    return CompensationResult(
        kcal_norm=kcal_norm,
        kcal_fact=kcal_fact,
        remaining_b=_remaining(b_exceeded, norm_b, fact_b),
        remaining_j=_remaining(j_exceeded, norm_j, fact_j),
        remaining_u=_remaining(u_exceeded, norm_u, fact_u),
        b_exceeded=b_exceeded,
        j_exceeded=j_exceeded,
        u_exceeded=u_exceeded,
        day_exhausted=False,
    )


def is_day_exhausted(
    norm_b: float,
    norm_j: float,
    norm_u: float,
    fact_b: float,
    fact_j: float,
    fact_u: float,
) -> bool:
    """Check if the daily calorie budget is already exhausted.

    Returns True if kcal_fact >= kcal_norm, meaning the next logging
    attempt should be blocked.
    """
    kcal_norm = norm_b * KCAL_PER_G_B + norm_j * KCAL_PER_G_J + norm_u * KCAL_PER_G_U
    kcal_fact = fact_b * KCAL_PER_G_B + fact_j * KCAL_PER_G_J + fact_u * KCAL_PER_G_U
    return kcal_fact >= kcal_norm
