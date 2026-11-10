"""Pure-Python parsing for the unofficial Nourish today's-goals response.

Only the fields observed in the browser experiment are considered supported:
type, subType, goalAmount and goalProgress[0]. Progress objects are not fully
documented; we intentionally leave unknown formats as unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class Nutrient:
    """One nutrient's target and current progress, if numeric."""

    subtype: str
    goal: float | None
    progress: float | None


@dataclass(frozen=True)
class DailyGoals:
    """Data captured for a specific Home Assistant local date."""

    day: date
    nutrients: dict[str, Nutrient]
    fetched_at: datetime


def _number(value: Any) -> float | None:
    """Interpret finite numbers without coercing booleans or strings."""
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    number = float(value)
    return number if isfinite(number) else None


def _progress(value: Any) -> float | None:
    """Handle scalar progress and a few explicit amount-shaped objects."""
    if not isinstance(value, list) or not value:
        return None
    first = value[0]
    numeric = _number(first)
    if numeric is not None:
        return numeric
    if not isinstance(first, dict):
        return None
    for field in (
        "amount", "currentAmount", "progressAmount", "consumedAmount",
        "loggedAmount", "actualAmount", "totalAmount", "value",
    ):
        if field in first:
            return _number(first[field])
    return None


def parse_goals_response(raw: Any, day: date, fetched_at: datetime) -> DailyGoals:
    """Parse a response without inventing unknown nutrient progress values."""
    if not isinstance(raw, list):
        raise ValueError("The Nourish goals response was not a list")
    nutrients: dict[str, Nutrient] = {}
    for row in raw:
        if not isinstance(row, dict) or row.get("type") != "LOG_NUTRIENT":
            continue
        subtype = row.get("subType")
        if not isinstance(subtype, str) or not subtype.strip():
            continue
        # Preserve the API's label while giving it stable case-insensitive identity.
        key = subtype.strip().upper()
        nutrients[key] = Nutrient(
            subtype=key,
            goal=_number(row.get("goalAmount")),
            progress=_progress(row.get("goalProgress")),
        )
    return DailyGoals(day=day, nutrients=nutrients, fetched_at=fetched_at)
