"""A return whose check ran and whose form then served no export door records that as served state."""

from __future__ import annotations

import pytest

from cadrumo.application.modelo.work_form_next_step import ModeloFormNextAction

from ...persona_table.frontend import NOT_REACHED
from ..intake import NOT_OWED, PilotRow
from ..pilot import _note_export_served

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _row(*, verify: str | None, export: str | None) -> PilotRow:
    return PilotRow(persona="p", modelo="200", year=1, period="0A", calculate="pass", verify=verify, export=export)


def test_no_export_door_after_the_check_reads_not_served() -> None:
    row = _row(verify="incomplete", export=NOT_REACHED)

    _note_export_served(row, None)

    assert row.export_served is False


def test_a_served_export_door_is_not_marked_unserved() -> None:
    row = _row(verify="pass", export=NOT_REACHED)

    _note_export_served(row, ModeloFormNextAction.EXPORT)

    assert row.export_served is None


@pytest.mark.parametrize("verify", [None, NOT_REACHED, NOT_OWED])
def test_a_check_that_never_ran_says_nothing_about_the_export_door(verify: str | None) -> None:
    row = _row(verify=verify, export=NOT_REACHED)

    _note_export_served(row, None)

    assert row.export_served is None


def test_an_export_that_was_pressed_is_not_overwritten() -> None:
    row = _row(verify="pass", export="pass")

    _note_export_served(row, None)

    assert row.export_served is None
