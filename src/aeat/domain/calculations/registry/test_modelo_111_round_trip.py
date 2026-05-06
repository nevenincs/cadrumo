"""Tier 1 round-trip test for modelo 111 (IRPF retenciones e ingresos a cuenta).

Modelo 111 collects worker / professional / prize / capital-gain
withholdings the autonomo has applied during the period. The 30 input
casillas split into nine income categories, each with three fields
(perceptores / base / retenciones). Two formulas roll up the totals:

- ``28`` = sum of all category retenciones casillas (03, 06, 09, 12,
  15, 18, 21, 24, 27)
- ``30`` = ``28`` - ``29`` (resultado a ingresar net of any prior-period
  adjustment)

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

# The full set of input casillas the schema expects: nine categories of
# (perceptores, base, retenciones) plus the prior-period resultado.
_ALL_INPUT_CASILLAS = (
    "01",
    "02",
    "03",  # trabajo dinerario
    "04",
    "05",
    "06",  # trabajo especie
    "07",
    "08",
    "09",  # actividades dinerario
    "10",
    "11",
    "12",  # actividades especie
    "13",
    "14",
    "15",  # premios dinerario
    "16",
    "17",
    "18",  # premios especie
    "19",
    "20",
    "21",  # ganancias dinerario
    "22",
    "23",
    "24",  # ganancias especie
    "25",
    "26",
    "27",  # derechos imagen
    "29",  # resultado de anteriores autoliquidaciones
)


def _zero_inputs() -> dict[str, Decimal]:
    return {casilla_id: Decimal("0") for casilla_id in _ALL_INPUT_CASILLAS}


def test_modelo_111_resolves_a_typical_quarterly_filing_with_workers_and_professionals() -> None:
    """An autonomo with two employees and one professional contractor in 1T."""

    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "111")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="1T")

    inputs = _zero_inputs()
    # Trabajo dinerario: 2 perceptores, 12 000 € base, 1 800 € retenciones.
    inputs["01"] = Decimal("2")
    inputs["02"] = Decimal("12000.00")
    inputs["03"] = Decimal("1800.00")
    # Actividades dinerario: 1 perceptor (a freelance professional), 5 000 €
    # base, 750 € retenciones (15 %).
    inputs["07"] = Decimal("1")
    inputs["08"] = Decimal("5000.00")
    inputs["09"] = Decimal("750.00")

    date_context = {"filing_period": date(2025, 4, 20)}

    result = calculate_registry_snapshot(snapshot, inputs=inputs, date_context=date_context)

    # 28: total retenciones = 03 + 09 = 1800 + 750 = 2550 (other categories zero).
    assert result.values["28"] == Decimal("2550.00")
    # 30: resultado a ingresar = 28 - 29 = 2550.
    assert result.values["30"] == Decimal("2550.00")


def test_modelo_111_sums_every_category_into_total_retenciones() -> None:
    """Each of the nine category retenciones casillas contributes to casilla 28."""

    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "111")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="2T")

    inputs = _zero_inputs()
    # 1 € on every category retenciones casilla so the sum is 9.
    for casilla_id in ("03", "06", "09", "12", "15", "18", "21", "24", "27"):
        inputs[casilla_id] = Decimal("1.00")

    date_context = {"filing_period": date(2025, 7, 20)}

    result = calculate_registry_snapshot(snapshot, inputs=inputs, date_context=date_context)

    assert result.values["28"] == Decimal("9.00")
    assert result.values["30"] == Decimal("9.00")


def test_modelo_111_subtracts_previous_period_resultado() -> None:
    """The resultado a ingresar (casilla 30) nets out the prior-period adjustment."""

    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "111")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2025, period="3T")

    inputs = _zero_inputs()
    inputs["01"] = Decimal("3")
    inputs["02"] = Decimal("18000.00")
    inputs["03"] = Decimal("2700.00")
    inputs["29"] = Decimal("200.00")  # 200 € over-paid in a previous autoliquidacion

    date_context = {"filing_period": date(2025, 10, 20)}

    result = calculate_registry_snapshot(snapshot, inputs=inputs, date_context=date_context)

    assert result.values["28"] == Decimal("2700.00")
    assert result.values["30"] == Decimal("2500.00")
