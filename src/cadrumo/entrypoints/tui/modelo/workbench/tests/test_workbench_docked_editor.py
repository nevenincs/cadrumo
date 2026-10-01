"""The box panel docks at the foot of the workbench, and opens as a centred dialog on a short terminal.

Driven through the standalone host with the sectioned synthetic form, whose
first page holds three assumed values one after another: from thirty rows of
height, Enter docks the panel in place of the help band, below the list,
whose row stays highlighted in view; keeping a value and going to the next
moves the list's highlight and refills the panel for that box; Escape closes
it and gives the cursor back to the list; the arrow keys in the panel's input
never move the list, and the workbench's own keys wait while the filer works
in it; the list still scrolls under the mouse. Below thirty rows the same
panel opens in the centred dialog, and a panel already open keeps what the
filer typed when the terminal is resized across that height.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from textual import events
from textual.pilot import Pilot
from textual.widgets import Button, Input, Static

from ......core.config import override_settings
from ....components.host import ScreenHostApp
from ....navigation import TuiNavigationTargetV1
from ..casilla_list import CasillaList
from ..editor import CasillaEditorPanel, CasillaEditorScreen
from ..screen import ModeloWorkbenchScreen
from ..sources import surface_target
from .editor_panel import open_panel
from .sectioned_form import long_section_form, sectioned_form
from .workbench_fixture import FakeActions, FakeReader

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_DOCKED = (120, 36)
_SHORT = (80, 24)


_SHOWING_WAIT = 200
"""The most pauses a test waits for the screen to show what it expects before it reads what is there."""


async def _settle(pilot: Pilot[None], times: int = 4) -> None:
    for _ in range(times):
        await pilot.pause()


def _workbench(navigate: list[TuiNavigationTargetV1] | None = None) -> ModeloWorkbenchScreen:
    return ModeloWorkbenchScreen(
        FakeReader(form=sectioned_form()),
        actions=FakeActions(),
        navigate=None if navigate is None else navigate.append,
    )


def _highlighted_box(screen: ModeloWorkbenchScreen) -> str | None:
    entry = screen.query_one(CasillaList).highlighted
    return None if entry is None else entry.field.box


def _list_lines(screen: ModeloWorkbenchScreen) -> list[str]:
    widget = screen.query_one(CasillaList)
    return [widget.render_line(y).text for y in range(widget.size.height)]


def _title(panel: CasillaEditorPanel) -> str:
    return str(panel.query_one("#editor-title", Static).render())


@pytest.mark.asyncio
async def test_enter_docks_the_panel_under_the_list_with_the_row_still_highlighted_in_view() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = _workbench()
        app = ScreenHostApp(screen)
        async with app.run_test(size=_DOCKED) as pilot:
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            on_top = app.screen
            panel = open_panel(screen)
            assert panel is not None
            listed = screen.query_one(CasillaList)
            list_region = listed.region
            panel_region = panel.region
            help_shown = screen.query_one("#wb-help").display
            title = _title(panel)
            status = list(panel.query("#editor-status"))
            focused = app.focused
            highlighted = _highlighted_box(screen)
            lines = _list_lines(screen)

    assert on_top is screen, "at 36 rows the panel docks in the workbench rather than covering it"
    assert panel_region.y >= list_region.bottom, "the panel sits below the list, where the help band was"
    assert list_region.height > 0
    assert not help_shown, "the panel takes the help band's place rather than stacking under it"
    assert title.startswith("[05]"), "the panel says which box it edits"
    assert not status, "the header stays in view, so the docked panel does not repeat its result line"
    assert isinstance(focused, Input)
    assert focused.id == "editor-input"
    assert highlighted == "05"
    row = next((line for line in lines if "[05]" in line), None)
    assert row is not None, "the row being edited stays in view above the panel"
    assert any("[01]" in line for line in lines), "its neighbours stay in view too"


@pytest.mark.asyncio
async def test_keep_and_go_to_next_moves_the_highlight_and_refills_the_panel_for_that_box() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = _workbench()
        app = ScreenHostApp(screen)
        async with app.run_test(size=_DOCKED) as pilot:
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            first = open_panel(screen)
            assert first is not None
            await pilot.press("enter")
            await _settle(pilot)
            refilled = open_panel(screen)
            assert refilled is not None
            title = _title(refilled)
            refilled_input = refilled.query_one("#editor-input", Input)
            prefilled = refilled_input.value
            focused = app.focused
            highlighted = _highlighted_box(screen)
            staged = [(change.field.box, change.value) for change in screen.staged_changes]
            on_top = app.screen

    assert on_top is screen
    assert refilled is not first
    assert highlighted == "07", "the list's highlight moved on to the next box that needs the filer"
    assert title.startswith("[07]")
    assert prefilled == "0.00", "the panel now holds the next box's assumed value, ready to confirm"
    assert focused is refilled_input
    assert staged == [("05", Decimal("100.00"))]


@pytest.mark.asyncio
async def test_on_the_shortest_docking_terminal_the_box_being_edited_shows_with_the_row_after_it() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=long_section_form(16)), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(120, 30)) as pilot:
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            for _ in range(10):
                await pilot.press("enter")
                await _settle(pilot)
            # Wait on what the filer would see, within a bound, rather than on a fixed number of pauses.
            for _ in range(_SHOWING_WAIT):
                panel = open_panel(screen)
                title = "" if panel is None else _title(panel)
                lines = _list_lines(screen)
                if title.startswith("[40]") and any("[41]" in line for line in lines):
                    break
                await pilot.pause()
            scrolled = screen.query_one(CasillaList).scroll_offset.y

    assert title.startswith("[40]")
    assert scrolled > 0, "the list scrolled to follow the box being edited"
    assert any("[40]" in line for line in lines), "the box being edited stays in view"
    assert any("[41]" in line for line in lines), "and the row after it shows too"


@pytest.mark.asyncio
async def test_escape_closes_the_docked_panel_gives_the_help_band_back_and_the_cursor_to_the_list() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = _workbench()
        app = ScreenHostApp(screen)
        async with app.run_test(size=_DOCKED) as pilot:
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            await pilot.press(*"42")
            await pilot.press("escape")
            await _settle(pilot)
            on_top = app.screen
            panel = open_panel(screen)
            focused = app.focused
            listed = screen.query_one(CasillaList)
            highlighted = _highlighted_box(screen)
            band = screen.query_one("#wb-help", Static)
            band_shown = band.display
            band_text = str(band.render())
            staged = screen.staged_changes

    assert on_top is screen, "Escape closes the panel, not the workbench"
    assert panel is None
    assert focused is listed
    assert highlighted == "05"
    assert band_shown
    assert "[05]" in band_text, "the help band returns, explaining the box under the cursor"
    assert staged == ()


@pytest.mark.asyncio
async def test_the_arrow_keys_in_the_panel_never_move_the_list_and_the_workbench_keys_wait() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = _workbench()
        app = ScreenHostApp(screen)
        async with app.run_test(size=_DOCKED) as pilot:
            await _settle(pilot)
            page_before = str(screen.query_one("#wb-page", Static).render())
            await pilot.press("enter")
            await _settle(pilot)
            await pilot.press("down", "down", "up", "down")
            await _settle(pilot)
            after_arrows = (_highlighted_box(screen), app.focused)
            panel = open_panel(screen)
            assert panel is not None
            panel.query_one("#editor-cancel", Button).focus()
            await _settle(pilot)
            await pilot.press("right_square_bracket", "f", "o", "q")
            await _settle(pilot)
            on_top = app.screen
            still_docked = open_panel(screen) is panel
            page_after = str(screen.query_one("#wb-page", Static).render())

    highlighted, focused = after_arrows
    assert highlighted == "05", "the arrow keys in the panel's input leave the list where it is"
    assert isinstance(focused, Input)
    assert on_top is screen, "q on the panel's button does not leave the workbench"
    assert still_docked
    assert page_after == page_before, "the page, filter and order keys wait while the filer is in the panel"


@pytest.mark.asyncio
async def test_the_list_stays_scrollable_with_the_mouse_while_the_panel_is_docked() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = _workbench()
        app = ScreenHostApp(screen)
        async with app.run_test(size=(120, 30)) as pilot:
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            docked = open_panel(screen) is not None
            listed = screen.query_one(CasillaList)
            assert listed.max_scroll_y > 0, "the list must be taller than its view for scrolling to show"
            listed.scroll_to(y=0, animate=False)
            await _settle(pilot)
            x, y = listed.region.x + 4, listed.region.y + 1
            under_mouse, _ = app.get_widget_at(x, y)
            for _ in range(3):
                app.post_message(
                    events.MouseScrollDown(
                        widget=None,
                        x=x,
                        y=y,
                        delta_x=0,
                        delta_y=1,
                        button=0,
                        shift=False,
                        meta=False,
                        ctrl=False,
                        screen_x=x,
                        screen_y=y,
                    )
                )
            await _settle(pilot)
            scrolled = listed.scroll_offset.y
            still_docked = open_panel(screen) is not None

    assert docked, "thirty rows is tall enough to dock"
    assert under_mouse is listed, "the panel leaves the list uncovered"
    assert scrolled > 0
    assert still_docked


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [_SHORT, (120, 29)])
async def test_below_thirty_rows_the_same_panel_opens_as_the_centred_dialog(size: tuple[int, int]) -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = _workbench()
        app = ScreenHostApp(screen)
        async with app.run_test(size=size) as pilot:
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            dialog = app.screen
            docked = open_panel(screen)
            assert isinstance(dialog, CasillaEditorScreen)
            panel = dialog.panel
            title = _title(panel)
            status = str(panel.query_one("#editor-status", Static).render())
            help_shown = screen.query_one("#wb-help").display
            await pilot.press("enter")
            await _settle(pilot)
            closed = app.screen is screen
            highlighted = _highlighted_box(screen)

    assert docked is None
    assert title.startswith("[05]")
    assert status, "the dialog covers the header, so the panel repeats its result line"
    assert help_shown, "the help band stays where it is under the dialog"
    assert closed, "keeping the value closes the dialog"
    assert highlighted == "07", "and moves the list on to the next box that needs the filer"


@pytest.mark.asyncio
async def test_a_docked_panel_keeps_what_was_typed_when_the_terminal_shrinks_below_thirty_rows() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = _workbench()
        app = ScreenHostApp(screen)
        async with app.run_test(size=_DOCKED) as pilot:
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            panel = open_panel(screen)
            assert panel is not None
            field_input = panel.query_one("#editor-input", Input)
            field_input.value = ""
            await pilot.press(*"250,5")
            await _settle(pilot)
            await pilot.resize_terminal(*_SHORT)
            await _settle(pilot)
            kept = open_panel(screen) is panel
            typed = panel.query_one("#editor-input", Input).value
            readback = str(panel.query_one("#editor-readback", Static).render())
            await pilot.press("ctrl+enter")
            await _settle(pilot)
            staged = [(change.field.box, change.value) for change in screen.staged_changes]
            closed = open_panel(screen) is None

    assert kept, "the open panel stays where it is until the filer closes it"
    assert typed == "250,5"
    assert "250,50" in readback
    assert staged == [("05", Decimal("250.5"))]
    assert closed, "keeping the value and staying closes the docked panel on its box"


@pytest.mark.asyncio
async def test_the_dialog_keeps_what_was_typed_when_the_terminal_grows_past_thirty_rows() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = _workbench()
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SHORT) as pilot:
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            dialog = app.screen
            assert isinstance(dialog, CasillaEditorScreen)
            dialog.panel.query_one("#editor-input", Input).value = ""
            await pilot.press(*"75")
            await _settle(pilot)
            await pilot.resize_terminal(*_DOCKED)
            await _settle(pilot)
            still_open = app.screen is dialog
            typed = dialog.panel.query_one("#editor-input", Input).value
            await pilot.press("ctrl+enter")
            await _settle(pilot)
            staged = [(change.field.box, change.value) for change in screen.staged_changes]
            docked = open_panel(screen)

    assert still_open
    assert typed == "75"
    assert staged == [("05", Decimal("75"))]
    assert docked is None, "a panel opens docked only when it is opened"


@pytest.mark.asyncio
async def test_a_docked_read_only_box_explains_itself_and_opens_the_area_that_owns_its_value() -> None:
    navigated: list[TuiNavigationTargetV1] = []
    with override_settings(cadrumo_output_language="en"):
        screen = _workbench(navigated)
        app = ScreenHostApp(screen)
        async with app.run_test(size=_DOCKED) as pilot:
            await _settle(pilot)
            await pilot.press("up")
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            panel = open_panel(screen)
            assert panel is not None
            read_only = panel.read_only
            inputs = list(panel.query(Input))
            area = panel.open_area
            focused = app.focused
            await pilot.press("a")
            await _settle(pilot)
            closed = open_panel(screen) is None

    assert read_only
    assert not inputs
    assert area is not None
    assert isinstance(focused, Button)
    assert focused.id == "editor-cancel"
    assert closed
    assert navigated == [surface_target(area)]
