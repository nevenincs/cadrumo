"""A Cadrumo app holds a focused text cursor steady, so an idle screen repaints nothing."""

from __future__ import annotations

import asyncio
from typing import override

import pytest
from textual.app import App, ComposeResult, RenderResult
from textual.strip import Strip
from textual.widgets import Input

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


class _QuietHarness(QuietApp, App[None]):
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
