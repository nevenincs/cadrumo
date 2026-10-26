"""Average-workforce conditions of two free-depreciation incentives.

LIS art. 102.1 admits free depreciation when the average total workforce of
the 24 months after the start of the tax period in which the assets enter
service exceeds that of the 12 months before it, and the increase is kept for
a further 24 months; the eligible investment is EUR 120,000 per unit of
increase, "calculado con dos decimales".  LIS DA 17a.1 conditions its free
depreciation on keeping the 24-month average at the prior 12-month level.
Workforce counts people employed as labour law defines them, weighted by
contracted hours against a full working day.

An IRPF tax period is the calendar year, so both windows are calendar years
around the entry year Y: Y-1 before, Y and Y+1 after, and Y+2 and Y+3 for the
art. 102 maintenance period.  The years come from the taxpayer profile's
validated ``irpf.plantilla_media`` instances.  A year not yet closed may be
declared as a commitment; it carries a regularisation duty (LIS art. 102.4,
DA 17a.7) that the evaluation reports rather than hides.
"""

from __future__ import annotations

import calendar
from decimal import ROUND_DOWN, Decimal

from pydantic import BaseModel

from ....core.models import STRICT_FROZEN_CONFIG
from ...user_profile.plantilla_media import PlantillaMediaState, PlantillaMediaYear
from .errors import ActividadAssetIncompleteError, ActividadAssetUnsupportedError

_TWO_PLACES = Decimal("0.01")


class WorkforceIncrease(BaseModel):
    """The LIS art. 102 increase, the declared years it rests on and those still committed."""

    model_config = STRICT_FROZEN_CONFIG

    increase: Decimal
    years: tuple[PlantillaMediaYear, ...]
    committed_years: tuple[int, ...]


class WorkforceMaintenance(BaseModel):
    """A met LIS DA 17a condition, the declared years it rests on and those still committed."""

    model_config = STRICT_FROZEN_CONFIG

    years: tuple[PlantillaMediaYear, ...]
    committed_years: tuple[int, ...]


def _require(years: tuple[PlantillaMediaYear, ...], year: int) -> PlantillaMediaYear:
    """Return a declared year, or refuse: an undeclared year is never zero."""
    found = next((item for item in years if item.year == year), None)
    if found is None:
        raise ActividadAssetIncompleteError(f"the average workforce of {year} is not declared")
    return found


def _window_average(years: tuple[PlantillaMediaYear, ...]) -> Decimal:
    """Average consecutive years weighted by their days, as one window would count them."""
    days = [Decimal(366 if calendar.isleap(item.year) else 365) for item in years]
    weighted = sum((item.average_workforce * day for item, day in zip(years, days, strict=True)), Decimal("0"))
    return weighted / sum(days, Decimal("0"))


def _committed(years: tuple[PlantillaMediaYear, ...]) -> tuple[int, ...]:
    return tuple(item.year for item in years if item.state is PlantillaMediaState.COMMITTED)


def job_creation_increase(years: tuple[PlantillaMediaYear, ...], *, entry_year: int) -> WorkforceIncrease:
    """Apply LIS art. 102.1 for assets entering service in ``entry_year``.

    The increase is truncated to two decimals, the reading of "calculado con
    dos decimales" that can never overstate the eligible investment.
    """
    before = _require(years, entry_year - 1)
    following = (_require(years, entry_year), _require(years, entry_year + 1))
    maintained = (_require(years, entry_year + 2), _require(years, entry_year + 3))
    increase = (_window_average(following) - before.average_workforce).quantize(_TWO_PLACES, rounding=ROUND_DOWN)
    if increase <= Decimal("0"):
        raise ActividadAssetUnsupportedError(
            "the average workforce of the 24 months after the entry year's start does not exceed that of the "
            "12 months before (LIS art. 102.1)",
        )
    if _window_average(maintained) - before.average_workforce < increase:
        raise ActividadAssetUnsupportedError(
            "the workforce increase is not kept for the further 24 months LIS art. 102.1 requires",
        )
    used = (before, *following, *maintained)
    return WorkforceIncrease(increase=increase, years=used, committed_years=_committed(used))


def renewable_workforce_maintained(
    years: tuple[PlantillaMediaYear, ...],
    *,
    entry_year: int,
) -> WorkforceMaintenance:
    """Apply LIS DA 17a.1: the 24-month average must not fall below the prior 12 months."""
    before = _require(years, entry_year - 1)
    following = (_require(years, entry_year), _require(years, entry_year + 1))
    if _window_average(following) < before.average_workforce:
        raise ActividadAssetUnsupportedError(
            "the average workforce of the 24 months after the entry year's start falls below that of the "
            "12 months before (LIS DA 17a.1)",
        )
    used = (before, *following)
    return WorkforceMaintenance(years=used, committed_years=_committed(used))


__all__ = [
    "WorkforceIncrease",
    "WorkforceMaintenance",
    "job_creation_increase",
    "renewable_workforce_maintained",
]
