"""Integration: rental tier resolver consumes the LIRPF art. 23.2 a) rebaja threshold from the registry.

The prior-rent-rebaja threshold (5% per BOE Ley 12/2023) lives as a
registry parameter under Modelo 100 / each ejercicio (id pattern
``renta-<year>-rental-prior-rent-rebaja-threshold``). The rental resolver's
``_resolve_prior_rent_rebaja_threshold(period_year)`` reads it via
``cadrumo.domain.calculations.registry.read_parameter`` and threads the value into
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

from ....core.resources._boundary import bundled_path
from ...calculations.registry.authority import bundled_authority
from ...calculations.registry.errors import RegistryValidationError
from ...calculations.registry.formula_runtime_ops import read_parameter
from ...calculations.registry.legal import verify_legal_catalogue
from ..enums import ReduccionTier
from ..tier_resolver import (
    DEFAULT_EJERCICIO_AMENDMENT_YEAR,
    JOVEN_TENANT_AGE_MAX,
    JOVEN_TENANT_AGE_MIN,
    REHAB_LOOKBACK_YEARS,
    TierResolution,
    _resolve_ejercicio_amendment_year,
    _resolve_joven_tenant_age_range,
    _resolve_prior_rent_rebaja_threshold,
    _resolve_rehab_lookback_years,
    _resolve_tier_reduccion_rate,
    _with_registry_rate,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SUPPORTED_YEARS = (2020, 2021, 2022, 2023, 2024, 2025)
_RESOLVER_LEGAL_REFS = (
    "ley-35-2006:art-23",
    "ley-35-2006:art-23-2021",
    "ley-35-2006:dt-38",
)
_TIER_RATES = (
    ("tier-50", Decimal("0.50")),
    ("tier-60", Decimal("0.60")),
    ("tier-70", Decimal("0.70")),
    ("tier-90", Decimal("0.90")),
)


def _read_rental_parameter(year: int, suffix: str) -> Decimal:
    return read_parameter(
        "100",
        str(year),
        f"renta-{year}-{suffix}",
        date_context={"filing_period": date(year, 12, 31)},
    )


def test_resolver_legal_refs_resolve_against_catalogue_and_bundled_corpus() -> None:
    catalogues = bundled_authority().catalogues
    missing = sorted(ref for ref in _RESOLVER_LEGAL_REFS if ref not in catalogues.legal)

    assert missing == []
    verify_legal_catalogue(
        {ref: catalogues.legal[ref] for ref in _RESOLVER_LEGAL_REFS},
        source_root=bundled_path(),
    )


def test_rental_registry_parameters_registered_for_every_supported_ejercicio() -> None:
    scalar_parameters = (
        ("rental-prior-rent-rebaja-threshold", Decimal("0.05")),
        ("rental-ejercicio-amendment-year", Decimal("2024")),
        # Two CALENDAR years, not 730 days: art. 23.2.c counts de fecha a fecha and a
        # day count is one short across any leap span.
        ("rental-rehab-lookback-years", Decimal("2")),
        ("rental-joven-tenant-age-min", Decimal("18")),
        ("rental-joven-tenant-age-max", Decimal("35")),
    )
    for year in _SUPPORTED_YEARS:
        for suffix, expected in scalar_parameters:
            assert _read_rental_parameter(year, suffix) == expected, (year, suffix)
        for tier_id, expected in _TIER_RATES:
            assert _read_rental_parameter(year, f"rental-reduccion-rate-{tier_id}") == expected, (year, tier_id)


def test_resolver_helpers_return_registry_values_for_every_supported_ejercicio() -> None:
    for year in _SUPPORTED_YEARS:
        assert _resolve_prior_rent_rebaja_threshold(year) == Decimal("0.05"), year

        amendment_year = _resolve_ejercicio_amendment_year(year)
        assert amendment_year == 2024
        assert amendment_year == DEFAULT_EJERCICIO_AMENDMENT_YEAR

        rehab_lookback_years = _resolve_rehab_lookback_years(year)
        assert rehab_lookback_years == 2
        assert rehab_lookback_years == REHAB_LOOKBACK_YEARS

        age_min, age_max = _resolve_joven_tenant_age_range(year)
        assert (age_min, age_max) == (18, 35)
        assert age_min == JOVEN_TENANT_AGE_MIN
        assert age_max == JOVEN_TENANT_AGE_MAX

        for tier_id, expected in _TIER_RATES:
            assert _resolve_tier_reduccion_rate(year, tier_id) == expected, (year, tier_id)


def test_resolver_threshold_helper_refuses_unregistered_year() -> None:
    with pytest.raises(RegistryValidationError, match="has no revision '1999'"):
        _resolve_prior_rent_rebaja_threshold(1999)


def test_resolver_amendment_year_helper_refuses_unregistered_year() -> None:
    with pytest.raises(RegistryValidationError, match="has no revision '1999'"):
        _resolve_ejercicio_amendment_year(1999)


def test_resolver_rehab_lookback_helper_refuses_unregistered_year() -> None:
    with pytest.raises(RegistryValidationError, match="has no revision '1999'"):
        _resolve_rehab_lookback_years(1999)


def test_resolver_joven_age_range_helper_refuses_unregistered_year() -> None:
    with pytest.raises(RegistryValidationError, match="has no revision '1999'"):
        _resolve_joven_tenant_age_range(1999)


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


def test_with_registry_rate_overrides_wrong_template_with_registry_value() -> None:
    """A template carrying a deliberately-wrong rate is corrected to the registry value."""
    for tier_id, registry_rate in _TIER_RATES:
        wrong_template = TierResolution(
            tier=ReduccionTier.TIER_90,
            reduccion_pct=Decimal("0.99"),
            qualifying_share=Decimal("1"),
            legal_refs=("ley-35-2006:art-23",),
        )
        result = _with_registry_rate(wrong_template, 2024, tier_id)
        # The rate comes from the registry parameter, NOT the template's 0.99.
        assert result.reduccion_pct == registry_rate, tier_id
        assert result.reduccion_pct != Decimal("0.99")


def test_with_registry_rate_preserves_singleton_identity_when_rate_matches() -> None:
    """When the registry rate equals the template rate the frozen singleton is returned unchanged."""
    template = TierResolution(
        tier=ReduccionTier.TIER_90,
        reduccion_pct=Decimal("0.90"),
        qualifying_share=Decimal("1"),
        legal_refs=("ley-35-2006:art-23",),
    )
    result = _with_registry_rate(template, 2024, "tier-90")
    assert result is template


def test_with_registry_rate_preserves_qualifying_share_on_override() -> None:
    """Overriding the rate must not disturb the computed qualifying_share (joven co-tenant case)."""
    joven_template = TierResolution(
        tier=ReduccionTier.TIER_70_JOVEN,
        reduccion_pct=Decimal("0.99"),
        qualifying_share=Decimal("0.5"),
        legal_refs=("ley-35-2006:art-23",),
    )
    result = _with_registry_rate(joven_template, 2024, "tier-70")
    assert result.reduccion_pct == Decimal("0.70")
    assert result.qualifying_share == Decimal("0.5")
