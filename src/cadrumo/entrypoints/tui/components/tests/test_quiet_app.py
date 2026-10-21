"""A Cadrumo app holds a focused text cursor steady, so an idle screen repaints nothing."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from typing import override

import pytest
from textual.app import App, ComposeResult, RenderResult
from textual.screen import Screen
from textual.strip import Strip
from textual.widgets import Input
from textual.worker import WorkerFailed

from ..host import ScreenHostApp
from ..quiet_app import QuietApp, TuiRunFailedError
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


class _FailingScreen(Screen[None]):
    def on_mount(self) -> None:
        raise ValueError("synthetic TUI failure")


def test_production_sync_run_raises_hosted_screen_failure_after_shutdown() -> None:
    app = ScreenHostApp(_FailingScreen())
    with pytest.raises(ValueError, match="synthetic TUI failure"):
        app.run(headless=True)
    assert app.return_code == 1
    assert not app.is_running


@pytest.mark.asyncio
@pytest.mark.parametrize("worker", [False, True])
async def test_production_async_run_raises_event_and_worker_failures(
    caplog: pytest.LogCaptureFixture, *, worker: bool
) -> None:
    error = ValueError("synthetic TUI failure")

    class FailingApp(QuietApp[None]):
        def on_mount(self) -> None:
            if worker:
                self.run_worker(self.fail())
            else:
                self.call_later(self.fail_event)

        def fail_event(self) -> None:
            raise error

        async def fail(self) -> None:
            raise error

    app = FailingApp()
    with pytest.raises(WorkerFailed if worker else ValueError) as caught:
        await app.run_async(headless=True)
    if not worker:
        assert caught.value is error
    assert app.return_code == 1
    assert not app.is_running
    diagnostic = next(record for record in caplog.records if record.getMessage() == "tui_application_failed")
    assert diagnostic.__dict__["error_type"] == ("WorkerFailed" if worker else "ValueError")
    assert diagnostic.__dict__["exit_code"] == 1
    assert diagnostic.__dict__["outcome"] == "failed"
    assert diagnostic.exc_info is None


@pytest.mark.asyncio
async def test_production_run_preserves_normal_return_value() -> None:
    class NormalApp(QuietApp[str]):
        def on_mount(self) -> None:
            self.exit("complete")

    app = NormalApp()
    assert await app.run_async(headless=True) == "complete"
    assert app.return_code == 0


@pytest.mark.asyncio
async def test_explicit_failure_exit_cannot_be_mistaken_for_dismissal() -> None:
    class RefusedApp(QuietApp[None]):
        def on_mount(self) -> None:
            self.exit(return_code=7)

    with pytest.raises(TuiRunFailedError) as caught:
        await RefusedApp().run_async(headless=True)
    assert caught.value.exit_code == 7


def test_crashed_tui_child_process_exits_with_failure() -> None:
    """Exercise the production runner outside pytest's exception-handling loop."""
    child = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            (
                "from cadrumo.entrypoints.tui.components.quiet_app import QuietApp\n"
                "class BrokenApp(QuietApp):\n"
                "    def on_mount(self):\n"
                "        raise ValueError('synthetic child crash')\n"
                "BrokenApp().run(headless=True)\n"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert child.returncode != 0
    assert "ValueError: synthetic child crash" in child.stderr
