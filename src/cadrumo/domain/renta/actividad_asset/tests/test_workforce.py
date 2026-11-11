"""Average-workforce conditions of LIS art. 102 and DA 17a, checked by hand."""

from __future__ import annotations

from calendar import isleap
from decimal import ROUND_DOWN, Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetIncompleteError, ActividadAssetUnsupportedError
from cadrumo.domain.renta.actividad_asset.workforce import (
    WorkforceWindows,
    job_creation_increase,
    renewable_workforce_maintained,
)
from cadrumo.domain.user_profile.plantilla_media import PlantillaMediaYear, plantilla_media_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ART_102 = WorkforceWindows(prior_months=12, following_months=24, maintained_months=24)
_DA_17 = WorkforceWindows(prior_months=12, following_months=24)
_ENTRY = filing_year_envelope().horizon
"""The entry year of the investment; the declared years are counted from it."""


def _days_in_year(year: int) -> int:
    return 366 if isleap(year) else 365


def _weighted_average(*year_values: tuple[int, str]) -> Decimal:
    """Return the average workforce weighted by the days of each year."""
    days = [_days_in_year(year) for year, _ in year_values]
    return sum((Decimal(value) * day for (_, value), day in zip(year_values, days, strict=True)), Decimal(0)) / sum(
        days
    )


def _years(*rows: tuple[int, str, str]) -> tuple[PlantillaMediaYear, ...]:
    """Build instances through the profile's own validating reader."""
    facts: dict[str, object] = {}
    for index, (year, value, state) in enumerate(rows):
        facts[f"irpf.plantilla_media.{index}.year"] = year
        facts[f"irpf.plantilla_media.{index}.average_workforce"] = Decimal(value)
        facts[f"irpf.plantilla_media.{index}.state"] = state
    return plantilla_media_years(facts)


def test_the_job_creation_increase_is_measured_and_its_maintenance_checked() -> None:
    years = _years(
        (_ENTRY - 1, "10.00", "observed"),
        (_ENTRY, "12.00", "observed"),
        (_ENTRY + 1, "12.00", "committed"),
        (_ENTRY + 2, "12.50", "committed"),
        (_ENTRY + 3, "12.00", "committed"),
    )

    result = job_creation_increase(years, entry_year=_ENTRY, windows=_ART_102, increase_decimal_places=2)

    # The entry year and the next average 12.00 against 10.00 before: an increase of 2.00. The
    # maintenance window weighs each year by its days and stays above the prior 10.00 by more than 2.00.
    maintained = _weighted_average((_ENTRY + 2, "12.50"), (_ENTRY + 3, "12.00"))
    assert maintained - Decimal("10.00") > Decimal("2.00")
    assert result.increase == Decimal("2.00")
    assert result.committed_years == (_ENTRY + 1, _ENTRY + 2, _ENTRY + 3)


def test_the_increase_is_truncated_to_two_decimals_and_weighted_by_days() -> None:
    truncated = _years(
        (_ENTRY - 1, "10.00", "observed"),
        (_ENTRY, "11.01", "observed"),
        (_ENTRY + 1, "11.00", "observed"),
        (_ENTRY + 2, "11.01", "observed"),
        (_ENTRY + 3, "11.01", "observed"),
    )
    leap_entry = next(year for year in filing_year_envelope().years if isleap(year))
    leap = _years(
        (leap_entry - 1, "5.00", "observed"),
        (leap_entry, "7.00", "observed"),
        (leap_entry + 1, "6.00", "observed"),
        (leap_entry + 2, "7.00", "observed"),
        (leap_entry + 3, "7.00", "observed"),
    )

    # The weighted average of 11.01 and 11.00 stays within a day of weight of 11.005, so the increase
    # over 10.00 is 1.005 give or take 0.0001, truncated to 1.00 rather than rounded up.
    assert job_creation_increase(
        truncated, entry_year=_ENTRY, windows=_ART_102, increase_decimal_places=2
    ).increase == Decimal("1.00")
    # The entry year is a leap year: the window weighs 7.00 by 366 days and 6.00 by 365, over 5.00
    # before, and the increase is cut to two decimals without rounding.
    weighted_increase = _weighted_average((leap_entry, "7.00"), (leap_entry + 1, "6.00")) - Decimal("5.00")
    assert job_creation_increase(
        leap, entry_year=leap_entry, windows=_ART_102, increase_decimal_places=2
    ).increase == weighted_increase.quantize(Decimal("0.01"), rounding=ROUND_DOWN)


