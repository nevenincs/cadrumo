"""Tier 1 round-trip test for modelo 123 (retenciones sobre capital mobiliario).

Modelo 123 is the capital-mobiliario withholding feeder. The
withholding agent (typically a bank) reports per-perceptor
withholdings split into two categories — dividendos / participaciones
and resto de rentas — and the registry sums them into totals plus a
final resultado a ingresar.

Five formulas, all pure sums or subtractions, no parameter rates or
external bindings:

- ``03`` = ``01`` + ``02`` (total perceptores)
- ``06`` = ``04`` + ``05`` (total base)
- ``09`` = ``07`` + ``08`` (total retenciones)
- ``12`` = ``09`` + ``11`` (suma retenciones + regularizacion)
- ``14`` = ``12`` - ``13`` (resultado a ingresar)

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


def test_modelo_123_resolves_a_simple_first_quarter_capital_mobiliario_filing() -> None:
    """A bank withholds on dividends and on bond interest in 1T."""

    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "123")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="1T")

    inputs = {
        "01": Decimal("3"),  # perceptores dividendos
        "02": Decimal("2"),  # perceptores resto
        "04": Decimal("1500.00"),  # base dividendos
        "05": Decimal("1000.00"),  # base resto
        "07": Decimal("285.00"),  # retenciones dividendos (19 % * 1500 already withheld)
        "08": Decimal("190.00"),  # retenciones resto (19 % * 1000 already withheld)
        "10": Decimal("0.00"),  # ingresos de ejercicios anteriores
        "11": Decimal("0.00"),  # regularizacion
        "13": Decimal("0.00"),  # resultado de anteriores autoliquidaciones
    }
    date_context = {"filing_period": date(2025, 4, 20)}

    result = calculate_registry_snapshot(snapshot, inputs=inputs, date_context=date_context)

    # 03: total perceptores = 3 + 2 = 5.
    assert result.values["03"] == Decimal("5")
    # 06: total base = 1500 + 1000 = 2500.
    assert result.values["06"] == Decimal("2500.00")
    # 09: total retenciones = 285 + 190 = 475.
    assert result.values["09"] == Decimal("475.00")
    # 12: suma con regularizacion = 09 + 11 = 475 + 0 = 475.
    assert result.values["12"] == Decimal("475.00")
    # 14: resultado a ingresar = 12 - 13 = 475.
    assert result.values["14"] == Decimal("475.00")


def test_modelo_123_applies_regularizacion_and_prior_resultado() -> None:
    """A regularizacion adjustment plus a previous-autoliquidation residual."""

    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "123")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="2T")

    inputs = {
        "01": Decimal("2"),
        "02": Decimal("1"),
        "04": Decimal("1000.00"),
        "05": Decimal("500.00"),
        "07": Decimal("190.00"),
        "08": Decimal("95.00"),
        "10": Decimal("0.00"),
        "11": Decimal("25.00"),  # regularizacion +25 €
        "13": Decimal("100.00"),  # 100 € from previous autoliquidacion
    }
    date_context = {"filing_period": date(2025, 7, 20)}

    result = calculate_registry_snapshot(snapshot, inputs=inputs, date_context=date_context)

    # 09 = 190 + 95 = 285.
    assert result.values["09"] == Decimal("285.00")
    # 12 = 09 + 11 = 285 + 25 = 310.
    assert result.values["12"] == Decimal("310.00")
    # 14 = 12 - 13 = 310 - 100 = 210.
    assert result.values["14"] == Decimal("210.00")
