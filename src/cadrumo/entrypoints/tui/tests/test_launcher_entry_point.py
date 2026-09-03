"""Real proofs that the TUI entry point starts a session rather than merely importing.

Every test here CALLS ``main`` and lets it drive a real Textual session to
completion through Textual's own headless driver. An entry point that
imports cleanly and fails to start is exactly the defect these prove
against, so none of them asserts on the symbol's existence or signature.
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest
from textual.screen import Screen

from ....application.search.installed_workbench import (
    InstalledWorkbenchSearchInputsV1,
    InstalledWorkbenchSearchSnapshotV1,
)
from ....application.search.workbench import (
    WorkbenchDestinationAdmission,
    WorkbenchDestinationAdmissionState,
    WorkbenchSearchService,
)
from ....core.i18n.render import tr
from ..__main__ import run
from ..app import CadrumoTuiApp
from ..devtools.home_fixtures import HomeFixtureScenario, build_home_projection_fixture
from ..launcher import InstalledWorkbenchRootInputsV1, compose_installed_workbench_root, main

if TYPE_CHECKING:
    from textual.pilot import Pilot

    from ..account import AccountFactoriesV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _StaticSearchInputs:
    """Minimal preloaded input double that crosses the real launcher seam."""

    def __init__(
        self,
        service: WorkbenchSearchService,
        admissions: dict[str, WorkbenchDestinationAdmission],
    ) -> None:
        self._service = service
        self.ledger_admission = admissions["workbench.ledger"]
        self.declarations_admission = admissions["workbench.declarations"]
        self.aeat_sync_admission = admissions["workbench.aeat_sync"]

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


def _admissions() -> dict[str, WorkbenchDestinationAdmission]:
    return {
        destination: WorkbenchDestinationAdmission(
            destination=destination, state=WorkbenchDestinationAdmissionState.AVAILABLE
        )
        for destination in (
            "workbench.home",
            "workbench.ledger",
            "workbench.declarations",
            "workbench.aeat_sync",
            "workbench.profile",
        )
    }


def _screen_factory(_: object) -> Screen[None]:
    return Screen()


def _root_inputs(
    service: WorkbenchSearchService | None = None,
    *,
    refresh_search: InstalledWorkbenchSearchInputsV1 | None = None,
) -> InstalledWorkbenchRootInputsV1:
    """Supply one coherent, preloaded generation through the root seam."""
    admissions = _admissions()
    search_inputs = cast(
        InstalledWorkbenchSearchInputsV1,
        _StaticSearchInputs(service or WorkbenchSearchService(()), admissions),
    )
    return InstalledWorkbenchRootInputsV1(
        home_projection=build_home_projection_fixture(HomeFixtureScenario.READY),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        admissions=admissions,
        account_factories=cast("AccountFactoriesV1", SimpleNamespace(profile=_screen_factory)),
        ledger_factory=_screen_factory,
        declarations_factory=_screen_factory,
        aeat_sync_factory=_screen_factory,
        search_inputs=search_inputs,
        refresh_search_inputs=lambda: refresh_search or search_inputs,
    )


def _root_inputs_provider(service: WorkbenchSearchService | None = None):
    """Return an explicit root generation provider without storage reads."""
    return lambda: _root_inputs(service)


def test_root_composition_preserves_existing_area_factories_and_refuses_search_admission_drift() -> None:
    """One source generation cannot make a palette route disagree with its screen."""
    inputs = _root_inputs()
    composition = compose_installed_workbench_root(inputs)

    assert composition.destination_catalogue.resolve("workbench.profile").factory is _screen_factory
    assert composition.destination_catalogue.resolve("workbench.ledger").factory is _screen_factory
    assert composition.destination_catalogue.resolve("workbench.declarations").factory is _screen_factory
    assert composition.destination_catalogue.resolve("workbench.aeat_sync").factory is _screen_factory

    drifted_admissions = dict(inputs.admissions)
    drifted_admissions["workbench.ledger"] = WorkbenchDestinationAdmission(
        destination="workbench.ledger",
        state=WorkbenchDestinationAdmissionState.LOCKED,
        reason_code="workbench.ledger.locked",
    )
    with pytest.raises(ValueError, match="search and root navigation admissions"):
        compose_installed_workbench_root(replace(inputs, admissions=drifted_admissions))


def test_entry_point_starts_a_real_session_and_exits_zero() -> None:
    """Running the entry point composes services, mounts the root, and settles."""
    mounted: list[str] = []

    async def observe(pilot: Pilot[object]) -> None:
        mounted.append(type(pilot.app).__name__)
        await pilot.pause()
        pilot.app.exit()

    assert main(headless=True, auto_pilot=observe, workbench_root_inputs_provider=_root_inputs_provider()) == 0
    assert mounted == [CadrumoTuiApp.__name__]


def test_entry_point_session_mounts_the_composed_home_and_hides_the_empty_placeholder() -> None:
    """A real root never replaces an installed composition with an empty shell."""
    rendered: list[object] = []

    async def capture(pilot: Pilot[object]) -> None:
        await pilot.pause()
        rendered.append(pilot.app.query_one("#root-no-areas").display)
        rendered.append(str(pilot.app.query_one("#root-title").render()))
        pilot.app.exit()

    assert main(headless=True, auto_pilot=capture, workbench_root_inputs_provider=_root_inputs_provider()) == 0
    assert rendered == [False, tr("tui.root.title")]


def test_entry_point_session_mounts_only_the_composed_home_screen() -> None:
    """The root starts at its one admitted Home body, not every destination."""
    screens: list[int] = []

    async def count_screens(pilot: Pilot[object]) -> None:
        await pilot.pause()
        screens.append(len(pilot.app.screen_stack))
        pilot.app.exit()

    assert main(headless=True, auto_pilot=count_screens, workbench_root_inputs_provider=_root_inputs_provider()) == 0
    assert screens == [2]


def test_entry_point_hands_the_session_its_composed_services() -> None:
    """The root runs against services composed outside it, never a graph of its own."""
    services: list[object] = []

    async def read_services(pilot: Pilot[object]) -> None:
        await pilot.pause()
        app = pilot.app
        assert isinstance(app, CadrumoTuiApp)
        services.append(app.services.submission)
        pilot.app.exit()

    assert main(headless=True, auto_pilot=read_services, workbench_root_inputs_provider=_root_inputs_provider()) == 0
    assert services and services[0] is not None


def test_entry_point_injects_and_rebuilds_the_installed_search_provider() -> None:
    """A real session installs one current generation and replaces it on return."""
    initial = WorkbenchSearchService(())
    refreshed = WorkbenchSearchService(())
    refreshed_inputs = cast(InstalledWorkbenchSearchInputsV1, _StaticSearchInputs(refreshed, _admissions()))
    supplied = [_root_inputs(initial, refresh_search=refreshed_inputs)]
    calls: list[InstalledWorkbenchRootInputsV1] = []

    def provider() -> InstalledWorkbenchRootInputsV1:
        current = supplied.pop(0)
        calls.append(current)
        return current

    async def inspect_search(pilot: Pilot[object]) -> None:
        await pilot.pause()
        app = pilot.app
        assert isinstance(app, CadrumoTuiApp)
        assert app.workbench_search_service is initial
        app._rebuild_workbench_search()
        assert app.workbench_search_service is refreshed
        assert app.workbench_search_refusal_code is None
        app.exit()

    assert main(headless=True, auto_pilot=inspect_search, workbench_root_inputs_provider=provider) == 0
    assert len(calls) == 1


def test_module_entry_refuses_missing_installed_root_composition(capsys: pytest.CaptureFixture[str]) -> None:
    """Bare execution cannot claim a root it was not given."""
    assert run([]) == 2
    assert capsys.readouterr().err == "workbench.root.composition_required\n"
