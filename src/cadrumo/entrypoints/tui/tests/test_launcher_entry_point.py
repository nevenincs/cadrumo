"""Real proofs that the TUI entry point starts a session rather than merely importing.

Every test here CALLS ``main`` and lets it drive a real Textual session to
completion through Textual's own headless driver. An entry point that
imports cleanly and fails to start is exactly the defect these prove
against, so none of them asserts on the symbol's existence or signature.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ....core.i18n import tr
from ..app import CadrumoTuiApp
from ..launcher import main

if TYPE_CHECKING:
    from textual.pilot import Pilot

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_entry_point_starts_a_real_session_and_exits_zero() -> None:
    """Running the entry point composes services, mounts the root, and settles."""
    mounted: list[str] = []

    async def observe(pilot: Pilot[object]) -> None:
        mounted.append(type(pilot.app).__name__)
        await pilot.pause()
        pilot.app.exit()

    assert main(headless=True, auto_pilot=observe) == 0
    assert mounted == [CadrumoTuiApp.__name__]


def test_entry_point_session_renders_the_areas_it_has_not_mounted() -> None:
    """The root states the unmounted condition on screen instead of implying areas exist."""
    rendered: list[str] = []

    async def capture(pilot: Pilot[object]) -> None:
        await pilot.pause()
        rendered.append(str(pilot.app.query_one("#root-no-areas").render()))
        rendered.append(str(pilot.app.query_one("#root-title").render()))
        pilot.app.exit()

    assert main(headless=True, auto_pilot=capture) == 0
    assert rendered == [tr("tui.root.no_areas"), tr("tui.root.title")]


def test_entry_point_session_mounts_no_area_screen() -> None:
    """No area is joined yet, so the root must carry no area screen at all."""
    screens: list[int] = []

    async def count_screens(pilot: Pilot[object]) -> None:
        await pilot.pause()
        screens.append(len(pilot.app.screen_stack))
        pilot.app.exit()

    assert main(headless=True, auto_pilot=count_screens) == 0
    assert screens == [1]


def test_entry_point_hands_the_session_its_composed_services() -> None:
    """The root runs against services composed outside it, never a graph of its own."""
    services: list[object] = []

    async def read_services(pilot: Pilot[object]) -> None:
        await pilot.pause()
        app = pilot.app
        assert isinstance(app, CadrumoTuiApp)
        services.append(app.services.submission)
        pilot.app.exit()

    assert main(headless=True, auto_pilot=read_services) == 0
    assert services and services[0] is not None
