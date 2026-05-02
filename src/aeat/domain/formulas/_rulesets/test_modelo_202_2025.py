"""Unit tests for the Modelo 202 2025 ruleset.

Exercises the cuota-íntegra, resultado, and cantidad-a-ingresar
derivations of :data:`aeat.domain.formulas._rulesets.MODELO_202_2025`,
including the LIS art. 40.3 modalidad pago-fraccionado worked example
and a regression for the whole-percent casilla 17 normalisation.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_202_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


class TestModelo202Ruleset:
    """Formula-engine assertions for the 2025 Modelo 202 ruleset."""

    def test_consistent_instalment_is_clean(self) -> None:
        # Base 100_000 x tipo 17% = 17_000 cuota.
        # AEAT prints casilla 17 as whole-percent value:
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

    def test_external_worked_example_lis_art_40_3_modalidad(self) -> None:
        """Externally-anchored worked example for LIS art. 40.3 modalidad.

        Provenance: Ley 27/2014 (LIS) art. 40.3 párrafo 1 fixes the
        tipo de gravamen aplicable al pago fraccionado modalidad
        base-del-período-corriente at **5/7 del tipo general
        redondeado por defecto**, which resolves to **17 %** for the
        general 25 % tipo de gravamen (LIS art. 29.1: "25 por ciento
        con carácter general"). For micropymes with the Ley 31/2022
        transitional 23 % tipo, 5/7 x 23 rounds to 16 %. The general-
        tipo 17 % applies to Modelo 202 filings by sociedades not
        claiming the micropyme / new-entity régimen.

        This fixture uses the 17 % general-tipo modalidad 40.3 rate
        — NOT the rate from the ruleset's param table (there is
        none: casilla 17 is a user-supplied PDF extraction). A
        rate-swap bug in the ruleset would surface as a Decimal
        mismatch.

        Note: LIS art. 40.3 párrafo 2 does mention 23 % as an
        **importe mínimo** threshold — minimum of 23 % of positive
        P&L — for large entities > 10 M € net turnover, but this
        is a floor on the pago fraccionado, not a tipo de gravamen.
        The 17 % rate here is the derived modalidad-rate for
        ordinary sociedades under LIS 29.1 + 40.3.

        Scenario: Q2 2025 (2P) sociedad ordinaria with base 200 000
        at 17 % modalidad 40.3 rate:

        - casilla 16 (base) = 200 000.
        - casilla 17 (tipo) = 17.00 per LIS art. 40.3 (5/7 of 25 %).
        - casilla 18 (cuota íntegra) = 200 000 x 17 % = 34 000.
        - casilla 27 bonificaciones = 0.
        - casilla 28 retenciones = 2 000.
        - casilla 30 pago fraccionado anterior = 10 000 (1P).
        - casilla 32 resultado = 34 000 - 0 - 2 000 - 10 000 = 22 000.
        - casilla 33 mínimo = 20 000.
        - casilla 34 cantidad = max(32, 33) = max(22 000, 20 000) = 22 000.

        Citation: BOE-A-2014-12328 art. 40.3 párr. 1.
        """
        provided = {
            "16": Decimal("200000.00"),
            "17": Decimal("17.00"),  # 17% per LIS art. 40.3 (5/7 of 25%)
            "18": Decimal("34000.00"),
            "27": Decimal("0.00"),
            "28": Decimal("2000.00"),
            "30": Decimal("10000.00"),
            "32": Decimal("22000.00"),
            "33": Decimal("20000.00"),
            "34": Decimal("22000.00"),
        }
        report = Engine().audit_against(ruleset=MODELO_202_2025, provided=provided, tolerance=Decimal("0.01"))
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_whole_percent_casilla_17_not_treated_as_fraction(self) -> None:
        """Regression: casilla 17 = 17.00 (whole percent) must NOT yield 1.7 M €.

        The original formula was ``percent(ref("17"), ref("16"))`` which
        multiplied whole-percent * base = 100x wrong. The current formula
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
