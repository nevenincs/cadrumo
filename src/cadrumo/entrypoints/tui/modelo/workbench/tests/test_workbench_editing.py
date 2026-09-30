"""Editing in the workbench stages typed values, reviews them, and never loses them silently.

Driven through the standalone host with the synthetic form and a fake actions
port: the editor reads every keystroke through the port's parser and only
stages a value that reads cleanly; staged values show on their line with what
they replace; a box the filer cannot type into says why; leaving with staged
changes asks first; applying submits the typed changes and keeps them when the
operation cannot run; and the next-step key runs the step the stepper offers.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, Input, Static

from ......core.config import override_settings
from ....components.dialogs import ConfirmScreen
from ....components.host import ScreenHostApp
from ..casilla_list import CasillaList
from ..editor import CasillaEditorScreen
from ..ports import WorkbenchChangeKind
from ..review import EditReviewScreen
from ..screen import ModeloWorkbenchScreen
from .workbench_fixture import FakeActions, FakeReader, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


async def _settle(pilot: Pilot[None], times: int = 3) -> None:
    for _ in range(times):
        await pilot.pause()


def _list_text(screen: ModeloWorkbenchScreen) -> str:
    widget = screen.query_one(CasillaList)
    return "\n".join(widget.render_line(y).text for y in range(widget.size.height))


@pytest.mark.asyncio
async def test_a_typed_value_is_read_back_then_staged_on_its_line() -> None:
    actions = FakeActions()
    with override_settings(cadrumo_output_language="es"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            editor = app.screen
            assert isinstance(editor, CasillaEditorScreen)
            await pilot.press(*"300,50")
            await _settle(pilot)
            readback = str(editor.query_one("#editor-readback", Static).render())
            await pilot.press("enter")
            await _settle(pilot)
            listing = _list_text(screen)
            next_line = str(screen.query_one("#wb-next", Static).render())

    assert "Se leerá como 300,50" in readback
    staged_line = next(line for line in listing.splitlines() if "Retenciones" in line)
    assert "Δ" in staged_line
    assert "300,50" in staged_line
    assert "Revisa y aplica tus cambios (pendientes: 1) [R]" in next_line


@pytest.mark.asyncio
async def test_an_unreadable_value_cannot_be_staged() -> None:
    with override_settings(cadrumo_output_language="es"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            editor = app.screen
            assert isinstance(editor, CasillaEditorScreen)
            await pilot.press(*"abc")
            await _settle(pilot)
            readback = str(editor.query_one("#editor-readback", Static).render())
            save_disabled = editor.query_one("#editor-save", Button).disabled

    assert readback.startswith("× Escribe un importe")
    assert save_disabled


@pytest.mark.asyncio
async def test_a_box_that_follows_the_records_says_why_it_cannot_be_typed_into() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("left_square_bracket")
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            still_workbench = app.screen is screen
            notice = str(screen.query_one("#wb-notice", Static).render())

    assert still_workbench
    assert notice == "It follows your records; correct it there and recalculate."


@pytest.mark.asyncio
async def test_a_staged_change_can_be_reverted() -> None:
    with override_settings(cadrumo_output_language="es"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            await pilot.press(*"10", "enter")
            await _settle(pilot)
            await pilot.press("u")
            await _settle(pilot)
            staged_line = next(line for line in _list_text(screen).splitlines() if "Retenciones" in line)

    assert "Δ" not in staged_line
    assert "sin dato" in staged_line


@pytest.mark.asyncio
async def test_leaving_with_staged_changes_asks_first_and_can_stay() -> None:
    with override_settings(cadrumo_output_language="es"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            await pilot.press(*"10", "enter")
            await _settle(pilot)
            await pilot.press("escape")
            await _settle(pilot)
            asked = isinstance(app.screen, ConfirmScreen)
            await pilot.press("escape")
            await _settle(pilot)
            stayed = app.screen is screen

    assert asked
    assert stayed


@pytest.mark.asyncio
async def test_applying_submits_the_typed_changes_and_keeps_them_when_the_operation_cannot_run() -> None:
    actions = FakeActions()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            await pilot.press(*"1234,5", "enter")
            await _settle(pilot)
            await pilot.press("R")
            await _settle(pilot)
            reviewing = isinstance(app.screen, EditReviewScreen)
            await pilot.press("a")
            await _settle(pilot, 6)
            notice = str(screen.query_one("#wb-notice", Static).render())
            still_staged = "Δ" in _list_text(screen)

    assert reviewing
    assert len(actions.applied) == 1
    (change,) = actions.applied[0]
    assert change.kind is WorkbenchChangeKind.SET
    assert change.value == Decimal("1234.5")
    assert change.address.kind == "casilla"
    assert notice
    assert still_staged


@pytest.mark.asyncio
async def test_the_next_step_key_runs_the_step_the_stepper_offers() -> None:
    actions = FakeActions()
    reader = FakeReader(form=synthetic_form(calculated=False, needs_input=False))
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(reader, actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("f8")
            await _settle(pilot, 6)

    assert actions.requested == ["calculate"]


@pytest.mark.asyncio
async def test_without_an_edit_admission_the_editor_explains_itself() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            notice = str(screen.query_one("#wb-notice", Static).render())
            focused_input = app.screen.query(Input)

    assert notice == "Editing is not available for this declaration right now."
    assert not focused_input
