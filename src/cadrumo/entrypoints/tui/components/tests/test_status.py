"""Pilot-driven proofs for the reusable pinned TUI status channel."""

from __future__ import annotations

from typing import override

import pytest
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from ..status import PinnedStatusBar

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_TERMINAL_SIZE = (100, 24)


class _StatusBarHarness(App[None]):
    """Real Textual host used only to mount and scroll the production widget."""

    CSS = """
    VerticalScroll { height: 1fr; }
    .scroll-row { height: 1; }
    """

    @override
    def compose(self) -> ComposeResult:
        yield PinnedStatusBar(summary="Profile 2 / 5", id="status")
        with VerticalScroll(id="body"):
            for row in range(40):
                yield Static(f"row {row}", classes="scroll-row", markup=False)


@pytest.mark.asyncio
async def test_status_bar_stays_pinned_and_preserves_plain_multiline_diagnostics() -> None:
    app = _StatusBarHarness()
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        bar = app.query_one("#status", PinnedStatusBar)
        initial_y = bar.region.y

        diagnostic = "Open Cl@ve verification\nCode: [bold]834-221[/bold]\nReturn here after approval"
        bar.show_progress(diagnostic)
        await pilot.pause()

        assert bar.tone == "progress"
        assert bar.message == diagnostic
        assert bar.region.height >= 4, "the pinned channel must grow to show every diagnostic line"
        message_line = bar.query_one(".status-message", Static)
        assert "[bold]834-221[/bold]" in str(message_line.content), (
            "operator text resembling Rich markup must remain literal"
        )

        body = app.query_one("#body", VerticalScroll)
        body.scroll_end(animate=False)
        await pilot.pause()

        assert body.scroll_y > 0
        assert bar.region.y == initial_y, "scrolling the content body must not move the status channel"


@pytest.mark.asyncio
async def test_status_bar_exposes_each_closed_tone_and_keeps_a_supplied_summary() -> None:
    app = _StatusBarHarness()
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        bar = app.query_one("#status", PinnedStatusBar)
        height = bar.region.height

        for tone, render in (
            ("success", bar.show_success),
            ("warning", bar.show_warning),
            ("error", bar.show_error),
        ):
            render(f"{tone} message")
            await pilot.pause()
            assert bar.tone == tone
            assert bar.message == f"{tone} message"
            assert bar.has_class(f"tone-{tone}")

        bar.clear_message()
        await pilot.pause()
        assert bar.tone == "idle"
        assert bar.message == ""
        assert bar.region.height >= height


@pytest.mark.asyncio
async def test_status_bar_renders_progress_text_exactly_as_supplied() -> None:
    """Progress policy belongs to the caller; this widget only presents its text."""
    app = _StatusBarHarness()
    supplied = "Waiting for the browser confirmation. Time remaining: 1:59."
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        bar = app.query_one("#status", PinnedStatusBar)
        bar.show_progress(supplied)
        await pilot.pause()

        assert bar.tone == "progress"
        assert bar.message == supplied


@pytest.mark.asyncio
async def test_status_bar_without_a_summary_collapses_when_idle() -> None:
    """A screen with no operation under way must not carry an empty header row."""

    class _TransientHarness(App[None]):
        @override
        def compose(self) -> ComposeResult:
            yield PinnedStatusBar(id="status")
            yield Static("body", id="body")

    app = _TransientHarness()
    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        bar = app.query_one("#status", PinnedStatusBar)
        assert not bar.display

        bar.show_progress("Working")
        await pilot.pause()
        assert bar.display
        assert bar.region.height > 0

        bar.clear_message()
        await pilot.pause()
        assert not bar.display
