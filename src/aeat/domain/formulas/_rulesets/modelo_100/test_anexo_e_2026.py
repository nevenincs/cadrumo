"""Unit tests for Modelo 100 Anexo E (ejercicio 2026).

Exercises ganancias y pérdidas patrimoniales derivations of
:data:`aeat.domain.formulas._rulesets.MODELO_100_2026` against worked
inputs anchored to LIRPF arts. 33-39.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..._engine import Engine
from .. import MODELO_100_2026

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _baseline() -> dict[str, Decimal]:
    """Return zero values for every casilla used in Anexo E tests.

    Tests overwrite the relevant subset; the engine then derives the
    computed casillas accordingly.

    Returns:
        Mapping of casilla id to ``Decimal("0.00")``.
    """
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


class TestModelo100AnexoE:
    """Cover the saldo patrimonial derivation in Anexo E (LIRPF arts. 33-39)."""

    def test_consistent_saldo_patrimonial(self) -> None:
        """Ganancias 5.000, pérdidas 1.500 -> saldo neto 3.500."""
        provided = _baseline() | {
            "0306": Decimal("5000.00"),
            "0307": Decimal("1500.00"),
            "0405": Decimal("3500.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_negative_saldo_patrimonial(self) -> None:
        """Perdidas > ganancias -> saldo negativo (no clamp at this layer)."""
        provided = _baseline() | {
            "0306": Decimal("1000.00"),
            "0307": Decimal("3000.00"),
            "0405": Decimal("-2000.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_drift_in_saldo_detected(self) -> None:
        """Wrong saldo (3.000 vs expected 3.500) is reported as a discrepancy."""
        provided = _baseline() | {
            "0306": Decimal("5000.00"),
            "0307": Decimal("1500.00"),
            "0405": Decimal("3000.00"),  # WRONG -- should be 3500
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2026,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        assert "0405" in {d.casilla_id for d in report.discrepancies}
