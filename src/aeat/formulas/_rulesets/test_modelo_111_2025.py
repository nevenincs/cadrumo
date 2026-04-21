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
            "09": Decimal("0.00"),
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
            "09": Decimal("0.00"),
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
            "09": Decimal("0.00"),
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

    def test_ruleset_exposes_nine_casillas(self) -> None:
        assert len(MODELO_111_2025.casillas) == 9
        computed = {c.casilla_id for c in MODELO_111_2025.casillas if c.computed}
        assert computed == {"28", "30"}
