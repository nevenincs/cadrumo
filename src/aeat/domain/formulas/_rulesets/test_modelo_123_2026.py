"""Focused tests for the Modelo 123 2026 ruleset."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_123_2025, MODELO_123_2026

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_2026_no_drift_from_2025_on_same_inputs() -> None:
    """The 2026 ruleset shares the 2025 Modelo 123 liquidación shape."""
    provided = {
        "01": Decimal("4"),
        "02": Decimal("2"),
        "03": Decimal("6"),
        "04": Decimal("18000.00"),
        "05": Decimal("7000.00"),
        "06": Decimal("25000.00"),
        "07": Decimal("3420.00"),
        "08": Decimal("1330.00"),
        "09": Decimal("4750.00"),
        "10": Decimal("0.00"),
        "11": Decimal("4750.00"),
    }
    report_2025 = Engine().audit_against(ruleset=MODELO_123_2025, provided=provided, tolerance=Decimal("0.01"))
    report_2026 = Engine().audit_against(ruleset=MODELO_123_2026, provided=provided, tolerance=Decimal("0.01"))
    assert report_2025.is_clean()
    assert report_2026.is_clean()
    assert {e.casilla_id: e.value for e in report_2026.ledger.entries} == {
        e.casilla_id: e.value for e in report_2025.ledger.entries
    }


def test_2026_complementaria_offset_mismatch_is_flagged() -> None:
    """Casilla 11 must equal casilla 09 minus casilla 10."""
    provided = {
        "01": Decimal("1"),
        "02": Decimal("2"),
        "03": Decimal("3"),
        "04": Decimal("6400.00"),
        "05": Decimal("3600.00"),
        "06": Decimal("10000.00"),
        "07": Decimal("1216.00"),
        "08": Decimal("684.00"),
        "09": Decimal("1900.00"),
        "10": Decimal("75.00"),
        "11": Decimal("1900.00"),
    }
    report = Engine().audit_against(ruleset=MODELO_123_2026, provided=provided, tolerance=Decimal("0.01"))
    assert "11" in {d.casilla_id for d in report.discrepancies}
