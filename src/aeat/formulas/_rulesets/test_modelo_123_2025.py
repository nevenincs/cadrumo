"""Unit tests for the Modelo 123 2025 ruleset."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_123_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def _provided(**overrides: str) -> dict[str, Decimal]:
    """Consistent 123 fixture: 1+4=5 perceptores, 1500+8000=9500 base, 285+1520=1805, 1805-0=1805."""
    base = {
        "01": "1",
        "02": "4",
        "03": "5",
        "04": "1500.00",
        "05": "8000.00",
        "06": "9500.00",
        "07": "285.00",
        "08": "1520.00",
        "09": "1805.00",
        "10": "0.00",
        "11": "1805.00",
    }
    base.update(overrides)
    return {k: Decimal(v) for k, v in base.items()}


class TestModelo123Ruleset:
    def test_consistent_quarter_is_clean(self) -> None:
        report = Engine().audit_against(
            ruleset=MODELO_123_2025,
            provided=_provided(),
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_total_perceptores_mismatch(self) -> None:
        report = Engine().audit_against(
            ruleset=MODELO_123_2025,
            provided=_provided(**{"03": "6"}),
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        assert "03" in {d.casilla_id for d in report.discrepancies}

    def test_total_base_mismatch(self) -> None:
        report = Engine().audit_against(
            ruleset=MODELO_123_2025,
            provided=_provided(**{"06": "9000.00"}),
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        assert "06" in {d.casilla_id for d in report.discrepancies}

    def test_complementaria_offset_applied(self) -> None:
        # 09 = 2000 (07+08=800+1200), 10 = 500, expected 11 = 1500.
        report = Engine().audit_against(
            ruleset=MODELO_123_2025,
            provided=_provided(
                **{
                    "07": "800.00",
                    "08": "1200.00",
                    "09": "2000.00",
                    "10": "500.00",
                    "11": "1500.00",
                }
            ),
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_ruleset_has_four_formulas(self) -> None:
        # 03, 06, 09, 11 are computed; 01/02/04/05/07/08/10 are user input.
        computed = {c.casilla_id for c in MODELO_123_2025.casillas if c.computed}
        assert computed == {"03", "06", "09", "11"}
