"""The oracle judges a run from independent readings and tells a product disagreement from an agent's miss.

Readings are built in the shapes the packaged command line and the export
parser return. The positive controls plant a disagreement between two readings
of the same fact (export against stored calculation, export against the
ledger) and a figure that is wrong but consistent: the first two must be
disagreements, the last only a missed end state.
"""

from __future__ import annotations

import pytest

from ..live.oracle import OracleReading, judge
from ..live.scenario import load_scenario

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ROWS = [
    {
        "booked_date": "2026-02-15",
        "amount": "12000.00",
        "direction": "INCOMING",
        "description": "income",
        "business_classification": "BUSINESS",
        "taxable_base": "12000.00",
    },
    {
        "booked_date": "2026-03-10",
        "amount": "4000.00",
        "direction": "OUTGOING",
        "description": "expense",
        "business_classification": "BUSINESS",
        "taxable_base": "4000.00",
    },
]
_CASILLAS = {"01": "12000.00", "02": "4000.00", "03": "8000.00", "04": "1600.00", "07": "1600.00", "13": "100.00"}


def _reading(**changes: object) -> OracleReading:
    reading = OracleReading(
        ledger_rows=[dict(row) for row in _ROWS],
        work_units=[{"modelo": "130", "filing_year": 2026, "period": "2026-1T"}],
        revision_casillas=dict(_CASILLAS),
        history_event_types=["work_unit_created", "calculation_recorded", "verification_recorded", "export_recorded"],
        export_present=True,
        export_casillas=dict(_CASILLAS),
    )
    for name, value in changes.items():
        setattr(reading, name, value)
    return reading


def test_agreeing_readings_of_the_published_figures_reach_the_end_state() -> None:
    judgement = judge(_reading(), load_scenario("modelo_130_dr130"))
    assert judgement.end_state_reached
    assert judgement.disagreements == judgement.shortfalls == ()


def test_an_export_that_disagrees_with_the_stored_calculation_is_a_disagreement() -> None:
    planted = {**_CASILLAS, "07": "1700.00"}
    judgement = judge(_reading(export_casillas=planted), load_scenario("modelo_130_dr130"))
    assert any("casilla 07" in item and "stored calculation" in item for item in judgement.disagreements)
    assert not judgement.end_state_reached


def test_an_export_that_disagrees_with_the_ledger_is_a_disagreement() -> None:
    rows = [dict(row) for row in _ROWS]
    rows[0]["taxable_base"] = "11000.00"
    judgement = judge(_reading(ledger_rows=rows), load_scenario("modelo_130_dr130"))
    assert any(item.startswith("casilla 01") and "ledger" in item for item in judgement.disagreements)


def test_a_consistent_but_wrong_figure_is_a_missed_end_state_not_a_disagreement() -> None:
    wrong = {**_CASILLAS, "04": "1500.00", "07": "1500.00"}
    judgement = judge(_reading(export_casillas=wrong, revision_casillas=wrong), load_scenario("modelo_130_dr130"))
    assert judgement.disagreements == ()
    assert not judgement.end_state_reached
    assert any("casilla 04" in item for item in judgement.shortfalls)


def test_no_export_is_a_missed_end_state() -> None:
    judgement = judge(_reading(export_present=False, export_casillas={}), load_scenario("modelo_130_dr130"))
    assert not judgement.end_state_reached
    assert judgement.disagreements == ()


def test_the_fingerprint_changes_only_when_the_profile_does() -> None:
    before = _reading(export_present=False, export_casillas={})
    assert before.fingerprint() == _reading(export_present=False, export_casillas={}).fingerprint()
    after = _reading(export_present=False, export_casillas={}, ledger_rows=[*_ROWS, {**_ROWS[0], "amount": "1.00"}])
    assert before.fingerprint() != after.fingerprint()
