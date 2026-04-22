"""Unit tests for the Modelo 115 2025 ruleset."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_115_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


class TestModelo115Ruleset:
    def test_matches_published_values_is_clean(self) -> None:
        provided = {
            "01": Decimal("2"),
            "02": Decimal("12000.00"),
            "03": Decimal("2280.00"),
            "04": Decimal("0.00"),
            "05": Decimal("0.00"),
            "06": Decimal("2280.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_115_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_retention_percent_mismatch_reported(self) -> None:
        # Kent typos 2280 → 2300 (off by ~20€ vs. 19% of 12000).
        provided = {
            "01": Decimal("2"),
            "02": Decimal("12000.00"),
            "03": Decimal("2300.00"),
            "04": Decimal("0.00"),
            "05": Decimal("0.00"),
            "06": Decimal("2300.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_115_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert not report.is_clean()
        offenders = {d.casilla_id for d in report.discrepancies}
        assert "03" in offenders

    def test_resultado_a_ingresar_formula(self) -> None:
        # 06 should be 03 + 04 - 05 = 2280 + 100 - 50 = 2330.
        provided = {
            "02": Decimal("12000.00"),
            "03": Decimal("2280.00"),
            "04": Decimal("100.00"),
            "05": Decimal("50.00"),
            "06": Decimal("2330.00"),
        }
        report = Engine().audit_against(
            ruleset=MODELO_115_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean()

    def test_includes_reglamento_and_ley_citations(self) -> None:
        # Wave 29 HIGH-1: 19% lives in RD 439/2007 art. 100.3.a, not LIRPF 100.2.
        articles = {c.article for c in MODELO_115_2025.legal_citations}
        assert "100.3.a" in articles  # Reglamento: fija el 19%
        assert "101.8" in articles  # LIRPF: delega el tipo al reglamento
