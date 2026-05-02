"""Cover Modelo 100 Anexo C (capital inmobiliario) for the 2024 ejercicio.

Worked examples are externally anchored to LIRPF arts. 22-24 and 85
including the post-Ley 12/2023 tiered art. 23.2 reducción, so the
suite remains independent of the ruleset's own arithmetic.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..._engine import Engine
from .. import MODELO_100_2024

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


class TestModelo100AnexoC:
    """Audit Anexo C against the 2024 ruleset using LIRPF-derived anchors."""

    def test_consistent_arrendamiento_default_50pct(self) -> None:
        """Default tier (50 %): ingresos 12.000, gastos 3.500, amortización
        1.500 -> rendimiento neto previo 7.000; reducción 50 % = 3.500;
        rendimiento neto reducido 3.500. Caller pre-computes the tier
        amount.
        """
        provided = _c_zero_b1_b2() | {
            "0061": Decimal("12000.00"),
            "0066": Decimal("3500.00"),
            "0072": Decimal("1500.00"),
            "0078": Decimal("3500.00"),  # 50 % of 7.000
            "0085": Decimal("0.00"),
            "0106": Decimal("7000.00"),
            "0107": Decimal("3500.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_rehabilitacion_60pct_tier(self) -> None:
        """60 % tier (LIRPF art. 23.2.b post Ley 12/2023): nuevas viviendas
        rehabilitadas o de nueva construcción, alquiler vivienda habitual.
        Same gross numbers as default test, but reducción = 60 % of 7.000
        = 4.200; rendimiento neto reducido 2.800.
        """
        provided = _c_zero_b1_b2() | {
            "0061": Decimal("12000.00"),
            "0066": Decimal("3500.00"),
            "0072": Decimal("1500.00"),
            "0078": Decimal("4200.00"),  # 60 % of 7.000
            "0085": Decimal("0.00"),
            "0106": Decimal("7000.00"),
            "0107": Decimal("2800.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_zona_tensionada_70pct_inquilino_joven(self) -> None:
        """70 % tier (zona tensionada, inquilino 18-35): same gross numbers
        as default test, but reducción = 70 % of 7.000 = 4.900.
        """
        provided = _c_zero_b1_b2() | {
            "0061": Decimal("12000.00"),
            "0066": Decimal("3500.00"),
            "0072": Decimal("1500.00"),
            "0078": Decimal("4900.00"),
            "0085": Decimal("0.00"),
            "0106": Decimal("7000.00"),
            "0107": Decimal("2100.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_zona_tensionada_90pct_max_reduction(self) -> None:
        """90 % tier (zona tensionada con reducción >= 5 % vs contrato anterior):
        reducción 90 % of 7.000 = 6.300; rendimiento neto reducido 700.
        """
        provided = _c_zero_b1_b2() | {
            "0061": Decimal("12000.00"),
            "0066": Decimal("3500.00"),
            "0072": Decimal("1500.00"),
            "0078": Decimal("6300.00"),
            "0085": Decimal("0.00"),
            "0106": Decimal("7000.00"),
            "0107": Decimal("700.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_negative_arrendamiento_clamps_to_zero(self) -> None:
        """When gastos + amortización exceed ingresos the rendimiento neto
        previo clamps to 0 — LIRPF art. 23 doesn't permit negative
        rendimiento del capital inmobiliario at the per-finca base.
        """
        provided = _c_zero_b1_b2() | {
            "0061": Decimal("3000.00"),
            "0066": Decimal("4000.00"),
            "0072": Decimal("1000.00"),
            "0078": Decimal("0.00"),
            "0085": Decimal("0.00"),
            "0106": Decimal("0.00"),
            "0107": Decimal("0.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_imputacion_rentas_inmobiliarias_does_not_feed_aggregation(self) -> None:
        """LIRPF art. 85 imputación (casilla 0085) is parallel income — it
        does NOT enter the 0106 / 0107 chain. Setting 0085 high should
        leave 0107 unaffected when arrendamiento is zero.
        """
        provided = _c_zero_b1_b2() | {
            "0061": Decimal("0.00"),
            "0066": Decimal("0.00"),
            "0072": Decimal("0.00"),
            "0078": Decimal("0.00"),
            "0085": Decimal("1500.00"),  # parallel income, ignored by 0106/0107
            "0106": Decimal("0.00"),
            "0107": Decimal("0.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_drift_in_rendimiento_neto_reducido_detected(self) -> None:
        """Mismatch on 0107 surfaces as a discrepancy."""
        provided = _c_zero_b1_b2() | {
            "0061": Decimal("12000.00"),
            "0066": Decimal("3500.00"),
            "0072": Decimal("1500.00"),
            "0078": Decimal("3500.00"),
            "0085": Decimal("0.00"),
            "0106": Decimal("7000.00"),
            "0107": Decimal("3000.00"),  # WRONG -- should be 3500
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        offenders = {d.casilla_id for d in report.discrepancies}
        assert "0107" in offenders


def _c_zero_b1_b2() -> dict[str, Decimal]:
    """Return zero values for every B1 + B2 casilla so the engine derives
    them as zero too. Lets C tests focus on C casilla values."""
    return {
        # Anexo B1.
        "0001": Decimal("0.00"),
        "0008": Decimal("0.00"),
        "0009": Decimal("0.00"),
        "0010": Decimal("0.00"),
        "0019": Decimal("0.00"),
        "0020": Decimal("0.00"),
        "0021": Decimal("0.00"),  # post M-1 cap fix: min(0020, max(piece_a, piece_b)) = 0 at zero rend
        "0022": Decimal("0.00"),
        # Anexo B2.
        "0028": Decimal("0.00"),
        "0029": Decimal("0.00"),
        "0030": Decimal("0.00"),
        "0031": Decimal("0.00"),
        "0032": Decimal("0.00"),
        "0035": Decimal("0.00"),
        "0048": Decimal("0.00"),
        "0049": Decimal("0.00"),
    }
