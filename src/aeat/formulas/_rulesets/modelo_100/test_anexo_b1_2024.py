"""Unit tests for Modelo 100 Anexo B1 — rendimientos del trabajo (2024).

Ejercicio 2024 is the first year RD-Ley 4/2024 applied. The ruleset is
a structural clone of 2025 with year-scoped formula IDs and 2024
effective dates. Verifies the same piecewise reducción art. 20 anchors
and ruleset shape against the 2024 ruleset constant.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..._engine import Engine
from .. import MODELO_100_2024

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


class TestModelo100AnexoB1:
    def test_ruleset_id_and_default_variant(self) -> None:
        assert MODELO_100_2024.ruleset_id == "modelo_100.2024"
        assert MODELO_100_2024.variant == "default"

    def test_consistent_filing_is_clean(self) -> None:
        """Same scenario as 2025 — RD-Ley 4/2024 thresholds apply identically."""
        provided = {
            "0001": Decimal("15000.00"),
            "0008": Decimal("1000.00"),
            "0009": Decimal("500.00"),
            "0010": Decimal("0.00"),
            "0019": Decimal("0.00"),
            "0020": Decimal("13500.00"),
            "0021": Decimal("7302.00"),
            "0022": Decimal("6198.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_reduccion_art_20_at_piece_b_middle(self) -> None:
        """Cross-year regression: same 18.000 €rendimiento → 1.992,15 reducción
        in 2024 (no rate / threshold change relative to 2025).
        """
        provided = {
            "0001": Decimal("18000.00"),
            "0008": Decimal("0.00"),
            "0009": Decimal("0.00"),
            "0010": Decimal("0.00"),
            "0019": Decimal("0.00"),
            "0020": Decimal("18000.00"),
            "0021": Decimal("1992.15"),
            "0022": Decimal("16007.85"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_100_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_ruleset_shape(self) -> None:
        computed = {c.casilla_id for c in MODELO_100_2024.casillas if c.computed}
        assert computed == {"0020", "0021", "0022"}
        assert len(MODELO_100_2024.formulas) == 3
