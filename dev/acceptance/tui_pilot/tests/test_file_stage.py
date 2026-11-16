"""The TUI row states a file stage from what the workbench itself shows, only for a return the table filed locally."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from textual.widgets import Static

from cadrumo.application.modelo.work_form_next_step import ModeloFormNextAction
from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.core.config import override_settings
from cadrumo.core.operations import OperationTerminalCondition
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.modelo.workbench.screen import ModeloWorkbenchScreen
from cadrumo.entrypoints.tui.modelo.workbench.tests.declaration_states import recorded_as_filed
from cadrumo.entrypoints.tui.modelo.workbench.tests.workbench_driver import (
    ShownFiling,
    ShownOutcome,
    recorded_sentence_shown,
)
from cadrumo.entrypoints.tui.modelo.workbench.tests.workbench_fixture import FakeActions, FakeReader, synthetic_form
from cadrumo.entrypoints.tui.tests.settling import settle

from ...persona_table.frontend import NOT_REACHED, parse_result
from ...persona_table.rows import Stage, TableRow
from ..causes import _differing_cause, file_stage_of, row_cause, table_filed_locally
from ..intake import ERROR, NOT_SHOWN, OUT_ENV, PASSED, REFUSED, TREE_ENV, PilotRow, write_rows
from ..pilot import _recorded

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_YEAR = 7
"""A synthetic year: these rows meet no registry."""
_RECORDED_LINE = "Recorded as filed on Apr 15, 2026"


def _table(reason: str) -> TableRow:
    return TableRow(
        persona="synthetic-autonomo",
        modelo="130",
        year=_YEAR,
        period="1T",
        horizon=_YEAR,
        grounding="verified",
        sources=("rd-439-2007:art-110",),
        has_values=True,
        calculate=Stage.PASSED,
        verify=Stage.PASSED,
        export=Stage.PASSED,
        reason=reason,
        figures=(("01", "1000"),),
    )


def _row(**data: object) -> PilotRow:
    held = PilotRow(
        persona="synthetic-autonomo",
        modelo="130",
        year=_YEAR,
        period="1T",
        calculate="pass",
        verify="pass",
        export="pass",
        figures={"01": "1000.00"},
    )
    return replace(held, **data)


def _shown(
    condition: OperationTerminalCondition | None,
    *,
    submitted: bool = True,
    next_line: str | None = None,
    notice: str = "",
    refusal: str = "",
) -> ShownOutcome:
    """A step the workbench settled with ``condition``, followed by the next-step line it then showed."""
    terminal = (
        None
        if condition is None
        else OperationPublicProjectionV1.model_construct(
            terminal_condition=condition, refusal_ref="REFUSED_MODELO_FILING_X", failure_error_code="ERROR_X"
        )
    )
    filing = (
        None if next_line is None else ShownFiling(next_line=next_line, recorded=recorded_sentence_shown(next_line))
    )
    return ShownOutcome(
        action=ModeloFormNextAction.RECORD_AFTER_FILE,
        submitted=submitted,
        terminal=terminal,
        refusal=refusal,
        notice=notice,
        verification=None,
        filing=filing,
    )


# -- what the workbench shows --------------------------------------------------------------------------------------


async def _next_line(*, recorded: bool) -> str:
    form = synthetic_form(needs_input=False)
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(
            FakeReader(form=recorded_as_filed(form) if recorded else form, verified=True, filed=recorded),
            actions=FakeActions(),
        )
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await settle(pilot)
            line = " ".join(str(screen.query_one("#wb-next", Static).render()).split())
            app.exit(None)
    return line


@pytest.mark.asyncio
async def test_the_recorded_sentence_is_recognised_in_what_the_real_screen_renders() -> None:
    line = await _next_line(recorded=True)

    assert line == _RECORDED_LINE
    with override_settings(cadrumo_output_language="en"):
        assert recorded_sentence_shown(line)


@pytest.mark.asyncio
async def test_a_screen_not_yet_recorded_does_not_show_the_recorded_sentence() -> None:
    line = await _next_line(recorded=False)

    assert line != _RECORDED_LINE
    with override_settings(cadrumo_output_language="en"):
        assert not recorded_sentence_shown(line)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (_RECORDED_LINE, True),
        ("Recorded as filed on 15 abr 2026", True),
        ("✓ Record filing", True),
        ("Record the filing [F8]", False),
        ("Recorded as filed", False),
        ("", False),
    ],
)
def test_only_the_workbenchs_recorded_sentence_counts_as_the_filed_state(line: str, expected: bool) -> None:
    with override_settings(cadrumo_output_language="en"):
        assert recorded_sentence_shown(line) is expected


# -- the three outcomes --------------------------------------------------------------------------------------------


def test_a_filing_the_workbench_shows_recorded_is_file_pass() -> None:
    row = _row()

    with override_settings(cadrumo_output_language="en"):
        taken = _recorded(_shown(OperationTerminalCondition.SUCCEEDED, next_line=_RECORDED_LINE), row)

    assert taken
    assert (row.filed, row.file) == (True, PASSED)
    assert any(_RECORDED_LINE in reason for reason in row.reasons)


def test_a_filing_the_workbench_refuses_is_file_refused_with_its_words() -> None:
    row = _row()

    taken = _recorded(
        _shown(
            OperationTerminalCondition.REFUSED, next_line="Record the filing [F8]", refusal="The check is out of date."
        ),
        row,
    )

    assert not taken
    assert (row.filed, row.file) == (False, REFUSED)
    assert any("REFUSED_MODELO_FILING_X" in reason and "The check is out of date." in reason for reason in row.reasons)


def test_a_key_the_workbench_withholds_is_file_refused() -> None:
    row = _row()

    taken = _recorded(_shown(None, submitted=False, notice="Not available while the check is out of date."), row)

    assert not taken
    assert (row.filed, row.file) == (False, REFUSED)
    assert any("Not available while the check is out of date." in reason for reason in row.reasons)


def test_a_filing_that_settles_while_the_line_shows_nothing_of_it_is_file_not_shown() -> None:
    row = _row()

    with override_settings(cadrumo_output_language="en"):
        taken = _recorded(_shown(OperationTerminalCondition.SUCCEEDED, next_line="Record the filing [F8]"), row)

    assert taken
    assert (row.filed, row.file) == (True, NOT_SHOWN)
    assert any("Record the filing [F8]" in reason for reason in row.reasons)


def test_a_filing_that_fails_is_file_error() -> None:
    row = _row()

    _recorded(_shown(OperationTerminalCondition.FAILED, next_line="Record the filing [F8]"), row)

    assert (row.filed, row.file) == (False, ERROR)


# -- which rows carry the stage ------------------------------------------------------------------------------------


def test_a_return_the_table_did_not_file_gets_no_file_stage() -> None:
    assert not table_filed_locally(_table("file: REFUSED_MODELO_PRIOR_PERIOD_UNFILED"))
    assert file_stage_of(_row(file=PASSED), _table("file: REFUSED_MODELO_PRIOR_PERIOD_UNFILED")) is None
    assert file_stage_of(_row(file=REFUSED), _table("")) is None


def test_a_return_the_table_filed_keeps_the_workbenchs_word() -> None:
    table = _table("filed locally")

    assert table_filed_locally(table)
    assert [file_stage_of(_row(file=word), table) for word in (PASSED, REFUSED, NOT_SHOWN)] == [
        PASSED,
        REFUSED,
        NOT_SHOWN,
    ]


def test_a_filed_return_the_drive_never_recorded_is_not_reached() -> None:
    assert file_stage_of(_row(), _table("filed locally")) == NOT_REACHED


def test_a_file_stage_other_than_pass_on_otherwise_equal_stages_names_its_own_cause() -> None:
    cause, _ = _differing_cause(_row(file=NOT_SHOWN), _table("filed locally"), [], "words")

    assert cause == "other:file_not_shown"


def test_a_stage_that_differs_keeps_its_own_cause_before_the_file_stage() -> None:
    cause, _ = _differing_cause(_row(file=NOT_SHOWN, verify="incomplete"), _table("filed locally"), [], "words")

    assert cause == "other:verify_incomplete"


# -- the line the pilot writes -------------------------------------------------------------------------------------


def _written(row: PilotRow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    out = tmp_path / "rows.jsonl"
    monkeypatch.setenv(OUT_ENV, str(out))
    monkeypatch.setenv(TREE_ENV, "abc123")
    write_rows([row])
    (line,) = out.read_text(encoding="utf-8").splitlines()
    written = json.loads(line)
    assert isinstance(written, dict)
    return {str(key): value for key, value in written.items()}


@pytest.mark.parametrize("word", [PASSED, REFUSED])
def test_the_stage_is_written_as_the_grader_parses_it(
    word: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    written = _written(_row(file=word), tmp_path, monkeypatch)

    assert written["file"] == word
    assert parse_result(json.dumps(written)).file == word


def test_not_shown_is_never_written_as_a_line_the_grader_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = _row(file=NOT_SHOWN, reasons=["file: the workbench shows 'Record the filing [F8]'"])

    written = _written(row, tmp_path, monkeypatch)

    assert parse_result(json.dumps(written)).file in (None, NOT_SHOWN)
    assert "Record the filing [F8]" in str(written["reason"])


def test_a_row_without_a_file_stage_writes_no_file_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    written = _written(_row(), tmp_path, monkeypatch)

    assert "file" not in written
    assert parse_result(json.dumps(written)).file is None


def test_a_row_carrying_a_file_stage_reads_back_with_it_and_keeps_its_stage_causes() -> None:
    row = _row(file=PASSED)

    assert row.result().file == PASSED
    assert row_cause(row, _table("filed locally"), []) == (None, "")
    assert row_cause(replace(row, verify="incomplete"), _table("filed locally"), [])[0] == "other:verify_incomplete"
