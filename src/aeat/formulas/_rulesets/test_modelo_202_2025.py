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

    def test_external_worked_example_lis_art_29_micropyme(self) -> None:
        """External-anchored worked example (wave 59c H3 closure).

        Provenance: Ley 27/2014 (LIS) art. 29.1 fixes the tipo de
        gravamen for micropymes at 23% (since Orden HAC/262/2025).
        The ruleset reads the rate from casilla 17 (whole-percent),
        so this fixture sets 17=23.00 per LIS art. 29.1.

        Scenario: Q2 2025 (2P) micropyme with base 200 000 at 23%:
        - casilla 16 (base) = 200 000.
        - casilla 17 (tipo) = 23.00 per LIS art. 29.1.
        - casilla 18 (cuota integra) = 200 000 x 23% = 46 000.
        - casilla 27 bonificaciones = 0.
        - casilla 28 retenciones = 2 000.
        - casilla 30 pago fraccionado anterior = 10 000 (1P).
        - casilla 32 resultado = 46 000 - 0 - 2 000 - 10 000 = 34 000.
        - casilla 33 minimo = 20 000.
        - casilla 34 cantidad = max(32, 33) = 34 000.

        Citation: BOE-A-2014-12328 art. 29.1.
        """
        provided = {
            "16": Decimal("200000.00"),
            "17": Decimal("23.00"),  # 23% per LIS art. 29.1, NOT from ruleset
            "18": Decimal("46000.00"),
            "27": Decimal("0.00"),
            "28": Decimal("2000.00"),
            "30": Decimal("10000.00"),
            "32": Decimal("34000.00"),
            "33": Decimal("20000.00"),
            "34": Decimal("34000.00"),
        }
        report = Engine().audit_against(ruleset=MODELO_202_2025, provided=provided, tolerance=Decimal("0.01"))
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

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
