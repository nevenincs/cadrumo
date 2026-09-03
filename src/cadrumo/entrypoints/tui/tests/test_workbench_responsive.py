"""Home and every principal workspace, proven to fit the terminals we support.

The sibling responsive suite covers the Modelo workspace destinations. This one
covers what the operator actually lands on: Home and the routed Ledger,
Declarations, AEAT Sync and Profile destinations composed by the installed
session. Nothing here declares a terminal size of its own — the shared
declaration is the single authority on which sizes matter.

Assertions are geometric, not textual. Vertical overflow is ordinary and
scrollable; horizontal overflow silently removes information, and a screen that
resolves to nothing at the floor has failed rather than adapted. Both are read
from the mounted regions rather than a rendered frame, because a frame is
clipped at the edge and looks identical either way.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widget import Widget

from ....tests.terminal_sizes import SUPPORTED_TERMINAL_SIZES
from ..components.host import ScreenHostApp
from ..components.theme import CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME
from ..navigation import TuiScreenContextV1
from .workbench_session import installed_workbench_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_THEMES = (CADRUMO_LIGHT_THEME_NAME, CADRUMO_DARK_THEME_NAME)


@pytest.mark.asyncio
async def test_no_workbench_destination_pushes_content_past_the_right_edge(tmp_path: Path) -> None:
    """Columns past the right edge are unreachable, so none may exist."""
    async with installed_workbench_root(tmp_path) as root:
        for route in root.destination_catalogue.routes:
            if route.factory is None:
                continue
            destination = route.descriptor.destination
            for size in SUPPORTED_TERMINAL_SIZES:
                width, _height = size
                app = ScreenHostApp(route.factory(TuiScreenContextV1(destination=destination)))
                async with app.run_test(size=size) as pilot:
                    await pilot.pause()
                    overflowing = [
                        widget for widget in app.screen.query(Widget) if widget.display and widget.region.right > width
                    ]
                    assert not overflowing, (
                        f"{destination} at {width} columns pushes "
                        + ", ".join(
                            f"{type(widget).__name__}(id={widget.id!r}) to x={widget.region.right}"
                            for widget in overflowing[:5]
                        )
                        + " past the right edge, where the operator cannot reach it"
                    )
                    app.exit(None)


@pytest.mark.asyncio
async def test_every_workbench_destination_paints_content_at_every_supported_size(tmp_path: Path) -> None:
    """A destination that mounts blank at the floor has failed, not adapted."""
    async with installed_workbench_root(tmp_path) as root:
        for route in root.destination_catalogue.routes:
            if route.factory is None:
                continue
            destination = route.descriptor.destination
            for size in SUPPORTED_TERMINAL_SIZES:
                app = ScreenHostApp(route.factory(TuiScreenContextV1(destination=destination)))
                async with app.run_test(size=size) as pilot:
                    await pilot.pause()
                    painted = [
                        widget
                        for widget in app.screen.query(Widget)
                        if widget.display and widget.region.height > 0 and widget.region.width > 0
                    ]
                    assert painted, f"{destination} rendered nothing at {size}"
                    app.exit(None)


@pytest.mark.asyncio
async def test_home_keeps_one_scrollable_owner_rather_than_nesting_them(tmp_path: Path) -> None:
    """Two nested scrollers make a keyboard operator guess which one moves.

    Home is the surface this matters most on: it is the return point from
    every journey, so a scroll position that lands in the wrong container is
    met again after every child dismissal.
    """
    from textual.containers import ScrollableContainer

    async with installed_workbench_root(tmp_path) as root:
        home = root.destination_catalogue.resolve("workbench.home")
        assert home.factory is not None
        for size in SUPPORTED_TERMINAL_SIZES:
            app = ScreenHostApp(home.factory(TuiScreenContextV1(destination="workbench.home")))
            async with app.run_test(size=size) as pilot:
                await pilot.pause()
                scrollers = [
                    widget
                    for widget in app.screen.query(ScrollableContainer)
                    if widget.display and widget.show_vertical_scrollbar
                ]
                assert len(scrollers) <= 1, f"Home offers {len(scrollers)} competing scrollable owners at {size}"
                app.exit(None)


@pytest.mark.asyncio
async def test_home_renders_under_both_appearances(tmp_path: Path) -> None:
    """Appearance is a palette swap, never a change to what is on the page."""
    async with installed_workbench_root(tmp_path) as root:
        home = root.destination_catalogue.resolve("workbench.home")
        assert home.factory is not None
        painted: dict[str, int] = {}
        for theme in _THEMES:
            app = ScreenHostApp(home.factory(TuiScreenContextV1(destination="workbench.home")))
            async with app.run_test(size=SUPPORTED_TERMINAL_SIZES[-1]) as pilot:
                app.theme = theme
                await pilot.pause()
                painted[theme] = len([widget for widget in app.screen.query(Widget) if widget.display])
                app.exit(None)

        assert len(set(painted.values())) == 1, f"appearance changed the mounted content: {painted}"
