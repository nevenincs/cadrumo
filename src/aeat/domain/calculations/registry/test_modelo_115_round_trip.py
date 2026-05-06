"""Tier 1 round-trip test for modelo 115 (IRPF retenciones sobre arrendamientos urbanos).

Modelo 115 is the simplest IRPF withholding feeder: a quarterly
declaration of withholdings landlords have applied to rental
payments. The schema has five casillas and two formulas:

- ``03`` = 19 % of the casilla ``02`` base (RD 439/2007 art. 100).
- ``05`` = ``03`` - ``04`` (the resultado a ingresar net of any
  prior-period adjustment).

Per the chain-tier-passage ADR, Tier 1 pins concrete Decimal inputs
and asserts the exact Decimal outputs the registry's formulas
produce, with no cross-modelo flow.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.core.paths import PROJECT_ROOT

from ._formula_runtime import calculate_registry_snapshot
from ._loader import load_registry_tree
from ._snapshot import build_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"


def test_modelo_115_resolves_a_simple_first_quarter_rental_withholding() -> None:
    """A landlord paid 1 000 € of rent base in 1T, with no prior-period adjustment."""

    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "115")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="1T")

    inputs = {
        "01": Decimal("1"),  # numero de perceptores
        "02": Decimal("1000.00"),  # base de retenciones
        "04": Decimal("0.00"),  # resultado de anteriores declaraciones
    }
    date_context = {"filing_period": date(2025, 4, 20)}

    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context=date_context,
    )

    # 03 = 19 % * 1000 = 190.
    assert result.values["03"] == Decimal("190.00")
    # 05 = 03 - 04 = 190.
    assert result.values["05"] == Decimal("190.00")


def test_modelo_115_subtracts_previous_period_resultado() -> None:
    """The resultado a ingresar (casilla 05) nets out the prior period's adjustment."""

    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "115")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="2T")

    inputs = {
        "01": Decimal("1"),
        "02": Decimal("2000.00"),  # 19 % * 2000 = 380
        "04": Decimal("50.00"),  # prior-period adjustment to subtract
    }
    date_context = {"filing_period": date(2025, 7, 20)}

    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context=date_context,
    )

    assert result.values["03"] == Decimal("380.00")
    assert result.values["05"] == Decimal("330.00")


def test_modelo_115_rejects_unknown_input_casilla() -> None:
    """The runtime rejects synthetic input keyed by a casilla id the schema does not declare."""

    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "115")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="1T")

    inputs = {
        "01": Decimal("1"),
        "02": Decimal("1000.00"),
        "04": Decimal("0.00"),
        "99": Decimal("0.00"),  # not declared on modelo 115
    }
    date_context = {"filing_period": date(2025, 4, 20)}

    with pytest.raises(Exception, match="unknown registry input casilla"):
        calculate_registry_snapshot(snapshot, inputs=inputs, date_context=date_context)
