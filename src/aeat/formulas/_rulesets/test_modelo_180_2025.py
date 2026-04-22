"""Unit tests for the Modelo 180 2025 ruleset."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_180_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


class TestModelo180Ruleset:
    def test_consistent_annual_is_clean(self) -> None:
        # 02 = 60_000, 03 = 19% = 11_400, 04 ingresos especie = 0.
        provided = {
            "01": Decimal("5"),
            "02": Decimal("60000.00"),
            "03": Decimal("11400.00"),
            "04": Decimal("0.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_180_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_retention_rate_mismatch(self) -> None:
        # User enters 18% retention by mistake.
        provided = {
            "01": Decimal("5"),
            "02": Decimal("60000.00"),
            "03": Decimal("10800.00"),  # 18% — wrong
            "04": Decimal("0.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_180_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        assert "03" in {d.casilla_id for d in report.discrepancies}

    def test_ruleset_shape(self) -> None:
        computed = {c.casilla_id for c in MODELO_180_2025.casillas if c.computed}
        assert computed == {"03"}
        assert len(MODELO_180_2025.formulas) == 1

    def test_ingresos_especie_preserves_04(self) -> None:
        """Casilla 04 (ingresos a cuenta en especie) is user-input, not computed.

        Wave 52 M6 expansion: pre-wave the test suite didn't exercise 04 at all.
        """
        provided = {
            "01": Decimal("3"),
            "02": Decimal("30000.00"),
            "03": Decimal("5700.00"),  # 30000 * 0.19
            "04": Decimal("250.00"),  # in-kind payments on account
        }
        report = Engine().audit_against(ruleset=MODELO_180_2025, provided=provided, tolerance=Decimal("0.01"))
        assert report.is_clean()

    def test_zero_base_yields_zero_retencion(self) -> None:
        """Boundary: 0€ base ⇒ 0€ retención."""
        provided = {
            "01": Decimal("0"),
            "02": Decimal("0.00"),
            "03": Decimal("0.00"),
            "04": Decimal("0.00"),
        }
        report = Engine().audit_against(ruleset=MODELO_180_2025, provided=provided, tolerance=Decimal("0.01"))
        assert report.is_clean()
