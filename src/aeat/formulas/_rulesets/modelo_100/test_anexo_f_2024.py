"""Unit tests for Modelo 100 Anexo F (2024).

External-anchored to LIRPF arts. 47-61 and 84.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..._engine import Engine
from .. import MODELO_100_2024

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


def _baseline() -> dict[str, Decimal]:
    """Zero values for every casilla — Anexo F tests overwrite the
    relevant subset; engine derives the computed casillas accordingly."""
    return {
        # B1.
        "0001": Decimal("0.00"),
        "0008": Decimal("0.00"),
        "0009": Decimal("0.00"),
        "0010": Decimal("0.00"),
        "0019": Decimal("0.00"),
        "0020": Decimal("0.00"),
        "0021": Decimal("0.00"),  # post M-1 cap
        "0022": Decimal("0.00"),
        # B2.
        "0028": Decimal("0.00"),
        "0029": Decimal("0.00"),
        "0030": Decimal("0.00"),
        "0031": Decimal("0.00"),
        "0032": Decimal("0.00"),
        "0035": Decimal("0.00"),
        "0048": Decimal("0.00"),
        "0049": Decimal("0.00"),
        # C.
        "0061": Decimal("0.00"),
        "0066": Decimal("0.00"),
        "0072": Decimal("0.00"),
        "0078": Decimal("0.00"),
        "0085": Decimal("0.00"),
        "0106": Decimal("0.00"),
        "0107": Decimal("0.00"),
        # D normal / simplificada / modulos.
        "0140": Decimal("0.00"),
        "0150": Decimal("0.00"),
        "0155": Decimal("0.00"),
        "0165": Decimal("0.00"),
        "0170": Decimal("0.00"),
        "0173": Decimal("0.00"),
        "0180": Decimal("0.00"),
        "0190": Decimal("0.00"),
        "0195": Decimal("0.00"),
        "0200": Decimal("0.00"),
        "0205": Decimal("0.00"),
        "0210": Decimal("0.00"),
        "0215": Decimal("0.00"),
        "0220": Decimal("0.00"),
        "0225": Decimal("0.00"),
        "0230": Decimal("0.00"),
        "0235": Decimal("0.00"),
        "0240": Decimal("0.00"),
        "0250": Decimal("0.00"),
        "0255": Decimal("0.00"),
        "0260": Decimal("0.00"),
        # E.
        "0306": Decimal("0.00"),
        "0307": Decimal("0.00"),
        "0399": Decimal("0.00"),
        "0400": Decimal("0.00"),
        "0405": Decimal("0.00"),
        # F.
        "0432": Decimal("0.00"),
        "0445": Decimal("0.00"),
        "0455": Decimal("0.00"),
        "0460": Decimal("0.00"),
        "0500": Decimal("0.00"),
        "0505": Decimal("0.00"),
        "0510": Decimal("0.00"),
        "0515": Decimal("0.00"),
        "0520": Decimal("0.00"),
        "0545": Decimal("0.00"),
        "0555": Decimal("0.00"),
    }


class TestModelo100AnexoF:
    def test_base_imponible_general_aggregates_per_anexo(self) -> None:
        """BIG = 0022 (B1) + 0107 (C) + 0085 (C) + 0205 (D normal) +
        0240 (D simpl.) + 0260 (D modulos) + 0399 (E general).

        Worked input chain:
          B1 input 0001=30000 -> 0020=30000, 0021=0 (rendimiento > 19747.50),
          0022=30000.
          C inputs 0061=4000, 0066=500 -> 0106=3500, 0107=3500.
          C 0085=500 (imputacion, input only).
          BIG = 30000 + 3500 + 500 + 0 + 0 + 0 + 0 = 34000.
        """
        provided = _baseline() | {
            # B1 chain.
            "0001": Decimal("30000.00"),
            "0020": Decimal("30000.00"),
            "0021": Decimal("0.00"),
            "0022": Decimal("30000.00"),
            # C chain.
            "0061": Decimal("4000.00"),
            "0066": Decimal("500.00"),
            "0106": Decimal("3500.00"),
            "0107": Decimal("3500.00"),
            "0085": Decimal("500.00"),
            # BIG aggregation.
            "0432": Decimal("34000.00"),
            "0545": Decimal("34000.00"),  # BLG = BIG (no reductions)
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_base_imponible_ahorro_aggregates_b2_plus_e(self) -> None:
        """BIA = 0049 (B2) + 0400 (E ahorro). Worked chain: 0028=2750, 0035=0
        -> 0048=2750, 0049=2750. 0400=1250. BIA=4000. BLA=4000.
        """
        provided = _baseline() | {
            "0028": Decimal("2750.00"),
            "0048": Decimal("2750.00"),
            "0049": Decimal("2750.00"),
            "0400": Decimal("1250.00"),
            "0460": Decimal("4000.00"),
            "0555": Decimal("4000.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_minimo_personal_familiar_aggregation(self) -> None:
        """0500 = 0505 + 0510 + 0515 + 0520. Worked example: contribuyente
        soltero 30 anos sin descendientes / ascendientes / discapacidad ->
        minimo 5.550 EUR; total = 5.550."""
        provided = _baseline() | {
            "0505": Decimal("5550.00"),
            "0510": Decimal("0.00"),
            "0515": Decimal("0.00"),
            "0520": Decimal("0.00"),
            "0500": Decimal("5550.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_minimo_familia_with_two_children_under_3(self) -> None:
        """Worked example: contribuyente con 2 hijos (1 menor de 3 anos)
        sin ascendientes ni discapacidad. LIRPF art. 58:
        - 1er descendiente: 2.400 EUR + 2.800 EUR menor 3 = 5.200
        - 2o descendiente: 2.700 EUR
        Total 0510 = 7.900 EUR. Total 0500 = 5.550 + 7.900 = 13.450 EUR.
        """
        provided = _baseline() | {
            "0505": Decimal("5550.00"),
            "0510": Decimal("7900.00"),
            "0515": Decimal("0.00"),
            "0520": Decimal("0.00"),
            "0500": Decimal("13450.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_base_liquidable_general_with_pension_plan_reduction(self) -> None:
        """BIG 30.000; aporta 1.500 EUR a plan de pensiones (LIRPF art. 51 + 52
        cap general); reduccion conjunta 0; BLG = clamp_pos(30.000 - 1.500 - 0)
        = 28.500. B1 chain: 0001=30000 -> 0022=30000 (0021=0 since
        rendimiento > 19747.50).
        """
        provided = _baseline() | {
            "0001": Decimal("30000.00"),
            "0020": Decimal("30000.00"),
            "0021": Decimal("0.00"),
            "0022": Decimal("30000.00"),
            "0432": Decimal("30000.00"),
            "0445": Decimal("1500.00"),
            "0545": Decimal("28500.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_base_liquidable_general_clamps_to_zero_when_reductions_exceed(self) -> None:
        """Reducciones > BIG -> BLG clamps to 0. B1 chain: 0001=12000
        -> 0020=12000, 0021=7302 (cap), 0022=4698. BIG=4698.
        """
        provided = _baseline() | {
            "0001": Decimal("12000.00"),
            "0020": Decimal("12000.00"),
            "0021": Decimal("7302.00"),
            "0022": Decimal("4698.00"),
            "0432": Decimal("4698.00"),
            "0445": Decimal("4000.00"),
            "0455": Decimal("3400.00"),
            "0545": Decimal("0.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_base_liquidable_ahorro_passthrough(self) -> None:
        """Default BLA = BIA (no per-anexo reducciones at this layer).
        B2 chain: 0028=4000, 0035=0 -> 0048=4000, 0049=4000. 0400=1000.
        BIA=5000. BLA=5000.
        """
        provided = _baseline() | {
            "0028": Decimal("4000.00"),
            "0048": Decimal("4000.00"),
            "0049": Decimal("4000.00"),
            "0400": Decimal("1000.00"),
            "0460": Decimal("5000.00"),
            "0555": Decimal("5000.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_drift_in_minimo_aggregation_detected(self) -> None:
        provided = _baseline() | {
            "0505": Decimal("5550.00"),
            "0510": Decimal("2400.00"),
            "0515": Decimal("0.00"),
            "0520": Decimal("0.00"),
            "0500": Decimal("8000.00"),  # WRONG -- should be 7950
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        assert "0500" in {d.casilla_id for d in report.discrepancies}
