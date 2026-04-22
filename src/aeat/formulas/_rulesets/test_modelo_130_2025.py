"""Unit tests for the Modelo 130 2025 ruleset.

Wave 55 companion to test_modelo_130_2024.py. The 2025 ruleset
re-uses the 2024 casillas + citations (mid-year rule changes absent
for 2024→2025 per the research doc), so the 2025 tests exercise the
same formulas via the 2025 variant to confirm no drift.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .._engine import Engine
from . import MODELO_130_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def _provided() -> dict[str, Decimal]:
    """Identical shape to the 2024 test: 20 000 € ingresos, 5 000 € gastos.

    If the 2025 ruleset drifted from 2024 (rate change, formula
    swap, casilla shuffle), this fixture would flag a discrepancy
    against the engine-derived values.
    """
    return {
        "01": Decimal("20000.00"),
        "02": Decimal("5000.00"),
        "03": Decimal("15000.00"),
        "04": Decimal("3000.00"),
        "05": Decimal("0.00"),
        "06": Decimal("0.00"),
        "07": Decimal("3000.00"),
        "08": Decimal("0.00"),
        "09": Decimal("0.00"),
        "10": Decimal("0.00"),
        "11": Decimal("0.00"),
        "12": Decimal("3000.00"),
        "13": Decimal("0.00"),
        "14": Decimal("3000.00"),
        "15": Decimal("0.00"),
        "16": Decimal("0.00"),
        "17": Decimal("3000.00"),
        "18": Decimal("0.00"),
        "19": Decimal("3000.00"),
    }


class TestModelo130Ruleset2025:
    def test_consistent_quarter_is_clean(self) -> None:
        report = Engine().audit_against(
            ruleset=MODELO_130_2025,
            provided=_provided(),
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_agraria_income_computes_2_percent(self) -> None:
        """Casilla 09 = 2% x 08. Agricultural autónomo fixture."""
        provided = _provided()
        # Set 08 = 5000 (agraria ingresos), expect 09 = 100.
        provided["08"] = Decimal("5000.00")
        provided["09"] = Decimal("100.00")
        provided["11"] = Decimal("100.00")  # 11 = 09 - 10 = 100
        provided["12"] = Decimal("3100.00")  # 07 + 11 = 3000 + 100
        provided["14"] = Decimal("3100.00")
        provided["17"] = Decimal("3100.00")
        provided["19"] = Decimal("3100.00")
        report = Engine().audit_against(
            ruleset=MODELO_130_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        assert report.is_clean(), [(d.casilla_id, d.computed_value, d.user_value) for d in report.discrepancies]

    def test_2025_no_drift_from_2024(self) -> None:
        """Wave 55 regression: 2025 ruleset MUST produce identical audit
        to 2024 for any fixture where both rulesets would legally apply
        (i.e. no mid-year change). The casillas + formulas are shared
        module-level imports, so a drift would require an active change.
        """
        from . import MODELO_130_2024

        provided = _provided()
        report_2024 = Engine().audit_against(
            ruleset=MODELO_130_2024,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        report_2025 = Engine().audit_against(
            ruleset=MODELO_130_2025,
            provided=provided,
            tolerance=Decimal("0.01"),
        )
        # Same number of ledger entries and same derived values.
        assert len(report_2024.ledger.entries) == len(report_2025.ledger.entries)
        derived_2024 = {e.casilla_id: e.value for e in report_2024.ledger.entries}
        derived_2025 = {e.casilla_id: e.value for e in report_2025.ledger.entries}
        assert derived_2024 == derived_2025

    def test_ruleset_id_and_effective_range(self) -> None:
        assert MODELO_130_2025.ruleset_id == "modelo_130.2025"
        assert MODELO_130_2025.effective_from == date(2025, 1, 1)
        assert MODELO_130_2025.effective_to == date(2025, 12, 31)
