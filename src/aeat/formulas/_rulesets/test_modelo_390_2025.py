"""Unit tests for the Modelo 390 2025 IVA annual-resumen ruleset."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_390_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def _provided() -> dict[str, Decimal]:
    """A consistent 2025 filing for an autónomo on régimen general."""
    # 96 cuotas repercutidas = 10_000
    # 100 IVA interior deducible = 2_000
    # 101 IVA importaciones deducible = 500
    # 104 = 100 + 101 = 2_500
    # 105 = 96 - 104 = 7_500
    # 108 simplificado = 0, 109 otros = 0
    # 190 = 105 + 108 + 109 = 7_500
    return {
        "96": Decimal("10000.00"),
        "100": Decimal("2000.00"),
        "101": Decimal("500.00"),
        "104": Decimal("2500.00"),
        "105": Decimal("7500.00"),
        "108": Decimal("0.00"),
        "109": Decimal("0.00"),
        "190": Decimal("7500.00"),
    }


class TestModelo390Ruleset:
    def test_consistent_filing_is_clean(self) -> None:
        report = Engine().audit_against(
            ruleset=MODELO_390_2025,
            provided=_provided(),
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_iva_deducible_sum(self) -> None:
        """104 = 100 + 101."""
        provided = _provided()
        provided["104"] = Decimal("2000.00")  # forgot importaciones (wrong: should be 2500)
        report = Engine().audit_against(
            ruleset=MODELO_390_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        assert "104" in {d.casilla_id for d in report.discrepancies}

    def test_resultado_regimen_general(self) -> None:
        """105 = 96 - 104. Kent double-subtracts."""
        provided = _provided()
        provided["105"] = Decimal("5000.00")  # wrong: should be 7500
        report = Engine().audit_against(
            ruleset=MODELO_390_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        assert "105" in {d.casilla_id for d in report.discrepancies}

    def test_suma_resultado_with_regimenes(self) -> None:
        """190 = 105 + 108 + 109."""
        provided = _provided()
        provided["108"] = Decimal("1000.00")  # simplificado contributes
        provided["109"] = Decimal("200.00")  # otros contributes
        provided["190"] = Decimal("8700.00")  # 7500 + 1000 + 200
        report = Engine().audit_against(
            ruleset=MODELO_390_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_ruleset_shape(self) -> None:
        computed = {c.casilla_id for c in MODELO_390_2025.casillas if c.computed}
        assert computed == {"104", "105", "190"}
        assert len(MODELO_390_2025.formulas) == 3

    def test_external_worked_example_liva_resumen_anual(self) -> None:
        """External-anchored worked example (wave 59c H3 closure).

        Provenance: Ley 37/1992 (LIVA) arts. 92-99 establish the IVA
        soportado deducible framework. Modelo 390 is the annual
        resumen that rolls up the quarterly 303 filings per AEAT
        Instrucciones Modelo 390.

        Scenario: Kent's 2025 annual resumen:
        - 96 cuotas repercutidas = 42 000 (Modelo 390's own annual
          sub-totals, not a direct sum of quarterly 303 casillas).
        - 100 IVA soportado interior = 8 500.
        - 101 IVA soportado importaciones = 1 500.
        - 104 total IVA soportado = 100 + 101 = 10 000 per AEAT instr.
        - 105 resultado régimen general = 96 - 104 = 32 000.
        - 108/109 otros regímenes = 0.
        - 190 suma resultado = 105 + 108 + 109 = 32 000.

        Citation: BOE-A-1992-28740 arts. 92-99 (LIVA deducciones).
        """
        provided = {
            "96": Decimal("42000.00"),
            "100": Decimal("8500.00"),
            "101": Decimal("1500.00"),
            "104": Decimal("10000.00"),  # 100 + 101 per AEAT instr.
            "105": Decimal("32000.00"),
            "108": Decimal("0.00"),
            "109": Decimal("0.00"),
            "190": Decimal("32000.00"),
        }
        report = Engine().audit_against(ruleset=MODELO_390_2025, provided=provided, tolerance=Decimal("0.01"))
        assert report.is_clean()
