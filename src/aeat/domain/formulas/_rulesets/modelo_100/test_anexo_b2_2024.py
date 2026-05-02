"""Cover Modelo 100 Anexo B2 (capital mobiliario) for the 2024 ejercicio.

Worked examples are externally anchored to LIRPF arts. 25-26 and 101.4
plus RIRPF art. 90 so the suite remains independent of the ruleset's
own arithmetic.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..._engine import Engine
from .. import MODELO_100_2024

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


class TestModelo100AnexoB2:
    """Audit Anexo B2 against the 2024 ruleset using LIRPF-derived anchors."""

    def test_consistent_filing_is_clean(self) -> None:
        """Worked example: dividendos 2.000 + intereses 800 = 2.800 ingresos
        íntegros; gastos administración 50; rendimiento neto previo 2.750;
        sin reducción art. 26.2; rendimiento neto reducido 2.750.
        """
        provided = _b2_zero_b1_c() | {
            "0028": Decimal("2000.00"),
            "0029": Decimal("500.00"),
            "0030": Decimal("300.00"),
            "0031": Decimal("0.00"),
            "0032": Decimal("0.00"),
            "0035": Decimal("50.00"),
            "0048": Decimal("2750.00"),
            "0049": Decimal("2750.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_irregularity_reduction_applied(self) -> None:
        """Reducción art. 26.2 30 % over irregular income subtracts directly
        from rendimiento neto previo (caller-supplied as 0032).
        """
        provided = _b2_zero_b1_c() | {
            "0028": Decimal("10000.00"),
            "0029": Decimal("0.00"),
            "0030": Decimal("0.00"),
            "0031": Decimal("0.00"),
            "0032": Decimal("3000.00"),
            "0035": Decimal("0.00"),
            "0048": Decimal("10000.00"),
            "0049": Decimal("7000.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_gastos_exceed_ingresos_clamps_to_zero(self) -> None:
        """Gastos administración exceed ingresos -> rendimiento neto previo = 0."""
        provided = _b2_zero_b1_c() | {
            "0028": Decimal("100.00"),
            "0029": Decimal("0.00"),
            "0030": Decimal("0.00"),
            "0031": Decimal("0.00"),
            "0032": Decimal("0.00"),
            "0035": Decimal("500.00"),
            "0048": Decimal("0.00"),
            "0049": Decimal("0.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_drift_in_rendimiento_neto_previo_detected(self) -> None:
        """Mismatch on 0048 surfaces as a discrepancy."""
        provided = _b2_zero_b1_c() | {
            "0028": Decimal("1000.00"),
            "0029": Decimal("500.00"),
            "0030": Decimal("0.00"),
            "0031": Decimal("0.00"),
            "0032": Decimal("0.00"),
            "0035": Decimal("100.00"),
            "0048": Decimal("1300.00"),  # WRONG -- should be 1400
            "0049": Decimal("1300.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        offenders = {d.casilla_id for d in report.discrepancies}
        assert "0048" in offenders


def _b2_zero_b1_c() -> dict[str, Decimal]:
    """Return zero values for every B1 + C casilla so the engine derives
    them as zero too. Lets B2 tests focus on B2 casilla values without
    cross-anexo noise."""
    return {
        # Anexo B1 inputs/computed.
        "0001": Decimal("0.00"),
        "0008": Decimal("0.00"),
        "0009": Decimal("0.00"),
        "0010": Decimal("0.00"),
        "0019": Decimal("0.00"),
        "0020": Decimal("0.00"),
        "0021": Decimal("0.00"),  # post M-1 cap fix: min(0020, max(piece_a, piece_b)) = 0 at zero rend
        "0022": Decimal("0.00"),
        # Anexo C inputs/computed.
        "0061": Decimal("0.00"),
        "0066": Decimal("0.00"),
        "0072": Decimal("0.00"),
        "0078": Decimal("0.00"),
        "0085": Decimal("0.00"),
        "0106": Decimal("0.00"),
        "0107": Decimal("0.00"),
    }
