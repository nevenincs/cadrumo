"""Real proofs that the TUI entry point starts a session rather than merely importing.

Every test here CALLS ``main`` and lets it drive a real Textual session to
completion through Textual's own headless driver. An entry point that
imports cleanly and fails to start is exactly the defect these prove
against, so none of them asserts on the symbol's existence or signature.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
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
from ...full_screen_session_protocol import SELF_TEST_FLAG
from ..__main__ import run
from ..account import AccountRecomposeReasonV1, AccountRecomposeRequiredV1
from ..app import CadrumoTuiApp
from ..devtools.home_fixtures import HomeFixtureScenario, build_home_projection_fixture
from ..launcher import (
    InstalledWorkbenchRootInputsV1,
    compose_installed_workbench_root,
    main,
    run_authenticated_workbench_sessions,
)

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
    return lambda _operation_runtime: _root_inputs(service)


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


def test_launcher_recomposes_with_a_fresh_provider_after_the_root_settles() -> None:
    """The outer owner receives no secret and never reuses the previous root."""
    mounted = 0
    requests: list[AccountRecomposeRequiredV1] = []

    async def request_recomposition(pilot: Pilot[object]) -> None:
        nonlocal mounted
        await pilot.pause()
        mounted += 1
        if mounted == 1:
            pilot.app.exit(AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.PASSWORD_CHANGED))
        else:
            pilot.app.exit()

    def recompose(outcome: AccountRecomposeRequiredV1):
        requests.append(outcome)
        return _root_inputs_provider()

    assert (
        asyncio.run(
            run_authenticated_workbench_sessions(
                headless=True,
                auto_pilot=request_recomposition,
                workbench_root_inputs_provider=_root_inputs_provider(),
                recompose_authenticated_session=recompose,
            )
        )
        is None
    )
    assert mounted == 2
    assert requests == [AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.PASSWORD_CHANGED)]


def test_entry_point_injects_and_rebuilds_the_installed_search_provider() -> None:
    """A real session installs one current generation and replaces it on return."""
    initial = WorkbenchSearchService(())
    refreshed = WorkbenchSearchService(())
    refreshed_inputs = cast(InstalledWorkbenchSearchInputsV1, _StaticSearchInputs(refreshed, _admissions()))
    supplied = [_root_inputs(initial, refresh_search=refreshed_inputs)]
    calls: list[InstalledWorkbenchRootInputsV1] = []

    def provider(_operation_runtime: object) -> InstalledWorkbenchRootInputsV1:
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


def test_module_entry_composes_the_production_session_rather_than_refusing(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Bare execution composes the installed session; it no longer fails closed.

    The refusal this once asserted was the gap, not the contract: the module
    is how ``aeat --tui`` starts, so an entry that printed
    ``workbench.root.composition_required`` and exited meant the product had
    no reachable workbench at all. What remains fail-closed is narrower and
    still proven here: against an empty profile store the self-test completes
    without inventing a profile to serve.
    """
    from ....tests.secure_sql import isolated_profile_storage_root

    with isolated_profile_storage_root(tmp_path=tmp_path):
        assert run([SELF_TEST_FLAG]) == 0

    assert "workbench.root.composition_required" not in capsys.readouterr().err
