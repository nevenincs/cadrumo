"""Render real Textual widgets for terminal palette acceptance tests."""

from __future__ import annotations

import asyncio
import json
from typing import override

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static

from ..components.host import ScreenHostApp


class ThemeSample(Screen[None]):
    """Representative styled content, including borders and editable state."""

    @override
    def compose(self) -> ComposeResult:
        """Build ordinary production-styled widgets."""
        yield Label("Theme sample", classes="cadrumo-banner")
        with Vertical(classes="cadrumo-panel") as panel:
            panel.border_title = "Panel title"
            yield Static("Existing content")
            yield Static("Muted detail", classes="cadrumo-subtle")
            yield Input(value="unsaved edit")
            yield Button("Continue", variant="primary")


async def render_sample() -> str:
    """Capture ANSI bytes from Textual's real styled strips."""
    app = ScreenHostApp(ThemeSample())
    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.pause(0.2)
        lines = app.screen._compositor.render_strips()
        return "\x1b[2J\x1b[H" + "".join(
            f"\x1b[{row + 1};1H"
            + "".join(segment.style.render(segment.text) if segment.style else segment.text for segment in line)
            for row, line in enumerate(lines)
        )


if __name__ == "__main__":
    print(json.dumps(asyncio.run(render_sample())))
