"""Tier 1 round-trip test for modelo 130 (IRPF pago fraccionado, estimacion directa).

This test exercises the registry calculation runtime end-to-end for a
single revision of a single modelo: synthetic input casillas in,
formula-resolved output casillas out. No cross-modelo flow, no
multi-period aggregation. The test pins concrete Decimal inputs and
asserts the exact concrete Decimal outputs the registry's formulas
produce.

Modelo 130 is the simplest fully-formulated IRPF feeder (19 casillas,
10 formulas, one binding for the previous-year net-income lookup that
gates the rendimientos-netos minoracion). The formulas implement the
RD 439/2007 art. 110 prepayment rule:

- Direct-estimation rate is 20 % of the rendimiento neto (ingresos -
  gastos) of the period, capped at zero (no negative pago fraccionado).
- The result subtracts retenciones already withheld and pagos
  fraccionados already filed for previous quarters of the same year.
- Capital-loss-from-vivienda-habitual deductions and a minoracion
  for low net incomes (≤9 000 €) further reduce the cuota.

The Tier 1 contract (per the chain-tier-passage ADR): given a
deterministic input vector covering every input casilla, the runtime
produces a deterministic output vector matching analyst-computed
expectations.
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


def test_modelo_130_resolves_a_simple_first_quarter_estimacion_directa_filing() -> None:
    """A vanilla autonomo: 10 000 € income, 4 000 € deductible expenses, 500 € retenido in 1T."""

    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "130")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="1T")

    inputs = {
        "01": Decimal("10000.00"),  # ingresos del trimestre
        "02": Decimal("4000.00"),  # gastos deducibles del trimestre
        "05": Decimal("0.00"),  # pagos fraccionados anteriores (1T -> 0)
        "06": Decimal("500.00"),  # retenciones e ingresos a cuenta del trimestre
        "08": Decimal("0.00"),  # volumen de ingresos agrarios (no agrarian activity)
        "10": Decimal("0.00"),  # retenciones agrarias
        "15": Decimal("0.00"),  # resultados negativos de trimestres anteriores
        "16": Decimal("0.00"),  # deduccion por inversion en vivienda habitual
        "18": Decimal("0.00"),  # resultado a ingresar de autoliquidaciones anteriores
    }
    bindings = {
        # Previous-year net economic-activity income above 12 000 -> minoracion = 0.
        "irpf.previous_year_economic_activity_net_income": Decimal("30000.00"),
    }
    date_context = {"filing_period": date(2025, 4, 20)}

    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context=date_context,
        binding_values=bindings,
    )

    # 03: rendimiento neto = ingresos - gastos = 10000 - 4000 = 6000.
    assert result.values["03"] == Decimal("6000.00")
    # 04: pago fraccionado directa = max(0, 20 % * 6000) = 1200.
    assert result.values["04"] == Decimal("1200.00")
    # 07: resultado apartado I = (04 - 05) - 06 = 1200 - 0 - 500 = 700.
    assert result.values["07"] == Decimal("700.00")
    # 09: pago fraccionado agrario = 2 % * 0 = 0.
    assert result.values["09"] == Decimal("0.00")
    # 11: resultado apartado II = 09 - 10 = 0.
    assert result.values["11"] == Decimal("0.00")
    # 12: suma parciales = max(0, 07 + 11) = 700.
    assert result.values["12"] == Decimal("700.00")
    # 13: minoracion = 0 (previous-year income above the 12 000 threshold).
    assert result.values["13"] == Decimal("0.00")
    # 14: neto tras minoracion = 12 - 13 = 700.
    assert result.values["14"] == Decimal("700.00")
    # 17: diferencia = (14 - 15) - 16 = 700.
    assert result.values["17"] == Decimal("700.00")
    # 19: resultado final = 17 - 18 = 700.
    assert result.values["19"] == Decimal("700.00")


def test_modelo_130_minoracion_kicks_in_for_low_previous_year_income() -> None:
    """Previous-year net income ≤ 9 000 €: minoracion is the full 100 € allowance."""

    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "130")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="1T")

    inputs = {
        "01": Decimal("10000.00"),
        "02": Decimal("4000.00"),
        "05": Decimal("0.00"),
        "06": Decimal("500.00"),
        "08": Decimal("0.00"),
        "10": Decimal("0.00"),
        "15": Decimal("0.00"),
        "16": Decimal("0.00"),
        "18": Decimal("0.00"),
    }
    bindings = {
        # Below 9 000 -> the formula applies the full 100 € minoracion.
        "irpf.previous_year_economic_activity_net_income": Decimal("8500.00"),
    }
    date_context = {"filing_period": date(2025, 4, 20)}

    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context=date_context,
        binding_values=bindings,
    )

    # Minoracion fires: 13 = 100, dropping 14 = 12 - 100 = 600.
    assert result.values["13"] == Decimal("100.00")
    assert result.values["14"] == Decimal("600.00")
    # 17 = (14 - 15) - 16 = 600. 19 = 17 - 18 = 600.
    assert result.values["17"] == Decimal("600.00")
    assert result.values["19"] == Decimal("600.00")


def test_modelo_130_negative_results_floor_at_zero() -> None:
    """Casilla 04 floors at zero when the rendimiento neto is negative."""

    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "130")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="1T")

    inputs = {
        "01": Decimal("3000.00"),
        "02": Decimal("5000.00"),  # gastos > ingresos -> rendimiento neto < 0
        "05": Decimal("0.00"),
        "06": Decimal("0.00"),
        "08": Decimal("0.00"),
        "10": Decimal("0.00"),
        "15": Decimal("0.00"),
        "16": Decimal("0.00"),
        "18": Decimal("0.00"),
    }
    bindings = {"irpf.previous_year_economic_activity_net_income": Decimal("30000.00")}
    date_context = {"filing_period": date(2025, 4, 20)}

    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context=date_context,
        binding_values=bindings,
    )

    # 03 is genuinely negative.
    assert result.values["03"] == Decimal("-2000.00")
    # 04 floors at 0 thanks to max(0, ...).
    assert result.values["04"] == Decimal("0.00")
    # All downstream casillas roll through zero.
    assert result.values["12"] == Decimal("0.00")
    assert result.values["19"] == Decimal("0.00")
