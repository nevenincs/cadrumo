"""Observe the public acknowledgement checkbox through its enabled Textual control."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from textual.pilot import Pilot
    from textual.widgets import Checkbox


async def _tick(pilot: Pilot[Any], box: Checkbox) -> bool:
    """Tick a checkbox as a filer does, with the space bar on it, and say whether it is ticked."""
    box.focus()
    await pilot.press("space")
    await pilot.pause()
    return box.value
