"""Unit tests for the Modelo 180 2026 ruleset."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_180_2025, MODELO_180_2026

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


def _provided() -> dict[str, Decimal]:
    """Worked example for a 2026 annual rental-withholding summary."""
    return {
        "01": Decimal("4"),
        "02": Decimal("36000.00"),
        "03": Decimal("6840.00"),
        "04": Decimal("0.00"),
    }


class TestModelo180Ruleset2026:
    def test_consistent_annual_is_clean(self) -> None:
        report = Engine().audit_against(ruleset=MODELO_180_2026, provided=_provided(), tolerance=Decimal("0.01"))
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_2026_no_drift_from_2025(self) -> None:
        """RIRPF art. 100.1 is unchanged, so 2025 and 2026 derive the same values."""
        provided = _provided()
        report_2025 = Engine().audit_against(ruleset=MODELO_180_2025, provided=provided, tolerance=Decimal("0.01"))
        report_2026 = Engine().audit_against(ruleset=MODELO_180_2026, provided=provided, tolerance=Decimal("0.01"))
        derived_2025 = {e.casilla_id: e.value for e in report_2025.ledger.entries}
        derived_2026 = {e.casilla_id: e.value for e in report_2026.ledger.entries}
        assert derived_2025 == derived_2026

    def test_ruleset_id_and_effective_range(self) -> None:
        assert MODELO_180_2026.ruleset_id == "modelo_180.2026"
        assert MODELO_180_2026.effective_from == date(2026, 1, 1)
        assert MODELO_180_2026.effective_to == date(2026, 12, 31)

    def test_formula_id_uses_2026_namespace(self) -> None:
        formula = MODELO_180_2026.formula_for("03")
        assert formula is not None
        assert formula.formula_id == "modelo_180.2026.total_retenciones"

    def test_external_worked_example_rirpf_art_100_2026(self) -> None:
        """Casilla 03 uses the statutory 19 % rate from RIRPF art. 100.1."""
        provided = {
            "01": Decimal("2"),
            "02": Decimal("9500.00"),
            "03": Decimal("1805.00"),
            "04": Decimal("0.00"),
        }
        report = Engine().audit_against(ruleset=MODELO_180_2026, provided=provided, tolerance=Decimal("0.01"))
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_zero_boundary_is_clean(self) -> None:
        provided = {
            "01": Decimal("0"),
            "02": Decimal("0.00"),
            "03": Decimal("0.00"),
            "04": Decimal("0.00"),
        }
        report = Engine().audit_against(ruleset=MODELO_180_2026, provided=provided, tolerance=Decimal("0.01"))
        assert report.is_clean()

    def test_retention_rate_mismatch_raises(self) -> None:
        provided = _provided()
        provided["03"] = Decimal("6480.00")
        report = Engine().audit_against(ruleset=MODELO_180_2026, provided=provided, tolerance=Decimal("0.01"))
        assert "03" in {d.casilla_id for d in report.discrepancies}


@pytest.mark.parametrize(
    ("base", "expected_03"),
    [
        (Decimal("0.00"), Decimal("0.00")),
        (Decimal("100.00"), Decimal("19.00")),
        (Decimal("12000.00"), Decimal("2280.00")),
        (Decimal("48000.00"), Decimal("9120.00")),
    ],
)
def test_casilla_03_derivations_at_various_bases_2026(base: Decimal, expected_03: Decimal) -> None:
    """Cent-exact derivations for casilla 03 across the annual base range."""
    provided = {
        "01": Decimal("1"),
        "02": base,
        "03": expected_03,
        "04": Decimal("0.00"),
    }
    report = Engine().audit_against(ruleset=MODELO_180_2026, provided=provided, tolerance=Decimal("0.01"))
    assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]
