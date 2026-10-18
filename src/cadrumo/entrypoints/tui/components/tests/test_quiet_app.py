"""A Cadrumo app holds a focused text cursor steady, so an idle screen repaints nothing."""

from __future__ import annotations

import asyncio
import sys
from typing import override

import pytest
from textual.app import App, ComposeResult, RenderResult
from textual.screen import Screen
from textual.strip import Strip
from textual.widgets import Input

from ..host import ScreenHostApp
from ..quiet_app import QuietApp
from ..status import ProgressLine

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _CountedInput(Input):
    renders = 0

    @override
    def render_line(self, y: int) -> Strip:
        if y == 0:
            self.renders += 1
        return super().render_line(y)


class _QuietHarness(QuietApp[None]):
    @override
    def compose(self) -> ComposeResult:
        yield _CountedInput(id="search")


@pytest.mark.asyncio
async def test_a_focused_input_in_a_cadrumo_app_does_not_repaint_while_idle() -> None:
    app = _QuietHarness()
    async with app.run_test(size=(40, 5)) as pilot:
        field = app.query_one("#search", _CountedInput)
        field.focus()
        await pilot.pause()
        assert app.focused is field
        assert field.cursor_blink is False
        settled = field.renders
        # Well past two half-second blink periods.
        await asyncio.sleep(1.3)
        await pilot.pause()
        assert field.renders == settled, "a focused cursor kept repainting the idle screen"


class _CountedLine(ProgressLine):
    renders = 0

    @override
    def render(self) -> RenderResult:
        self.renders += 1
        return super().render()


class _LineHarness(App[None]):
    @override
    def compose(self) -> ComposeResult:
        yield _CountedLine(id="progress")


@pytest.mark.asyncio
async def test_a_progress_line_repaints_only_when_its_progress_changes() -> None:
    app = _LineHarness()
    async with app.run_test(size=(40, 3)) as pilot:
        line = app.query_one("#progress", _CountedLine)
        line.update(total=4, progress=1)
        await pilot.pause()
        settled = line.renders
        # Past the one-second interval Textual's ProgressBar re-renders on.
        await asyncio.sleep(1.3)
        await pilot.pause()
        assert line.renders == settled, "an unchanged progress line repainted while idle"
        line.update(total=4, progress=2)
        await pilot.pause()
        assert line.renders > settled
        assert (line.progress, line.total) == (2, 4)


class _InputScreen(Screen[None]):
    @override
    def compose(self) -> ComposeResult:
        yield _CountedInput(id="field")


@pytest.mark.asyncio
async def test_a_screen_run_as_its_own_process_is_as_quiet_as_the_workbench() -> None:
    """The host for registration, credential and installation screens takes the same quiet base."""
    host = ScreenHostApp(_InputScreen())
    if sys.platform == "win32":
        assert host.driver_class.__name__ == "QuietWindowsDriver"
    async with host.run_test(size=(40, 5)) as pilot:
        await pilot.pause()
        field = host.screen.query_one("#field", _CountedInput)
        field.focus()
        await pilot.pause()
        assert field.cursor_blink is False
        settled = field.renders
        await asyncio.sleep(1.3)
        await pilot.pause()
        assert field.renders == settled, "a hosted screen's cursor kept repainting the idle screen"


@pytest.mark.parametrize(("value", "monochrome"), [("false", False), ("0", False), ("true", True), ("1", True)])
def test_no_color_is_read_as_the_boolean_cadrumo_declares(
    monkeypatch: pytest.MonkeyPatch, value: str, *, monochrome: bool
) -> None:
    """``NO_COLOR=false`` keeps colour, as it does in the CLI; Textual alone reads any value as monochrome."""
    monkeypatch.setenv("TERM_PROGRAM", "WindowsTerminal")
    monkeypatch.setenv("NO_COLOR", value)
    assert ScreenHostApp(_InputScreen()).no_color is monochrome
