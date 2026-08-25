"""Integration: the amortisation ledger consumes the RIRPF art. 14 rate from the registry.

The 3 por ciento amortisation rate for rented capital-inmobiliario lives as a
registry parameter under Modelo 100 / each ejercicio (id pattern
``renta-<year>-rental-amortizacion-rate``), grounded on ``rd-439-2007:art-14``
(the reglamentary provision that fixes the 3 por ciento over the greater of the
acquisition cost or the cadastral value, excluding the land) plus
``ley-35-2006:art-23`` as the substantive base. The ledger's
``_resolve_amortizacion_inmueble_rate(period_year)`` reads it via
``cadrumo.domain.calculations.registry.read_parameter`` and threads the value into
``compute_amortization_for_year``.

These tests confirm:

  - The registry holds the parameter for every supported ejercicio.
  - The resolver consumes the registry value (the documented constant
    ``ART_23_1_F_RATE`` / ``AMORTIZACION_INMUEBLE_RATE`` is ``0.03``).
  - Unsupported ejercicios fail closed instead of falling back to the constant.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.formula_runtime import read_parameter
from .._amortization_ledger import _resolve_amortizacion_inmueble_rate

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SUPPORTED_YEARS = (2020, 2021, 2022, 2023, 2024, 2025)


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
def test_amortizacion_rate_parameter_registered_for_every_ejercicio(year: int) -> None:
    value = read_parameter(
        "100",
        str(year),
        f"renta-{year}-rental-amortizacion-rate",
        date_context={"filing_period": date(year, 12, 31)},
    )
    assert value == Decimal("0.03")


@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
def test_resolver_returns_registry_value(year: int) -> None:
    assert _resolve_amortizacion_inmueble_rate(year) == Decimal("0.03")


def test_resolver_refuses_unregistered_year() -> None:
    with pytest.raises(RegistryValidationError, match="has no revision '1999'"):
        _resolve_amortizacion_inmueble_rate(1999)
