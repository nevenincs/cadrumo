"""Tier 1 round-trip test for modelo 131 (IRPF pago fraccionado, estimacion objetiva).

Modelo 131 is the IRPF prepayment for the modulos (objective-method)
regime. Fifteen casillas, six formulas applied per revision (the
schema declares one revision per ejercicio because the modulos
parameters can shift year-over-year, but the computational shape is
identical across revisions):

- ``04`` = 2 % of ``03`` (volumen ventas sin datos-base)
- ``06`` = 2 % of ``05`` (volumen ingresos agrarios del trimestre)
- ``07`` = ``02`` + ``04`` + ``06`` (suma de pagos fraccionados previos)
- ``10`` = (``07`` - ``08``) - ``09`` (diferencia)
- ``13`` = (``10`` - ``11``) - ``12`` (total)
- ``15`` = ``13`` - ``14`` (resultado de la declaracion)

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


def test_modelo_131_resolves_a_simple_first_quarter_modulos_filing() -> None:
    """A modulos taxpayer with 200 € of own-method pago plus a 5 000 € volumen sin datos-base."""

    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "131")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="1T")

    inputs = {
        "01": Decimal("0.00"),  # suma rendimientos netos (informational)
        "02": Decimal("200.00"),  # pago fraccionado previo por datos-base
        "03": Decimal("5000.00"),  # volumen ventas sin datos-base
        "05": Decimal("0.00"),  # no agrarian volume
        "08": Decimal("0.00"),  # no retenciones
        "09": Decimal("0.00"),  # no minoracion
        "11": Decimal("0.00"),  # no prior negative
        "12": Decimal("0.00"),  # no vivienda habitual deduction
        "14": Decimal("0.00"),  # no prior autoliquidacion
    }
    date_context = {"filing_period": date(2025, 4, 20)}

    result = calculate_registry_snapshot(snapshot, inputs=inputs, date_context=date_context)

    # 04: 2 % * 5000 = 100.
    assert result.values["04"] == Decimal("100.00")
    # 06: 2 % * 0 = 0.
    assert result.values["06"] == Decimal("0.00")
    # 07: 200 + 100 + 0 = 300.
    assert result.values["07"] == Decimal("300.00")
    # 10: (300 - 0) - 0 = 300.
    assert result.values["10"] == Decimal("300.00")
    # 13: (300 - 0) - 0 = 300.
    assert result.values["13"] == Decimal("300.00")
    # 15: 300 - 0 = 300.
    assert result.values["15"] == Decimal("300.00")


def test_modelo_131_combines_data_base_modulos_pago_and_agrarian_pago() -> None:
    """A taxpayer with both modulos data-base income and agrarian volumen."""

    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "131")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="2T")

    inputs = {
        "01": Decimal("0.00"),
        "02": Decimal("150.00"),  # 150 € from datos-base modulos calculation
        "03": Decimal("3000.00"),  # 60 € from sin-datos-base (2 %)
        "05": Decimal("4500.00"),  # 90 € from agrarian (2 %)
        "08": Decimal("50.00"),  # 50 € retenciones
        "09": Decimal("0.00"),
        "11": Decimal("0.00"),
        "12": Decimal("0.00"),
        "14": Decimal("0.00"),
    }
    date_context = {"filing_period": date(2025, 7, 20)}

    result = calculate_registry_snapshot(snapshot, inputs=inputs, date_context=date_context)

    # 04 = 2% * 3000 = 60. 06 = 2% * 4500 = 90. 07 = 150 + 60 + 90 = 300.
    assert result.values["04"] == Decimal("60.00")
    assert result.values["06"] == Decimal("90.00")
    assert result.values["07"] == Decimal("300.00")
    # 10 = (300 - 50) - 0 = 250.
    assert result.values["10"] == Decimal("250.00")
    assert result.values["15"] == Decimal("250.00")


def test_modelo_131_subtracts_prior_negative_and_vivienda_deduction() -> None:
    """Casillas 11 (resultados negativos previos) and 12 (vivienda) reduce casilla 13."""

    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "131")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="3T")

    inputs = {
        "01": Decimal("0.00"),
        "02": Decimal("400.00"),
        "03": Decimal("0.00"),
        "05": Decimal("0.00"),
        "08": Decimal("0.00"),
        "09": Decimal("0.00"),
        "11": Decimal("75.00"),  # 75 € of prior-period negative
        "12": Decimal("25.00"),  # 25 € vivienda habitual deduction
        "14": Decimal("0.00"),
    }
    date_context = {"filing_period": date(2025, 10, 20)}

    result = calculate_registry_snapshot(snapshot, inputs=inputs, date_context=date_context)

    # 07 = 400 + 0 + 0 = 400. 10 = 400. 13 = (400 - 75) - 25 = 300. 15 = 300.
    assert result.values["07"] == Decimal("400.00")
    assert result.values["10"] == Decimal("400.00")
    assert result.values["13"] == Decimal("300.00")
    assert result.values["15"] == Decimal("300.00")
