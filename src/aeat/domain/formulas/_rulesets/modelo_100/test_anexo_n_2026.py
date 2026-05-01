"""Unit tests for Modelo 100 Anexo N — deducciones autonómicas (2026).

External-anchored to LIRPF art. 46 bis + AEAT manual práctico Renta
2025 Parte 2 deducciones autonómicas.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..._engine import Engine
from .. import MODELO_100_2026

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _baseline() -> dict[str, Decimal]:
    """Zero values for every casilla — Anexo N tests overwrite per-CCAA
    aggregate inputs (1101..1115)."""
    return {
        "0001": Decimal("0.00"),
        "0008": Decimal("0.00"),
        "0009": Decimal("0.00"),
        "0010": Decimal("0.00"),
        "0019": Decimal("0.00"),
        "0020": Decimal("0.00"),
        "0021": Decimal("0.00"),
        "0022": Decimal("0.00"),
        "0028": Decimal("0.00"),
        "0029": Decimal("0.00"),
        "0030": Decimal("0.00"),
        "0031": Decimal("0.00"),
        "0032": Decimal("0.00"),
        "0035": Decimal("0.00"),
        "0048": Decimal("0.00"),
        "0049": Decimal("0.00"),
        "0061": Decimal("0.00"),
        "0066": Decimal("0.00"),
        "0072": Decimal("0.00"),
        "0078": Decimal("0.00"),
        "0085": Decimal("0.00"),
        "0106": Decimal("0.00"),
        "0107": Decimal("0.00"),
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
        "0306": Decimal("0.00"),
        "0307": Decimal("0.00"),
        "0399": Decimal("0.00"),
        "0400": Decimal("0.00"),
        "0405": Decimal("0.00"),
        "0432": Decimal("0.00"),
        "0445": Decimal("0.00"),
        "0455": Decimal("0.00"),
        "0460": Decimal("0.00"),
        "0500": Decimal("0.00"),
        "0505": Decimal("0.00"),
        "0510": Decimal("0.00"),
        "0515": Decimal("0.00"),
        "0520": Decimal("0.00"),
        "0540": Decimal("0.00"),
        "0542": Decimal("0.00"),
        "0545": Decimal("0.00"),
        "0550": Decimal("0.00"),
        "0551": Decimal("0.00"),
        "0555": Decimal("0.00"),
        "0560": Decimal("0.00"),
        "0561": Decimal("0.00"),
        "0595": Decimal("0.00"),
        "0612": Decimal("0.00"),
        "0620": Decimal("0.00"),
        "0622": Decimal("0.00"),
        "0630": Decimal("0.00"),
        "0698": Decimal("0.00"),
        "0699": Decimal("0.00"),
        "0700": Decimal("0.00"),
        "0720": Decimal("0.00"),
        "1101": Decimal("0.00"),
        "1102": Decimal("0.00"),
        "1103": Decimal("0.00"),
        "1104": Decimal("0.00"),
        "1105": Decimal("0.00"),
        "1106": Decimal("0.00"),
        "1107": Decimal("0.00"),
        "1108": Decimal("0.00"),
        "1109": Decimal("0.00"),
        "1110": Decimal("0.00"),
        "1111": Decimal("0.00"),
        "1112": Decimal("0.00"),
        "1113": Decimal("0.00"),
        "1114": Decimal("0.00"),
        "1115": Decimal("0.00"),
    }


class TestModelo100AnexoN:
    def test_zero_baseline_yields_zero_aggregate(self) -> None:
        """All 15 CCAA casillas zero -> 0622 = 0."""
        report = Engine().audit_against(
            ruleset=MODELO_100_2026,
            provided=_baseline(),
            tolerance=Decimal("0.01"),
        )
        offenders = {d.casilla_id for d in report.discrepancies}
        assert "0622" not in offenders

    @pytest.mark.parametrize(
        ("ccaa_casilla", "ccaa_name"),
        [
            ("1101", "Andalucia"),
            ("1102", "Aragon"),
            ("1108", "Castilla y Leon"),
            ("1109", "Cataluna"),
            ("1110", "Comunitat Valenciana"),
            ("1113", "Madrid"),
            ("1115", "La Rioja"),
        ],
    )
    def test_only_one_ccaa_active_per_filing(
        self,
        ccaa_casilla: str,
        ccaa_name: str,
    ) -> None:
        """Real filings have exactly one CCAA non-zero. Verify the
        aggregator correctly sums into 0622 when each CCAA is the
        active one in turn.
        """
        del ccaa_name
        provided = _baseline() | {
            ccaa_casilla: Decimal("1500.00"),
            "0622": Decimal("1500.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        offenders = {d.casilla_id for d in report.discrepancies}
        assert "0622" not in offenders

    def test_aggregate_sums_15_ccaa_inputs(self) -> None:
        """Pathological case: all 15 CCAAs non-zero (would never happen in
        a real filing — Kent has exactly one CCAA of habitual residence).
        Verifies 0622 = sum of all 15 inputs."""
        provided = _baseline() | {
            "1101": Decimal("100.00"),
            "1102": Decimal("100.00"),
            "1103": Decimal("100.00"),
            "1104": Decimal("100.00"),
            "1105": Decimal("100.00"),
            "1106": Decimal("100.00"),
            "1107": Decimal("100.00"),
            "1108": Decimal("100.00"),
            "1109": Decimal("100.00"),
            "1110": Decimal("100.00"),
            "1111": Decimal("100.00"),
            "1112": Decimal("100.00"),
            "1113": Decimal("100.00"),
            "1114": Decimal("100.00"),
            "1115": Decimal("100.00"),
            "0622": Decimal("1500.00"),  # 15 * 100
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        offenders = {d.casilla_id for d in report.discrepancies}
        assert "0622" not in offenders

    def test_drift_in_aggregate_detected(self) -> None:
        provided = _baseline() | {
            "1113": Decimal("2500.00"),  # Madrid
            "0622": Decimal("2000.00"),  # WRONG -- should be 2500
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        assert "0622" in {d.casilla_id for d in report.discrepancies}
