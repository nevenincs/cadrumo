"""Pilot-driven proofs for the permanent TUI status channel."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from .._status_bar import PinnedStatusBar

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]

_TERMINAL_SIZE = (100, 24)


class _StatusBarHarness(App[None]):
    """Real Textual host used only to mount and scroll the production widget."""

    CSS = """
    VerticalScroll { height: 1fr; }
    .scroll-row { height: 1; }
    """

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
async def test_status_bar_exposes_each_closed_tone_and_clear_keeps_reserved_space() -> None:
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
