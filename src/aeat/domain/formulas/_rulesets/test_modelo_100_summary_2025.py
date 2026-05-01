"""Unit tests for the Modelo 100 summary-block ruleset.

Wave 48 stream 4 H4 coverage gap: the Modelo 100 summary ruleset was
the first ruleset shipped (wave 10) and had only borrador-integration
coverage. Dedicated formula-engine unit tests live here.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_100_SUMMARY_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _provided() -> dict[str, Decimal]:
    """Worked example: Kent general base 20 000 €, savings base 5 000 €.

    Values chosen so every formula output is independently derivable
    from the input arithmetic (no tautology with the ruleset's own
    formulas):

    - 0595 (cuota íntegra total) = 0550 + 0551 + 0560 + 0561
      = 1900 + 1900 + 475 + 475 = 4750.
    - 0630 (total deducciones) = 0620 + 0622 = 600 + 0 = 600.
    - 0698 (cuota líquida) = max(0, 0595 - 0630) = max(0, 4150) = 4150.
    - 0720 (cuota resultante) = 0698 - 0699 - 0700 = 4150 - 400 - 50 = 3700.
    """
    return {
        # Base components of cuota íntegra: two estatal + two autonómica halves.
        "0550": Decimal("1900.00"),
        "0551": Decimal("1900.00"),
        "0560": Decimal("475.00"),
        "0561": Decimal("475.00"),
        "0595": Decimal("4750.00"),
        # Deducciones.
        "0620": Decimal("600.00"),
        "0622": Decimal("0.00"),
        "0630": Decimal("600.00"),
        # Post-deduction chain.
        "0698": Decimal("4150.00"),
        "0699": Decimal("400.00"),  # retenciones
        "0700": Decimal("50.00"),  # pagos a cuenta
        "0720": Decimal("3700.00"),
    }


class TestModelo100SummaryRuleset:
    def test_ruleset_id_and_variant(self) -> None:
        """Wave 47: Modelo 100 summary uses the ``variant='summary'`` slot."""
        assert MODELO_100_SUMMARY_2025.ruleset_id == "modelo_100.summary.2025"
        assert MODELO_100_SUMMARY_2025.variant == "summary"

    def test_consistent_filing_is_clean(self) -> None:
        report = Engine().audit_against(
            ruleset=MODELO_100_SUMMARY_2025,
            provided=_provided(),
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_cuota_integra_sum_detects_typo(self) -> None:
        """0595 = 0550 + 0551 + 0560 + 0561. Kent's sum off by 50€."""
        provided = _provided()
        provided["0595"] = Decimal("4700.00")  # should be 4750
        report = Engine().audit_against(
            ruleset=MODELO_100_SUMMARY_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        assert "0595" in {d.casilla_id for d in report.discrepancies}

    def test_cuota_liquida_clamps_negative_to_zero(self) -> None:
        """0698 = max(0, 0595 - 0630). When deductions exceed integra, 0698 is 0."""
        provided = _provided()
        # Push deducciones above integra so the clamp triggers.
        provided["0620"] = Decimal("5000.00")  # big deduction
        provided["0630"] = Decimal("5000.00")  # = 0620 + 0622
        provided["0698"] = Decimal("0.00")  # clamp to zero
        # Downstream values consistent with the clamped value.
        provided["0720"] = Decimal("-450.00")  # 0 - 400 - 50
        report = Engine().audit_against(
            ruleset=MODELO_100_SUMMARY_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_resultado_subtracts_retenciones_and_pagos(self) -> None:
        """0720 = 0698 - 0699 - 0700."""
        provided = _provided()
        provided["0720"] = Decimal("3800.00")  # wrong — should be 3700
        report = Engine().audit_against(
            ruleset=MODELO_100_SUMMARY_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert "0720" in {d.casilla_id for d in report.discrepancies}

    def test_ruleset_shape(self) -> None:
        computed = {c.casilla_id for c in MODELO_100_SUMMARY_2025.casillas if c.computed}
        assert computed == {"0595", "0630", "0698", "0720"}
        assert len(MODELO_100_SUMMARY_2025.formulas) == 4

    def test_external_worked_example_lirpf_art_62_and_73(self) -> None:
        """External anchor per Ley IRPF (Ley 35/2006) arts. 62, 73, 67, 77, 79, 99.

        Plain-text titles (BOE-A-2006-20764 consolidated text, retrieval
        2026-04-22):
          - art. 62 = "Cuota íntegra estatal" (tarifa general + tarifa
            ahorro, estatal half)
          - art. 73 = "Cuota íntegra autonómica" (mirror on the
            autonomous half; art. 74 carries the autonomous tarifa)
          - art. 67 = "Cuota líquida estatal"
          - art. 77 = "Cuota líquida autonómica total"
          - art. 79 = "Cuota diferencial"
          - art. 99 = "Obligación de practicar pagos a cuenta"

        Modelo 100 summary-block mapping:
          - 0595 (cuota íntegra total) = art. 62 + art. 73
          - 0698 (cuota líquida) = art. 67 + art. 77
          - 0720 (cuota diferencial) = art. 79, with the art. 99
            pagos-a-cuenta subtraction

        Citation-accuracy history (tracked for auditability):
         - Wave 61c originally cited art. 103 for the cuota diferencial
           — WRONG (art. 103 is "Liquidaciones provisionales"). Corrected
           in wave 63a to 79 + 99.
         - Wave 63a cited art. 77 for cuota íntegra autonómica — WRONG
           (art. 77 is "Cuota líquida autonómica total", post-deduction).
           Corrected in wave 65a to art. 73.
         - Wave 65a cited art. 67 for cuota íntegra estatal — WRONG
           (art. 67 is "Cuota líquida estatal"). Corrected in wave 67a
           to art. 62. Wave 65a also cited art. 79 for "cuota líquida
           total" — WRONG (art. 79 is "Cuota diferencial"; cuota líquida
           total splits across arts. 67 + 77). Wave 67a untangles this.
           Fixture arithmetic unchanged throughout; only statutory
           pointers update.

        The summary ruleset is a pure aggregator (no rate-bearing formulas,
        empty ParameterTable per the ADR §4 canonical pattern) so the
        external anchor asserts the summation arithmetic mandated by LIRPF
        is correctly reproduced.

        Scenario: Kent 2025 renta — distinct numeric profile from ``_provided()``:
          - Base general: 0550 estatal 3 150, 0551 autonómica 3 150
            (cuota íntegra estatal + autonómica por base general).
          - Base del ahorro: 0560 estatal 190, 0561 autonómica 190
            (cuota íntegra por base del ahorro al primer tramo 19%).
          - 0595 (LIRPF art. 62 + 73): 3 150 + 3 150 + 190 + 190 = 6 680,00.
          - Deducciones: 0620 vivienda habitual 1 200, 0622 donaciones 80.
          - 0630 (general deducciones estatal + autonómicas): 1 200 + 80 = 1 280,00.
          - 0698 (LIRPF art. 67 + 77 cuota líquida): max(0, 6 680 - 1 280) = 5 400,00.
          - 0699 retenciones 800, 0700 pagos a cuenta 125 (LIRPF art. 99).
          - 0720 (LIRPF art. 79 cuota diferencial): 5 400 - 800 - 125 = 4 475,00.
        """
        provided = {
            "0550": Decimal("3150.00"),
            "0551": Decimal("3150.00"),
            "0560": Decimal("190.00"),
            "0561": Decimal("190.00"),
            "0595": Decimal("6680.00"),
            "0620": Decimal("1200.00"),
            "0622": Decimal("80.00"),
            "0630": Decimal("1280.00"),
            "0698": Decimal("5400.00"),
            "0699": Decimal("800.00"),
            "0700": Decimal("125.00"),
            "0720": Decimal("4475.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_SUMMARY_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]
