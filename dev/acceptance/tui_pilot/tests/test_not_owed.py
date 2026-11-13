"""A return the table holds not owed stops after calculate, as the table stops it; an owed return is untouched."""

from __future__ import annotations

import pytest

from cadrumo.application.modelo.work_form_next_step import ModeloFormNextAction

from ...persona_table.frontend import MATCHED
from ...persona_table.rows import Stage, TableRow
from ..causes import outcome, row_cause, unreported_cause
from ..intake import NOT_OWED, PASSED, PilotRow
from ..pilot import stop_when_not_owed

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PERSONA = "synthetic-autonomo"
_YEAR = 7
"""A synthetic year: these rows meet no registry."""


def _table(*, verify: Stage, export: Stage) -> TableRow:
    return TableRow(
        persona=_PERSONA,
        modelo="130",
        year=_YEAR,
        period="1T",
        horizon=_YEAR,
        grounding="verified",
        sources=("rd-439-2007:art-110",),
        has_values=True,
        calculate=Stage.PASSED,
        verify=verify,
        export=export,
        figures=(("01", "1000"), ("03", "475")),
    )


def _calculated() -> PilotRow:
    return PilotRow(
        persona=_PERSONA,
        modelo="130",
        year=_YEAR,
        period="1T",
        calculate=PASSED,
        figures={"01": "1000.00", "03": "475.00"},
    )


def test_a_calculated_not_owed_return_stops_with_the_tables_stages_and_says_what_the_form_served() -> None:
    row = _calculated()

    stopped = stop_when_not_owed(row, owed=False, calculated=True, served=ModeloFormNextAction.VERIFY)

    assert stopped
    assert (row.calculate, row.verify, row.export) == (PASSED, NOT_OWED, "not-reached")
    assert row.filed is False
    assert row.stopped_at is None
    assert any("the next step verify" in reason for reason in row.reasons)


def test_the_stopped_row_matches_the_tables_not_owed_row_and_names_no_cause() -> None:
    row = _calculated()
    table = _table(verify=Stage.NOT_OWED, export=Stage.NOT_REACHED)
    stop_when_not_owed(row, owed=False, calculated=True, served=None)

    assert outcome(row, table) == MATCHED
    assert row_cause(row, table, []) == (None, "")
    assert unreported_cause(row, []) == (None, "")
    assert any("no next step" in reason for reason in row.reasons)


def test_a_not_owed_return_that_did_not_calculate_is_left_as_it_ran() -> None:
    row = PilotRow(persona=_PERSONA, modelo="130", year=_YEAR, period="1T", calculate="refused")

    assert not stop_when_not_owed(row, owed=False, calculated=False, served=None)
    assert (row.verify, row.export, row.reasons) == (None, None, [])


def test_an_owed_return_is_not_stopped_and_keeps_its_stages_for_the_steps_that_follow() -> None:
    row = _calculated()

    assert not stop_when_not_owed(row, owed=True, calculated=True, served=ModeloFormNextAction.VERIFY)
    assert (row.verify, row.export, row.reasons) == (None, None, [])
