"""Unit tests for the Modelo 111 2025 ruleset."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_111_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]


class TestModelo111Ruleset:
    def test_consistent_sum_and_resultado_is_clean(self) -> None:
        provided = {
            "03": Decimal("5000.00"),  # trabajo
            "06": Decimal("3000.00"),  # actividades
            "08": Decimal("0.00"),
            "09": Decimal("0.00"),
            "11": Decimal("0.00"),
            "12": Decimal("0.00"),
            "15": Decimal("0.00"),
            "18": Decimal("0.00"),
            "28": Decimal("8000.00"),
            "29": Decimal("0.00"),
            "30": Decimal("8000.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_111_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_sum_mismatch_surfaces_discrepancy(self) -> None:
        # Kent forgets to carry 5000 + 3000 → reports 7000.
        provided = {
            "03": Decimal("5000.00"),
            "06": Decimal("3000.00"),
            "08": Decimal("0.00"),
            "09": Decimal("0.00"),
            "11": Decimal("0.00"),
            "12": Decimal("0.00"),
            "15": Decimal("0.00"),
            "18": Decimal("0.00"),
            "28": Decimal("7000.00"),  # bug: actual 8000
            "29": Decimal("0.00"),
            "30": Decimal("7000.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_111_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        offenders = {d.casilla_id for d in report.discrepancies}
        assert "28" in offenders

    def test_resultado_subtracts_negative_carryover(self) -> None:
        provided = {
            "03": Decimal("2000.00"),
            "06": Decimal("0.00"),
            "08": Decimal("0.00"),
            "09": Decimal("0.00"),
            "11": Decimal("0.00"),
            "12": Decimal("0.00"),
            "15": Decimal("0.00"),
            "18": Decimal("0.00"),
            "28": Decimal("2000.00"),
            "29": Decimal("300.00"),
            "30": Decimal("1700.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_111_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_ruleset_exposes_fixed_rate_formulas(self) -> None:
        # Wave 29 HIGH-2: fixed-rate retentions on premios (casilla 09) and
        # arrendamientos-ganancias (casilla 12) at 19% are now verified.
        assert len(MODELO_111_2025.casillas) == 11
        computed = {c.casilla_id for c in MODELO_111_2025.casillas if c.computed}
        assert computed == {"09", "12", "28", "30"}

    def test_premios_retention_at_19pct(self) -> None:
        # 8000 premios x 19% = 1520 retencion.
        provided = {
            "03": Decimal("0.00"),
            "06": Decimal("0.00"),
            "08": Decimal("8000.00"),
            "09": Decimal("1520.00"),
            "11": Decimal("0.00"),
            "12": Decimal("0.00"),
            "15": Decimal("0.00"),
            "18": Decimal("0.00"),
            "28": Decimal("1520.00"),
            "29": Decimal("0.00"),
            "30": Decimal("1520.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_111_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_premios_retention_typo_detected(self) -> None:
        # Kent enters 1400 instead of 1520 — 120€ off the expected 19%.
        provided = {
            "03": Decimal("0.00"),
            "06": Decimal("0.00"),
            "08": Decimal("8000.00"),
            "09": Decimal("1400.00"),  # should be 1520
            "11": Decimal("0.00"),
            "12": Decimal("0.00"),
            "15": Decimal("0.00"),
            "18": Decimal("0.00"),
            "28": Decimal("1400.00"),
            "29": Decimal("0.00"),
            "30": Decimal("1400.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_111_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        offenders = {d.casilla_id for d in report.discrepancies}
        assert "09" in offenders
