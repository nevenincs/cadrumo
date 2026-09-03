"""Real proofs that the TUI entry point starts a session rather than merely importing.

Every test here CALLS ``main`` and lets it drive a real Textual session to
completion through Textual's own headless driver. An entry point that
imports cleanly and fails to start is exactly the defect these prove
against, so none of them asserts on the symbol's existence or signature.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from ....application.search.installed_workbench import (
    InstalledWorkbenchSearchInputsV1,
    InstalledWorkbenchSearchSnapshotV1,
)
from ....application.search.workbench import WorkbenchSearchService
from ....core.i18n.render import tr
from ..__main__ import run
from ..app import CadrumoTuiApp
from ..launcher import main

if TYPE_CHECKING:
    from textual.pilot import Pilot

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _StaticSearchInputs:
    """Minimal preloaded input double that crosses the real launcher seam."""

    def __init__(self, service: WorkbenchSearchService) -> None:
        self._service = service

    def snapshot(self) -> InstalledWorkbenchSearchSnapshotV1:
        """Return an immutable snapshot whose service is the supplied exact generation."""
        return cast(InstalledWorkbenchSearchSnapshotV1, _StaticSearchSnapshot(self._service))


class _StaticSearchSnapshot:
    """Return a prebuilt service without making the launcher read any state."""

    def __init__(self, service: WorkbenchSearchService) -> None:
        self._service = service

    def service(self) -> WorkbenchSearchService:
        """Expose the generation this input provider selected."""
        return self._service


def _inputs_provider(service: WorkbenchSearchService | None = None) -> InstalledWorkbenchSearchInputsV1:
    """Supply preloaded inputs as an installed-session composition would."""
    return cast(InstalledWorkbenchSearchInputsV1, _StaticSearchInputs(service or WorkbenchSearchService(())))


def test_entry_point_starts_a_real_session_and_exits_zero() -> None:
    """Running the entry point composes services, mounts the root, and settles."""
    mounted: list[str] = []

    async def observe(pilot: Pilot[object]) -> None:
        mounted.append(type(pilot.app).__name__)
        await pilot.pause()
        pilot.app.exit()

    assert main(headless=True, auto_pilot=observe, workbench_search_inputs_provider=_inputs_provider) == 0
    assert mounted == [CadrumoTuiApp.__name__]


def test_entry_point_session_renders_the_areas_it_has_not_mounted() -> None:
    """The root states the unmounted condition on screen instead of implying areas exist."""
    rendered: list[str] = []

    async def capture(pilot: Pilot[object]) -> None:
        await pilot.pause()
        rendered.append(str(pilot.app.query_one("#root-no-areas").render()))
        rendered.append(str(pilot.app.query_one("#root-title").render()))
        pilot.app.exit()

    assert main(headless=True, auto_pilot=capture, workbench_search_inputs_provider=_inputs_provider) == 0
    assert rendered == [tr("tui.root.no_areas"), tr("tui.root.title")]


def test_entry_point_session_mounts_no_area_screen() -> None:
    """No area is joined yet, so the root must carry no area screen at all."""
    screens: list[int] = []

    async def count_screens(pilot: Pilot[object]) -> None:
        await pilot.pause()
        screens.append(len(pilot.app.screen_stack))
        pilot.app.exit()

    assert main(headless=True, auto_pilot=count_screens, workbench_search_inputs_provider=_inputs_provider) == 0
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

    assert main(headless=True, auto_pilot=read_services, workbench_search_inputs_provider=_inputs_provider) == 0
    assert services and services[0] is not None


def test_entry_point_injects_and_rebuilds_the_installed_search_provider() -> None:
    """A real session installs one current generation and replaces it on return."""
    initial = WorkbenchSearchService(())
    refreshed = WorkbenchSearchService(())
    supplied = [_inputs_provider(initial), _inputs_provider(refreshed)]
    calls: list[InstalledWorkbenchSearchInputsV1] = []

    def provider() -> InstalledWorkbenchSearchInputsV1:
        current = supplied.pop(0)
        calls.append(current)
        return current

    async def inspect_search(pilot: Pilot[object]) -> None:
        await pilot.pause()
        app = pilot.app
        assert isinstance(app, CadrumoTuiApp)
        assert app.workbench_search_service is initial
        app._on_destination_dismissed(None)
        assert app.workbench_search_service is refreshed
        assert app.workbench_search_refusal_code is None
        app.exit()

    assert main(headless=True, auto_pilot=inspect_search, workbench_search_inputs_provider=provider) == 0
    assert len(calls) == 2


def test_module_entry_refuses_missing_installed_search_composition(capsys: pytest.CaptureFixture[str]) -> None:
    """Bare module execution cannot claim a search snapshot it was not given."""
    assert run([]) == 2
    assert capsys.readouterr().err == "workbench.search.composition_required\n"
