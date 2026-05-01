"""Focused tests for the Modelo 123 2024 ruleset."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_123_2024, MODELO_123_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_2024_no_drift_from_2025_on_same_inputs() -> None:
    """The 2024 ruleset shares the 2025 Modelo 123 liquidación shape."""
    provided = {
        "01": Decimal("1"),
        "02": Decimal("2"),
        "03": Decimal("3"),
        "04": Decimal("2500.00"),
        "05": Decimal("10000.00"),
        "06": Decimal("12500.00"),
        "07": Decimal("475.00"),
        "08": Decimal("1900.00"),
        "09": Decimal("2375.00"),
        "10": Decimal("0.00"),
        "11": Decimal("2375.00"),
    }
    report_2024 = Engine().audit_against(ruleset=MODELO_123_2024, provided=provided, tolerance=Decimal("0.01"))
    report_2025 = Engine().audit_against(ruleset=MODELO_123_2025, provided=provided, tolerance=Decimal("0.01"))
    assert report_2024.is_clean()
    assert report_2025.is_clean()
    assert {e.casilla_id: e.value for e in report_2024.ledger.entries} == {
        e.casilla_id: e.value for e in report_2025.ledger.entries
    }


def test_2024_retenciones_total_mismatch_is_flagged() -> None:
    """Casilla 09 must equal casilla 07 plus casilla 08."""
    provided = {
        "01": Decimal("1"),
        "02": Decimal("2"),
        "03": Decimal("3"),
        "04": Decimal("2500.00"),
        "05": Decimal("10000.00"),
        "06": Decimal("12500.00"),
        "07": Decimal("475.00"),
        "08": Decimal("1900.00"),
        "09": Decimal("2000.00"),
        "10": Decimal("0.00"),
        "11": Decimal("2000.00"),
    }
    report = Engine().audit_against(ruleset=MODELO_123_2024, provided=provided, tolerance=Decimal("0.01"))
    assert "09" in {d.casilla_id for d in report.discrepancies}
