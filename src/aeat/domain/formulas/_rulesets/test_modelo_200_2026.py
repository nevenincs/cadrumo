"""Unit tests for the Modelo 200 2026 ruleset."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_200_2025, MODELO_200_2026
from .test_modelo_200_2025 import _provided

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


class TestModelo200Ruleset2026:
    def test_ruleset_id_and_effective_range(self) -> None:
        assert MODELO_200_2026.ruleset_id == "modelo_200.2026"
        assert MODELO_200_2026.effective_from == date(2026, 1, 1)
        assert MODELO_200_2026.effective_to == date(2026, 12, 31)

    def test_2026_no_drift_from_2025_for_page_14_arithmetic(self) -> None:
        provided = _provided(
            base=Decimal("900000.00"),
            rate=Decimal("25.00"),
            cuota_liquida=Decimal("225000.00"),
            retenciones=Decimal("5000.00"),
            p1=Decimal("50000.00"),
            p2=Decimal("50000.00"),
            p3=Decimal("50000.00"),
        )
        report_2025 = Engine().audit_against(ruleset=MODELO_200_2025, provided=provided, tolerance=Decimal("0.01"))
        report_2026 = Engine().audit_against(ruleset=MODELO_200_2026, provided=provided, tolerance=Decimal("0.01"))
        assert {e.casilla_id: e.value for e in report_2025.ledger.entries} == {
            e.casilla_id: e.value for e in report_2026.ledger.entries
        }

    def test_formula_ids_use_2026_namespace(self) -> None:
        formula_00562 = MODELO_200_2026.formula_for("00562")
        formula_00611 = MODELO_200_2026.formula_for("00611")
        formula_00621 = MODELO_200_2026.formula_for("00621")
        assert formula_00562 is not None
        assert formula_00611 is not None
        assert formula_00621 is not None
        assert formula_00562.formula_id == "modelo_200.2026.cuota_integra"
        assert formula_00611.formula_id == "modelo_200.2026.cuota_diferencial"
        assert formula_00621.formula_id == "modelo_200.2026.liquido_a_ingresar"


@pytest.mark.parametrize(
    ("base", "rate", "label"),
    [
        (Decimal("1000000.00"), Decimal("25.00"), "general"),
        (Decimal("200000.00"), Decimal("23.00"), "reduced-size-transitional"),
        (Decimal("100000.00"), Decimal("15.00"), "startup"),
        (Decimal("50000.00"), Decimal("19.00"), "microempresa-2026-first-band"),
    ],
)
def test_tax_rate_split_examples_2026(base: Decimal, rate: Decimal, label: str) -> None:
    """LIS art. 29 rate examples are verified through casilla 00558."""
    del label
    provided = _provided(
        base=base,
        rate=rate,
        cuota_liquida=(base * rate / Decimal("100")).quantize(Decimal("0.01")),
    )
    report = Engine().audit_against(ruleset=MODELO_200_2026, provided=provided, tolerance=Decimal("0.01"))
    assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]


@pytest.mark.parametrize(
    ("provided", "expected"),
    [
        (
            _provided(
                base=Decimal("100000.00"),
                rate=Decimal("25.00"),
                cuota_liquida=Decimal("25000.00"),
            ),
            {"00562": Decimal("25000.00"), "00611": Decimal("25000.00"), "00621": Decimal("25000.00")},
        ),
        (
            _provided(
                base=Decimal("50000.00"),
                rate=Decimal("19.00"),
                cuota_liquida=Decimal("9500.00"),
                retenciones=Decimal("500.00"),
                p1=Decimal("1000.00"),
                p2=Decimal("1000.00"),
                p3=Decimal("1000.00"),
            ),
            {"00562": Decimal("9500.00"), "00611": Decimal("6000.00"), "00621": Decimal("6000.00")},
        ),
        (
            _provided(
                base=Decimal("125000.00"),
                rate=Decimal("15.00"),
                cuota_liquida=Decimal("18750.00"),
                abono=Decimal("250.00"),
                incremento=Decimal("100.00"),
            ),
            {"00562": Decimal("18750.00"), "00611": Decimal("18750.00"), "00621": Decimal("18600.00")},
        ),
    ],
)
def test_computed_casillas_are_cent_exact_2026(
    provided: dict[str, Decimal],
    expected: dict[str, Decimal],
) -> None:
    """Three anchored cases exercise every computed M200 casilla."""
    report = Engine().audit_against(ruleset=MODELO_200_2026, provided=provided, tolerance=Decimal("0.01"))
    assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]
    ledger = {entry.casilla_id: entry.value for entry in report.ledger.entries}
    for casilla_id, value in expected.items():
        assert ledger[casilla_id] == value