def test_no_increase_an_unkept_increase_and_an_undeclared_year_refuse() -> None:
    flat = _years(
        (_ENTRY - 1, "10.00", "observed"),
        (_ENTRY, "10.00", "observed"),
        (_ENTRY + 1, "10.00", "observed"),
        (_ENTRY + 2, "10.00", "observed"),
        (_ENTRY + 3, "10.00", "observed"),
    )
    unkept = _years(
        (_ENTRY - 1, "10.00", "observed"),
        (_ENTRY, "12.00", "observed"),
        (_ENTRY + 1, "12.00", "observed"),
        (_ENTRY + 2, "11.00", "observed"),
        (_ENTRY + 3, "11.00", "observed"),
    )
    partial = _years(
        (_ENTRY - 1, "10.00", "observed"), (_ENTRY, "12.00", "observed"), (_ENTRY + 1, "12.00", "observed")
    )

    with pytest.raises(ActividadAssetUnsupportedError) as flat_refusal:
        job_creation_increase(flat, entry_year=_ENTRY, windows=_ART_102, increase_decimal_places=2)
    assert flat_refusal.value.translated_message == "ledger.actividad_asset.errors.workforce_increase_not_reached"
    with pytest.raises(ActividadAssetUnsupportedError) as unkept_refusal:
        job_creation_increase(unkept, entry_year=_ENTRY, windows=_ART_102, increase_decimal_places=2)
    assert unkept_refusal.value.translated_message == "ledger.actividad_asset.errors.workforce_increase_not_kept"
    with pytest.raises(ActividadAssetIncompleteError) as partial_refusal:
        job_creation_increase(partial, entry_year=_ENTRY, windows=_ART_102, increase_decimal_places=2)
    assert partial_refusal.value.translated_message == "ledger.actividad_asset.errors.workforce_year_not_declared"
    assert partial_refusal.value.context == {"year": _ENTRY + 2}


def test_renewable_free_depreciation_needs_the_workforce_kept() -> None:
    kept = _years((_ENTRY - 1, "8.00", "observed"), (_ENTRY, "8.00", "observed"), (_ENTRY + 1, "8.00", "committed"))
    fallen = _years((_ENTRY - 1, "8.00", "observed"), (_ENTRY, "8.00", "observed"), (_ENTRY + 1, "7.50", "observed"))

    assert renewable_workforce_maintained(kept, entry_year=_ENTRY, windows=_DA_17).committed_years == (_ENTRY + 1,)
    with pytest.raises(ActividadAssetUnsupportedError) as fallen_refusal:
        renewable_workforce_maintained(fallen, entry_year=_ENTRY, windows=_DA_17)
    assert fallen_refusal.value.translated_message == "ledger.actividad_asset.errors.workforce_fell_below"
    with pytest.raises(ActividadAssetIncompleteError) as undeclared_refusal:
        renewable_workforce_maintained(_years((_ENTRY, "8.00", "observed")), entry_year=_ENTRY, windows=_DA_17)
    assert undeclared_refusal.value.translated_message == "ledger.actividad_asset.errors.workforce_year_not_declared"
    assert undeclared_refusal.value.context == {"year": _ENTRY - 1}


def test_a_window_is_read_from_its_parameter_and_a_part_year_refuses() -> None:
    years = _years(
        (_ENTRY - 2, "4.00", "observed"),
        (_ENTRY - 1, "6.00", "observed"),
        (_ENTRY, "9.00", "observed"),
    )

    # A two-year prior window of 4.00 and 6.00 averages about 5.00 day-weighted, under 9.00 for the entry year.
    widened = WorkforceWindows(prior_months=24, following_months=12)
    assert renewable_workforce_maintained(years, entry_year=_ENTRY, windows=widened).years == years
    with pytest.raises(ActividadAssetUnsupportedError) as refusal:
        renewable_workforce_maintained(
            years, entry_year=_ENTRY, windows=WorkforceWindows(prior_months=18, following_months=12)
        )
    assert refusal.value.translated_message == "ledger.actividad_asset.errors.workforce_window_not_whole_years"
