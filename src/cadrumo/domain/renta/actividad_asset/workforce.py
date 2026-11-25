"""Average-workforce conditions of two free-depreciation incentives.

LIS art. 102.1 admits free depreciation when the average total workforce of
a period after the start of the tax period in which the assets enter service
exceeds that of a period before it, and the increase is kept for a further
period; the eligible investment is an amount per unit of the increase.  LIS
DA 17a.1 conditions its free depreciation on keeping the later average at the
earlier level.  Workforce counts people employed as labour law defines them,
weighted by contracted hours against a full working day.

The lengths of those periods and the increase's decimal places are registry
parameters, which the law states in months.  An IRPF tax period is the calendar
year, so each one becomes consecutive calendar years around the entry year; a
length that is not a whole number of years cannot be counted from calendar-year
averages and refuses.  The years come from the taxpayer profile's validated
``irpf.plantilla_media`` instances.  A year not yet closed may be declared as a
commitment; it carries a regularisation duty (LIS art. 102.4, DA 17a.7) that
the evaluation reports rather than hides.
"""

from __future__ import annotations

import calendar
from decimal import ROUND_DOWN, Decimal

from pydantic import BaseModel, Field

from ....core.models import STRICT_FROZEN_CONFIG
from ...user_profile.plantilla_media import PlantillaMediaState, PlantillaMediaYear
from .errors import ActividadAssetIncompleteError, ActividadAssetUnsupportedError

_MONTHS_PER_YEAR = 12


class WorkforceWindows(BaseModel):
    """How long, in months, each average a workforce condition compares runs."""

    model_config = STRICT_FROZEN_CONFIG

    prior_months: int = Field(gt=0)
    following_months: int = Field(gt=0)
    maintained_months: int = Field(default=0, ge=0)


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
        raise ActividadAssetIncompleteError(
            context={"year": year},
            translated_message="ledger.actividad_asset.errors.workforce_year_not_declared",
        )
    return found


def _window_average(years: tuple[PlantillaMediaYear, ...]) -> Decimal:
    """Average consecutive years weighted by their days, as one window would count them."""
    days = [Decimal(366 if calendar.isleap(item.year) else 365) for item in years]
    weighted = sum((item.average_workforce * day for item, day in zip(years, days, strict=True)), Decimal("0"))
    return weighted / sum(days, Decimal("0"))


def _whole_years(months: int) -> int:
    """Return a window's length in calendar years, or refuse one calendar years cannot measure."""
    years, remainder = divmod(months, _MONTHS_PER_YEAR)
    if remainder:
        raise ActividadAssetUnsupportedError(
            context={"months": months},
            translated_message="ledger.actividad_asset.errors.workforce_window_not_whole_years",
        )
    return years


def _prior_years(
    years: tuple[PlantillaMediaYear, ...], *, entry_year: int, months: int
) -> tuple[PlantillaMediaYear, ...]:
    length = _whole_years(months)
    return tuple(_require(years, entry_year - offset) for offset in range(length, 0, -1))


def _years_from(
    years: tuple[PlantillaMediaYear, ...], *, first_year: int, months: int
) -> tuple[PlantillaMediaYear, ...]:
    return tuple(_require(years, first_year + offset) for offset in range(_whole_years(months)))


def _committed(years: tuple[PlantillaMediaYear, ...]) -> tuple[int, ...]:
    return tuple(item.year for item in years if item.state is PlantillaMediaState.COMMITTED)


def job_creation_increase(
    years: tuple[PlantillaMediaYear, ...],
    *,
    entry_year: int,
    windows: WorkforceWindows,
    increase_decimal_places: int,
) -> WorkforceIncrease:
    """Apply LIS art. 102.1 for assets entering service in ``entry_year``.

    The law states how many decimals the increase carries, not how it reaches
    them; it is truncated, the reading that can never overstate the eligible
    investment.
    """
    before = _prior_years(years, entry_year=entry_year, months=windows.prior_months)
    following = _years_from(years, first_year=entry_year, months=windows.following_months)
    maintained = _years_from(
        years,
        first_year=entry_year + _whole_years(windows.following_months),
        months=windows.maintained_months,
    )
    baseline = _window_average(before)
    increase = (_window_average(following) - baseline).quantize(
        Decimal(1).scaleb(-increase_decimal_places),
        rounding=ROUND_DOWN,
    )
    if increase <= Decimal("0"):
        raise ActividadAssetUnsupportedError(
            context={"following_months": windows.following_months, "prior_months": windows.prior_months},
            translated_message="ledger.actividad_asset.errors.workforce_increase_not_reached",
        )
    if _window_average(maintained) - baseline < increase:
        raise ActividadAssetUnsupportedError(
            context={"maintained_months": windows.maintained_months},
            translated_message="ledger.actividad_asset.errors.workforce_increase_not_kept",
        )
    used = (*before, *following, *maintained)
    return WorkforceIncrease(increase=increase, years=used, committed_years=_committed(used))


def renewable_workforce_maintained(
    years: tuple[PlantillaMediaYear, ...],
    *,
    entry_year: int,
    windows: WorkforceWindows,
) -> WorkforceMaintenance:
    """Apply LIS DA 17a.1: the later average must not fall below the earlier one."""
    before = _prior_years(years, entry_year=entry_year, months=windows.prior_months)
    following = _years_from(years, first_year=entry_year, months=windows.following_months)
    if _window_average(following) < _window_average(before):
        raise ActividadAssetUnsupportedError(
            context={"following_months": windows.following_months, "prior_months": windows.prior_months},
            translated_message="ledger.actividad_asset.errors.workforce_fell_below",
        )
    used = (*before, *following)
    return WorkforceMaintenance(years=used, committed_years=_committed(used))


__all__ = [
    "WorkforceIncrease",
    "WorkforceMaintenance",
    "WorkforceWindows",
    "job_creation_increase",
    "renewable_workforce_maintained",
]
