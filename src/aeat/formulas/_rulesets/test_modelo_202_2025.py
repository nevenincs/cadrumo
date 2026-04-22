"""Unit tests for the Modelo 202 2025 ruleset."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_202_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


class TestModelo202Ruleset:
    def test_consistent_instalment_is_clean(self) -> None:
        # Base 100_000 x tipo 17% = 17_000 cuota.
        # AEAT prints casilla 17 as whole-percent value (wave 33 H1):
        # Decimal("17.00") is what the PDF extractor produces.
        # 27 bonificaciones 0, 28 retenciones 1_000, 30 pagos anteriores 2_000.
        # resultado = 17_000 - 0 - 1_000 - 2_000 = 14_000.
        # minimo 10_000 → cantidad = max(14_000, 10_000) = 14_000.
        provided = {
            "16": Decimal("100000.00"),
            "17": Decimal("17.00"),  # whole-percent value from PDF
            "18": Decimal("17000.00"),
            "27": Decimal("0.00"),
            "28": Decimal("1000.00"),
            "30": Decimal("2000.00"),
            "32": Decimal("14000.00"),
            "33": Decimal("10000.00"),
            "34": Decimal("14000.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_202_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_cuota_integra_mismatch_detected(self) -> None:
        # Typo: 17% of 100_000 should be 17_000, user says 16_000.
        provided = {
            "16": Decimal("100000.00"),
            "17": Decimal("17.00"),
            "18": Decimal("16000.00"),  # should be 17_000
            "27": Decimal("0.00"),
            "28": Decimal("0.00"),
            "30": Decimal("0.00"),
            "32": Decimal("16000.00"),
            "33": Decimal("0.00"),
            "34": Decimal("16000.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_202_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        assert "18" in {d.casilla_id for d in report.discrepancies}

    def test_minimum_raises_cantidad_a_ingresar(self) -> None:
        # Resultado 5_000 but minimum 8_000 ⇒ cantidad = 8_000.
        provided = {
            "16": Decimal("40000.00"),
            "17": Decimal("17.00"),
            "18": Decimal("6800.00"),
            "27": Decimal("0.00"),
            "28": Decimal("800.00"),
            "30": Decimal("1000.00"),
            "32": Decimal("5000.00"),
            "33": Decimal("8000.00"),
            "34": Decimal("8000.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_202_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_ruleset_shape(self) -> None:
        computed = {c.casilla_id for c in MODELO_202_2025.casillas if c.computed}
        assert computed == {"18", "32", "34"}
        assert len(MODELO_202_2025.formulas) == 3

    def test_whole_percent_casilla_17_not_treated_as_fraction(self) -> None:
        """Wave 33 H1 regression: casilla 17 = 17.00 (whole percent) must NOT yield 1.7M.

        Pre-fix the formula was ``percent(ref("17"), ref("16"))`` which
        multiplied whole-percent * base = 100x wrong. The post-fix formula
        ``percent(div_op(ref("17"), lit("100")), ref("16"))`` normalises
        the whole-percent value to a fraction at audit time.
        """
        provided = {
            "16": Decimal("100000.00"),
            "17": Decimal("17.00"),  # NOT 0.17 — AEAT prints whole percents
            "18": Decimal("17000.00"),  # 100_000 x 17% = 17_000 (correct)
            "27": Decimal("0.00"),
            "28": Decimal("0.00"),
            "30": Decimal("0.00"),
            "32": Decimal("17000.00"),
            "33": Decimal("0.00"),
            "34": Decimal("17000.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_202_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), (
            f"casilla 18 discrepancy: {[(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]}"
        )
