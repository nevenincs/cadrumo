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
  - Unsupported ejercicios fail closed instead of falling back to module constants.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ...calculations.registry import RegistryValidationError, read_parameter
from .._enums import ReduccionTier
from .._tier_resolver import (
    DEFAULT_EJERCICIO_AMENDMENT_YEAR,
    JOVEN_TENANT_AGE_MAX,
    JOVEN_TENANT_AGE_MIN,
    REHAB_LOOKBACK_DAYS,
    TierResolution,
    _resolve_ejercicio_amendment_year,
    _resolve_joven_tenant_age_range,
    _resolve_prior_rent_rebaja_threshold,
    _resolve_rehab_lookback_days,
    _resolve_tier_reduccion_rate,
    _with_registry_rate,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

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


def test_resolver_threshold_helper_refuses_unregistered_year() -> None:
    with pytest.raises(RegistryValidationError, match="has no revision '1999'"):
        _resolve_prior_rent_rebaja_threshold(1999)


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


def test_resolver_amendment_year_helper_refuses_unregistered_year() -> None:
    with pytest.raises(RegistryValidationError, match="has no revision '1999'"):
        _resolve_ejercicio_amendment_year(1999)


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


def test_resolver_rehab_lookback_helper_refuses_unregistered_year() -> None:
    with pytest.raises(RegistryValidationError, match="has no revision '1999'"):
        _resolve_rehab_lookback_days(1999)


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


def test_resolver_joven_age_range_helper_refuses_unregistered_year() -> None:
    with pytest.raises(RegistryValidationError, match="has no revision '1999'"):
        _resolve_joven_tenant_age_range(1999)


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


def test_resolver_tier_rate_helper_refuses_unregistered_year() -> None:
    with pytest.raises(RegistryValidationError, match="has no revision '1999'"):
        _resolve_tier_reduccion_rate(1999, "tier-90")


# --- Causality proof: the dispatch sources the tier rate FROM the registry ---
#
# Before this wiring the registry reader was dormant — the dispatch returned
# inline TierResolution singletons and the registry parameter was authoritative
# only on paper. These tests prove _with_registry_rate (the dispatch's seam to
# the reader) is genuinely causal: a template carrying a wrong rate is corrected
# to the registry value, not echoed back. If the wiring is ever reverted to
# return the inline constant, the override test fails.


@pytest.mark.parametrize(("tier_id", "registry_rate"), _TIER_RATES)
def test_with_registry_rate_overrides_wrong_template_with_registry_value(
    tier_id: str,
    registry_rate: Decimal,
) -> None:
    """A template carrying a deliberately-wrong rate is corrected to the registry value."""
    wrong_template = TierResolution(
        tier=ReduccionTier.TIER_90,
        reduccion_pct=Decimal("0.99"),
        qualifying_share=Decimal("1"),
        boe_citation_id="art_23_2_a",
    )
    result = _with_registry_rate(wrong_template, 2024, tier_id)
    # The rate comes from the registry parameter, NOT the template's 0.99.
    assert result.reduccion_pct == registry_rate
    assert result.reduccion_pct != Decimal("0.99")


def test_with_registry_rate_preserves_singleton_identity_when_rate_matches() -> None:
    """When the registry rate equals the template rate the frozen singleton is returned unchanged."""
    template = TierResolution(
        tier=ReduccionTier.TIER_90,
        reduccion_pct=Decimal("0.90"),
        qualifying_share=Decimal("1"),
        boe_citation_id="art_23_2_a",
    )
    result = _with_registry_rate(template, 2024, "tier-90")
    assert result is template


def test_with_registry_rate_preserves_qualifying_share_on_override() -> None:
    """Overriding the rate must not disturb the computed qualifying_share (joven co-tenant case)."""
    joven_template = TierResolution(
        tier=ReduccionTier.TIER_70_JOVEN,
        reduccion_pct=Decimal("0.99"),
        qualifying_share=Decimal("0.5"),
        boe_citation_id="art_23_2_b_1",
    )
    result = _with_registry_rate(joven_template, 2024, "tier-70")
    assert result.reduccion_pct == Decimal("0.70")
    assert result.qualifying_share == Decimal("0.5")
