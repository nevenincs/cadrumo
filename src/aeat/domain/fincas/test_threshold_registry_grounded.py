"""Integration: rental tier resolver consumes the LIRPF art. 23.2 a) rebaja threshold from the registry.

The prior-rent-rebaja threshold (5% per BOE Ley 12/2023) lives as a
registry parameter under Modelo 100 / each ejercicio (id pattern
``renta-<year>-rental-prior-rent-rebaja-threshold``). The rental resolver's
``_resolve_prior_rent_rebaja_threshold(period_year)`` reads it via
``aeat.domain.calculations.registry.read_parameter`` and threads the value into
``_qualifies_for_tier_90``.

These tests confirm:

  - The registry actually holds the parameter for every supported ejercicio.
  - The resolver consumes the registry value (matches the documented module
    constant ``PRIOR_RENT_REBAJA_THRESHOLD = 0.05``).
  - The fallback path (registry lookup miss) returns the constant.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.domain.calculations.registry import read_parameter
from aeat.domain.fincas._tier_resolver import (
    DEFAULT_EJERCICIO_AMENDMENT_YEAR,
    JOVEN_TENANT_AGE_MAX,
    JOVEN_TENANT_AGE_MIN,
    PRIOR_RENT_REBAJA_THRESHOLD,
    REHAB_LOOKBACK_DAYS,
    _resolve_ejercicio_amendment_year,
    _resolve_joven_tenant_age_range,
    _resolve_prior_rent_rebaja_threshold,
    _resolve_rehab_lookback_days,
    _resolve_tier_reduccion_rate,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_SUPPORTED_YEARS = (2020, 2021, 2022, 2023, 2024, 2025)


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
def test_rental_rebaja_threshold_parameter_registered_for_every_ejercicio(year: int) -> None:
    value = read_parameter(
        "100",
        str(year),
        f"renta-{year}-rental-prior-rent-rebaja-threshold",
        date_context={"filing_period": date(year, 12, 31)},
    )
    assert value == Decimal("0.05")


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
def test_resolver_threshold_helper_returns_registry_value(year: int) -> None:
    value = _resolve_prior_rent_rebaja_threshold(year)
    assert value == Decimal("0.05")


def test_resolver_threshold_helper_falls_back_to_constant_for_unregistered_year() -> None:
    """When the registry lookup misses (year out of supported range), fallback to constant."""
    value = _resolve_prior_rent_rebaja_threshold(1999)
    assert value == PRIOR_RENT_REBAJA_THRESHOLD
    assert value == Decimal("0.05")


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
def test_amendment_year_parameter_registered_for_every_ejercicio(year: int) -> None:
    value = read_parameter(
        "100",
        str(year),
        f"renta-{year}-rental-ejercicio-amendment-year",
        date_context={"filing_period": date(year, 12, 31)},
    )
    assert value == Decimal("2024")


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
def test_resolver_amendment_year_helper_returns_registry_value(year: int) -> None:
    value = _resolve_ejercicio_amendment_year(year)
    assert value == 2024
    assert value == DEFAULT_EJERCICIO_AMENDMENT_YEAR


def test_resolver_amendment_year_helper_falls_back_for_unregistered_year() -> None:
    value = _resolve_ejercicio_amendment_year(1999)
    assert value == DEFAULT_EJERCICIO_AMENDMENT_YEAR


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
def test_rehab_lookback_days_parameter_registered_for_every_ejercicio(year: int) -> None:
    value = read_parameter(
        "100",
        str(year),
        f"renta-{year}-rental-rehab-lookback-days",
        date_context={"filing_period": date(year, 12, 31)},
    )
    assert value == Decimal("730")


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
def test_resolver_rehab_lookback_helper_returns_registry_value(year: int) -> None:
    value = _resolve_rehab_lookback_days(year)
    assert value == 730
    assert value == REHAB_LOOKBACK_DAYS


def test_resolver_rehab_lookback_helper_falls_back_for_unregistered_year() -> None:
    value = _resolve_rehab_lookback_days(1999)
    assert value == REHAB_LOOKBACK_DAYS


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
def test_joven_tenant_age_parameters_registered_for_every_ejercicio(year: int) -> None:
    age_min = read_parameter(
        "100",
        str(year),
        f"renta-{year}-rental-joven-tenant-age-min",
        date_context={"filing_period": date(year, 12, 31)},
    )
    age_max = read_parameter(
        "100",
        str(year),
        f"renta-{year}-rental-joven-tenant-age-max",
        date_context={"filing_period": date(year, 12, 31)},
    )
    assert age_min == Decimal("18")
    assert age_max == Decimal("35")


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
def test_resolver_joven_age_range_helper_returns_registry_value(year: int) -> None:
    age_min, age_max = _resolve_joven_tenant_age_range(year)
    assert (age_min, age_max) == (18, 35)
    assert age_min == JOVEN_TENANT_AGE_MIN
    assert age_max == JOVEN_TENANT_AGE_MAX


def test_resolver_joven_age_range_helper_falls_back_for_unregistered_year() -> None:
    age_min, age_max = _resolve_joven_tenant_age_range(1999)
    assert (age_min, age_max) == (JOVEN_TENANT_AGE_MIN, JOVEN_TENANT_AGE_MAX)


_TIER_RATES = (
    ("tier-50", Decimal("0.50")),
    ("tier-60", Decimal("0.60")),
    ("tier-70", Decimal("0.70")),
    ("tier-90", Decimal("0.90")),
)


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
@pytest.mark.parametrize(("tier_id", "expected"), _TIER_RATES)
def test_tier_reduccion_rate_parameter_registered_for_every_year(year: int, tier_id: str, expected: Decimal) -> None:
    value = read_parameter(
        "100",
        str(year),
        f"renta-{year}-rental-reduccion-rate-{tier_id}",
        date_context={"filing_period": date(year, 12, 31)},
    )
    assert value == expected


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
@pytest.mark.parametrize(("tier_id", "expected"), _TIER_RATES)
def test_resolver_tier_rate_helper_returns_registry_value(year: int, tier_id: str, expected: Decimal) -> None:
    assert _resolve_tier_reduccion_rate(year, tier_id) == expected


def test_resolver_tier_rate_helper_falls_back_for_unregistered_year() -> None:
    assert _resolve_tier_reduccion_rate(1999, "tier-90") == Decimal("0.90")
