"""Average-workforce conditions of LIS art. 102 and DA 17a, checked by hand."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.domain.renta.actividad_asset.errors import ActividadAssetIncompleteError, ActividadAssetUnsupportedError
from cadrumo.domain.renta.actividad_asset.workforce import job_creation_increase, renewable_workforce_maintained
from cadrumo.domain.user_profile.plantilla_media import PlantillaMediaYear, plantilla_media_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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
        (2024, "10.00", "observed"),
        (2025, "12.00", "observed"),
        (2026, "12.00", "committed"),
        (2027, "12.50", "committed"),
        (2028, "12.00", "committed"),
    )

    result = job_creation_increase(years, entry_year=2025)

    # 2025 and 2026 average 12.00 against 10.00 before: an increase of 2.00. The maintenance
    # window weighs 2028's 366 days: (12.50 x 365 + 12.00 x 366) / 731 = 12.2497, still 2.2497 up.
    assert result.increase == Decimal("2.00")
    assert result.committed_years == (2026, 2027, 2028)


def test_the_increase_is_truncated_to_two_decimals_and_weighted_by_days() -> None:
    truncated = _years(
        (2024, "10.00", "observed"),
        (2025, "11.01", "observed"),
        (2026, "11.00", "observed"),
        (2027, "11.01", "observed"),
        (2028, "11.01", "observed"),
    )
    leap = _years(
        (2023, "5.00", "observed"),
        (2024, "7.00", "observed"),
        (2025, "6.00", "observed"),
        (2026, "7.00", "observed"),
        (2027, "7.00", "observed"),
    )

    # (11.01 + 11.00) / 2 = 11.005 over 10.00 is 1.005, truncated to 1.00 rather than rounded up.
    assert job_creation_increase(truncated, entry_year=2025).increase == Decimal("1.00")
    # (7.00 x 366 + 6.00 x 365) / 731 = 6.50068 over 5.00 is 1.50068, truncated to 1.50.
    assert job_creation_increase(leap, entry_year=2024).increase == Decimal("1.50")


def test_no_increase_an_unkept_increase_and_an_undeclared_year_refuse() -> None:
    flat = _years(
        (2024, "10.00", "observed"),
        (2025, "10.00", "observed"),
        (2026, "10.00", "observed"),
        (2027, "10.00", "observed"),
        (2028, "10.00", "observed"),
    )
    unkept = _years(
        (2024, "10.00", "observed"),
        (2025, "12.00", "observed"),
        (2026, "12.00", "observed"),
        (2027, "11.00", "observed"),
        (2028, "11.00", "observed"),
    )
    partial = _years((2024, "10.00", "observed"), (2025, "12.00", "observed"), (2026, "12.00", "observed"))

    with pytest.raises(ActividadAssetUnsupportedError, match="does not exceed"):
        job_creation_increase(flat, entry_year=2025)
    with pytest.raises(ActividadAssetUnsupportedError, match="further 24 months"):
        job_creation_increase(unkept, entry_year=2025)
    with pytest.raises(ActividadAssetIncompleteError, match="2027 is not declared"):
        job_creation_increase(partial, entry_year=2025)


def test_renewable_free_depreciation_needs_the_workforce_kept() -> None:
    kept = _years((2024, "8.00", "observed"), (2025, "8.00", "observed"), (2026, "8.00", "committed"))
    fallen = _years((2024, "8.00", "observed"), (2025, "8.00", "observed"), (2026, "7.50", "observed"))

    assert renewable_workforce_maintained(kept, entry_year=2025).committed_years == (2026,)
    with pytest.raises(ActividadAssetUnsupportedError, match="DA 17a"):
        renewable_workforce_maintained(fallen, entry_year=2025)
    with pytest.raises(ActividadAssetIncompleteError, match="2024 is not declared"):
        renewable_workforce_maintained(_years((2025, "8.00", "observed")), entry_year=2025)
