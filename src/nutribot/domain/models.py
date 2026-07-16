"""Domain models for nutribot."""

from dataclasses import dataclass, field
from datetime import date


@dataclass
class MacroTotals:
    """Protein (b), fat (j), carbs (u) in grams."""

    b: float = 0.0
    j: float = 0.0
    u: float = 0.0

    def __add__(self, other: "MacroTotals") -> "MacroTotals":
        return MacroTotals(
            b=self.b + other.b,
            j=self.j + other.j,
            u=self.u + other.u,
        )


@dataclass
class UserProfile:
    """Stored user profile with daily norms."""

    user_id: int
    norm_b: float
    norm_j: float
    norm_u: float
    onboarded: bool = True


@dataclass
class DailyLog:
    """A single day's accumulated intake."""

    user_id: int
    date: date  # noqa: A003 — shadowing built-in is intentional for the domain model
    totals: MacroTotals = field(default_factory=MacroTotals)
