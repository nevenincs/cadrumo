"""End-to-end derivation tests for the Modelo 303 2024 ruleset (#183).

Cross-year parity tests live here too: since the régimen general
rates were stable 2024 → 2025 (LIVA arts. 90/91 unamended), the
2024 and 2025 rulesets must produce the exact same ledger for the
same input set.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._engine import Engine
from .modelo_303_2024 import RULESET as MODELO_303_2024
from .modelo_303_2025 import RULESET as MODELO_303_2025


def _ledger(ruleset, inputs):
    """Convenience derivation."""
    engine = Engine()
    return engine.derive(ruleset=ruleset, inputs=inputs)


@pytest.mark.unit
def test_modelo_303_2024_general_only() -> None:
    """Base 07 = 10000, 65 = 100 ⇒ 71 = 2100.00 (2024 ruleset)."""
    ledger = _ledger(MODELO_303_2024, {"07": Decimal("10000.00"), "65": Decimal("100")})
    values = {entry.casilla_id: entry.value for entry in ledger.entries}
    assert values["09"] == Decimal("2100.00")
    assert values["71"] == Decimal("2100.00")


@pytest.mark.unit
def test_modelo_303_2024_constants() -> None:
    """Casillas 02/05/08 carry the 4 / 10 / 21 printed rates."""
    ledger = _ledger(MODELO_303_2024, {"65": Decimal("100")})
    values = {entry.casilla_id: entry.value for entry in ledger.entries}
    assert values["02"] == Decimal("4.00")
    assert values["05"] == Decimal("10.00")
    assert values["08"] == Decimal("21.00")


@pytest.mark.unit
def test_cross_year_parity_at_cent_for_baseline_inputs() -> None:
    """The 2024 and 2025 rulesets produce the same ledger for the same inputs.

    Equivalence is required because LIVA arts. 90 / 91 were not
    amended between the two years and the parameter table values
    are identical.
    """
    inputs = {
        "01": Decimal("1000.00"),
        "04": Decimal("2000.00"),
        "07": Decimal("5000.00"),
        "29": Decimal("210.00"),
        "31": Decimal("0"),
        "33": Decimal("100.00"),
        "37": Decimal("420.00"),
        "40": Decimal("-50.00"),
        "65": Decimal("100"),
        "67": Decimal("0"),
    }
    ledger_2024 = _ledger(MODELO_303_2024, inputs)
    ledger_2025 = _ledger(MODELO_303_2025, inputs)
    map_2024 = {e.casilla_id: e.value for e in ledger_2024.entries}
    map_2025 = {e.casilla_id: e.value for e in ledger_2025.entries}
    assert map_2024 == map_2025
