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
art. 102 maintenance period.  A year not yet closed may be declared as a
commitment; it carries a regularisation duty (LIS art. 102.4, DA 17a.7) that
the evaluation reports rather than hides.
"""

from __future__ import annotations

import calendar
from decimal import ROUND_DOWN, Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.models import STRICT_FROZEN_CONFIG
from .errors import ActividadAssetIncompleteError, ActividadAssetUnsupportedError

_TWO_PLACES = Decimal("0.01")


class WorkforceYearState(StrEnum):
    """Whether a calendar year's average is observed or still a commitment."""

    OBSERVED = "observed"
    COMMITTED = "committed"


class AverageWorkforceYear(BaseModel):
    """One calendar year's average total workforce, to two decimal places."""

    model_config = STRICT_FROZEN_CONFIG

    year: int = Field(ge=2000, le=2100)
    average_workforce: Decimal
    state: WorkforceYearState

    @field_validator("average_workforce")
    @classmethod
    def _require_two_place_non_negative(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < Decimal("0"):
            raise ValueError("average_workforce must be a finite non-negative Decimal")
        if value != value.quantize(_TWO_PLACES):
            raise ValueError("average_workforce carries at most two decimal places")
        return value


class AverageWorkforceHistory(BaseModel):
    """The taxpayer's declared average workforce, one entry per calendar year."""

    model_config = STRICT_FROZEN_CONFIG

    years: tuple[AverageWorkforceYear, ...] = ()

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_unique_years(self) -> Self:
        declared = [item.year for item in self.years]
        if len(set(declared)) != len(declared):
            raise ValueError("average workforce declares a calendar year more than once")
        return self

    def require(self, year: int) -> AverageWorkforceYear:
        """Return a declared year, or refuse: an undeclared year is never zero."""
        found = next((item for item in self.years if item.year == year), None)
        if found is None:
            raise ActividadAssetIncompleteError(f"the average workforce of {year} is not declared")
        return found


class WorkforceIncrease(BaseModel):
    """The LIS art. 102 increase and the years still carrying a commitment."""

    model_config = STRICT_FROZEN_CONFIG

    increase: Decimal
    committed_years: tuple[int, ...]


class WorkforceMaintenance(BaseModel):
    """A met LIS DA 17a condition and the years still carrying a commitment."""

    model_config = STRICT_FROZEN_CONFIG

    committed_years: tuple[int, ...]


def _window_average(years: tuple[AverageWorkforceYear, ...]) -> Decimal:
    """Average consecutive years weighted by their days, as one window would count them."""
    days = [Decimal(366 if calendar.isleap(item.year) else 365) for item in years]
    weighted = sum((item.average_workforce * day for item, day in zip(years, days, strict=True)), Decimal("0"))
    return weighted / sum(days, Decimal("0"))


def _committed(years: tuple[AverageWorkforceYear, ...]) -> tuple[int, ...]:
    return tuple(item.year for item in years if item.state is WorkforceYearState.COMMITTED)


def job_creation_increase(history: AverageWorkforceHistory, *, entry_year: int) -> WorkforceIncrease:
    """Apply LIS art. 102.1 for assets entering service in ``entry_year``.

    The increase is truncated to two decimals, the reading of "calculado con
    dos decimales" that can never overstate the eligible investment.
    """
    before = history.require(entry_year - 1)
    following = (history.require(entry_year), history.require(entry_year + 1))
    maintained = (history.require(entry_year + 2), history.require(entry_year + 3))
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
    return WorkforceIncrease(increase=increase, committed_years=_committed((before, *following, *maintained)))


def renewable_workforce_maintained(history: AverageWorkforceHistory, *, entry_year: int) -> WorkforceMaintenance:
    """Apply LIS DA 17a.1: the 24-month average must not fall below the prior 12 months."""
    before = history.require(entry_year - 1)
    following = (history.require(entry_year), history.require(entry_year + 1))
    if _window_average(following) < before.average_workforce:
        raise ActividadAssetUnsupportedError(
            "the average workforce of the 24 months after the entry year's start falls below that of the "
            "12 months before (LIS DA 17a.1)",
        )
    return WorkforceMaintenance(committed_years=_committed((before, *following)))


__all__ = [
    "AverageWorkforceHistory",
    "AverageWorkforceYear",
    "WorkforceIncrease",
    "WorkforceMaintenance",
    "WorkforceYearState",
    "job_creation_increase",
    "renewable_workforce_maintained",
]
