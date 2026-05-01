"""Unit tests for the Modelo 180 2024 ruleset."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_180_2024

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


@pytest.mark.parametrize(
    ("base", "expected_03"),
    [
        (Decimal("0.00"), Decimal("0.00")),
        (Decimal("100.00"), Decimal("19.00")),
        (Decimal("48000.00"), Decimal("9120.00")),
        (Decimal("90000.00"), Decimal("17100.00")),
    ],
)
def test_casilla_03_derivation_2024(base: Decimal, expected_03: Decimal) -> None:
    """Casilla 03 is 19 % of casilla 02 under RIRPF art. 100.1."""
    provided = {
        "01": Decimal("1"),
        "02": base,
        "03": expected_03,
        "04": Decimal("0.00"),
    }
    report = Engine().audit_against(ruleset=MODELO_180_2024, provided=provided, tolerance=Decimal("0.01"))
    assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]


def test_ruleset_id_and_effective_range_2024() -> None:
    """Registry metadata is bounded to the 2024 ejercicio."""
    assert MODELO_180_2024.ruleset_id == "modelo_180.2024"
    assert MODELO_180_2024.effective_from == date(2024, 1, 1)
    assert MODELO_180_2024.effective_to == date(2024, 12, 31)


def test_retention_rate_mismatch_2024() -> None:
    """A printed value using 18 % is classified as a formula mismatch."""
    provided = {
        "01": Decimal("2"),
        "02": Decimal("10000.00"),
        "03": Decimal("1800.00"),
        "04": Decimal("0.00"),
    }
    report = Engine().audit_against(ruleset=MODELO_180_2024, provided=provided, tolerance=Decimal("0.01"))
    assert "03" in {d.casilla_id for d in report.discrepancies}
