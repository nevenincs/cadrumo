"""Pilot clicks that wait until the target's screen position is final."""

from __future__ import annotations

import asyncio

from textual.errors import NoWidget
from textual.geometry import Offset, Region, Size
from textual.pilot import Pilot
from textual.screen import Screen
from textual.widget import Widget

from cadrumo.entrypoints.tui.tests.settling import SETTLE_TIMEOUT_SECONDS, settle

type _Geometry = tuple[tuple[Region, Size, Offset], ...]


def _geometry(screen: Screen[object]) -> _Geometry:
    """Every widget's screen region, scrollable size and scroll position."""
    return tuple(
        (node.region, node.virtual_size, node.scroll_offset) for node in screen.walk_children(Widget, with_self=True)
    )


def _uncovered(screen: Screen[object], widget: Widget, region: Region) -> bool:
    """Whether the widget lies wholly on screen and is the topmost widget at its centre."""
    if not region or not screen.region.contains_region(region):
        return False
    try:
        found, _ = screen.get_widget_at(region.x + region.width // 2, region.y + region.height // 2)
    except NoWidget:
        return False
    return found is widget


async def click_when_laid_out[ResultT](
    pilot: Pilot[ResultT], widget: Widget, *, timeout: float = SETTLE_TIMEOUT_SECONDS
) -> bool:
    """Click the widget's centre once a full refresh leaves the screen's layout unchanged.

    ``Pilot.click`` reads the target position from the last composited frame and
    only then lets the app process pending work. A deferred scroll, or the second
    layout pass that follows a scrollbar appearing or disappearing, can still be
    queued at that moment; the widget then moves and the click lands on whatever
    took its place. A pause that changes no widget's geometry has left no such
    pass queued, so the position read after it is the one the click reaches.
    """
    screen = pilot.app.screen
    async with asyncio.timeout(timeout):
        while True:
            before = _geometry(screen)
            await settle(pilot, workers=False)
            region = widget.region
            if _geometry(screen) == before and _uncovered(screen, widget, region):
                break
    return await pilot.click(widget, offset=(region.width // 2, region.height // 2))
