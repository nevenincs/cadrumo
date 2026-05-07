"""Integration: rental tier resolver consumes the LIRPF art. 23.2 a) rebaja threshold from the registry.

Phase #50/#78: the prior-rent-rebaja threshold (5% per BOE Ley 12/2023) lives as a
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
from aeat.domain.rental._tier_resolver import (
    PRIOR_RENT_REBAJA_THRESHOLD,
    _resolve_prior_rent_rebaja_threshold,
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
