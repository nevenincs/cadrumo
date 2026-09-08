"""Behavioral proof that the shared status component stays render-only."""

from __future__ import annotations

from typing import override

import pytest
from textual.app import App, ComposeResult
from textual.widgets import LoadingIndicator

from ..status import PinnedStatusBar

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _StatusHarness(App[None]):
    @override
    def compose(self) -> ComposeResult:
        yield PinnedStatusBar(summary="Sync", id="status")


@pytest.mark.asyncio
async def test_status_bar_spinner_is_visible_only_while_the_tone_is_progress() -> None:
    """The spinner reflects the caller's closed tone, never an operation state it reads itself."""
    app = _StatusHarness()
    async with app.run_test(size=(80, 24)) as pilot:
        bar = app.query_one("#status", PinnedStatusBar)
        spinner = bar.query_one(LoadingIndicator)

        assert not spinner.display, "an idle bar must not show a spinner"

        bar.show_progress("Working")
        await pilot.pause()
        assert spinner.display, "the progress tone must reveal the spinner"

        bar.show_success("Done")
        await pilot.pause()
        assert not spinner.display, "a final outcome tone must hide the spinner"

        bar.show_warning("Careful")
        await pilot.pause()
        assert not spinner.display

        bar.show_error("Failed")
        await pilot.pause()
        assert not spinner.display
