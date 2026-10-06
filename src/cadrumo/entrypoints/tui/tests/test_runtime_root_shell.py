"""A precomposed TUI root can run without a second local operation graph."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
from threading import Event
from typing import TYPE_CHECKING, cast

import pytest
from textual.screen import Screen

from ....application.search.workbench import WorkbenchDestinationAdmission, WorkbenchDestinationAdmissionState
from ..account import AccountFactoriesV1, AccountRecomposeReasonV1, AccountRecomposeRequiredV1
from ..app import CadrumoTuiApp, RootBindingV1
from ..home import HomeScreen
from ..launcher import run_precomposed_runtime_root_session
from ..navigation import (
    TuiFocusIdentityV1,
    TuiNavigationTargetV1,
    build_destination_catalogue,
    declared_destination_ids,
)
from ..search import WorkbenchSearchDoorV1
from .home_fixtures import HomeFixtureScenario, build_home_projection_fixture

if TYPE_CHECKING:
    from textual.pilot import Pilot

    from ....application.overview.home import HomeProjectionV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _screen(_context: object) -> Screen[None]:
    return Screen()


def _root(*, child_factory: Callable[[object], Screen[None]] | None = None) -> RootBindingV1:
    destinations = declared_destination_ids()
    admissions = {
        destination: WorkbenchDestinationAdmission(
            destination=destination, state=WorkbenchDestinationAdmissionState.AVAILABLE
        )
        for destination in destinations
    }
    catalogue = build_destination_catalogue(
        admissions=admissions,
        factories={
            destination: child_factory if destination == "workbench.ledger" and child_factory is not None else _screen
            for destination in destinations
        },
    )
    account = object.__new__(AccountFactoriesV1)
    object.__setattr__(account, "subscribe_retirement", None)
    object.__setattr__(account, "profile", _screen)
    object.__setattr__(account, "password", lambda: Screen())
    object.__setattr__(account, "access", None)
    object.__setattr__(account, "onboarding_pending", False)
    return RootBindingV1(
        destination_catalogue=catalogue,
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        workbench_search_service=None,
        refresh_workbench_search=None,
        refresh_destination_catalogue=None,
        account_factories=account,
        read_account_session=None,
    )


def _ledger_target() -> TuiNavigationTargetV1:
    return TuiNavigationTargetV1(
        destination="workbench.ledger",
        focus=TuiFocusIdentityV1(destination="workbench.ledger", semantic_key="ledger.overview"),
    )


def test_precomposed_root_uses_injected_doors_without_local_operation_services() -> None:
    loaded: list[RootBindingV1] = []
    mounted: list[object] = []
    root = _root()

    def load_root() -> RootBindingV1:
        loaded.append(root)
        return root

    async def inspect(pilot: Pilot[object]) -> None:
        await pilot.pause()
        app = pilot.app
        assert isinstance(app, CadrumoTuiApp)
        mounted.append(isinstance(app.screen, HomeScreen))
        mounted.append(app.destination_catalogue is root.destination_catalogue)
        assert not hasattr(app, "services")
        app.exit()

    assert (
        asyncio.run(run_precomposed_runtime_root_session(load_root=load_root, headless=True, auto_pilot=inspect))
        is None
    )
    assert loaded == [root]
    assert mounted == [True, True]


def test_pushed_retirement_severs_precomposed_root() -> None:
    root = _root()
    callbacks: list[Callable[[], None]] = []

    def subscribe(receive: Callable[[], None]) -> Callable[[], None]:
        callbacks.append(receive)
        return lambda: callbacks.remove(receive)

    object.__setattr__(root.account_factories, "subscribe_retirement", subscribe)

    async def retire(pilot: Pilot[object]) -> None:
        await pilot.pause()
        assert len(callbacks) == 1
        callbacks[0]()
        await pilot.pause()
        app = pilot.app
        assert isinstance(app, CadrumoTuiApp)
        assert app._destination_catalogue is None
        assert not callbacks

    outcome = asyncio.run(
        run_precomposed_runtime_root_session(load_root=lambda: root, headless=True, auto_pilot=retire)
    )
    assert outcome is not None and outcome.reason is AccountRecomposeReasonV1.EXPIRED


@pytest.mark.asyncio
async def test_cancelled_root_read_retains_ownership_until_blocking_read_finishes() -> None:
    """Closing a frontend cannot leave its private loader running unowned."""
    started = asyncio.Event()
    release = Event()
    finished = Event()
    loop = asyncio.get_running_loop()
    root = _root()

    def load_root() -> RootBindingV1:
        loop.call_soon_threadsafe(started.set)
        if not release.wait(5):
            raise TimeoutError("test root read was not released")
        finished.set()
        return root

    app = CadrumoTuiApp()
    async with app.run_test():
        app._load_root = load_root
        reading = asyncio.create_task(app._open_root(load_root))
        try:
            await asyncio.wait_for(started.wait(), 5)
            reading.cancel()
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(reading), 0.02)
            reading.cancel()
            assert not finished.is_set()
        finally:
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(reading, 5)
        assert finished.is_set()
        assert app._account_factories is None


@pytest.mark.asyncio
async def test_late_search_result_cannot_restore_severed_private_presentation() -> None:
    """A completed old capture cannot repopulate the root after account loss."""
    started = asyncio.Event()
    release = Event()
    loop = asyncio.get_running_loop()
    private_search = cast(WorkbenchSearchDoorV1, object())

    def refresh_search() -> WorkbenchSearchDoorV1:
        loop.call_soon_threadsafe(started.set)
        if not release.wait(5):
            raise TimeoutError("test search read was not released")
        return private_search

    app = CadrumoTuiApp(refresh_workbench_search=refresh_search)
    async with app.run_test():
        reading = asyncio.create_task(app._rebuild_workbench_search())
        try:
            await asyncio.wait_for(started.wait(), 5)
            app._request_recompose(AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED))
        finally:
            release.set()
            await asyncio.wait_for(reading, 5)
        assert app._workbench_search_service is None
        assert app._load_root is None
        assert app.account_session is None


@pytest.mark.asyncio
async def test_root_read_failure_is_a_safe_refusal_without_rendering_exception(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An invalid private result must not become a Textual exception screen."""
    private_value = "synthetic-private-loader-value"

    def refuse() -> RootBindingV1:
        raise ValueError(private_value)

    app = CadrumoTuiApp(load_root=refuse)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert app._home_refresh_refusal_code == "workbench.home.refresh_unavailable"
        assert app._account_factories is None
    captured = capsys.readouterr()
    assert private_value not in captured.out + captured.err


@pytest.mark.asyncio
async def test_blocked_initial_home_read_cannot_replace_newly_selected_child() -> None:
    started = asyncio.Event()
    release = Event()
    finished = asyncio.Event()
    loop = asyncio.get_running_loop()
    mounted: list[Screen[None]] = []

    def child_factory(_context: object) -> Screen[None]:
        screen: Screen[None] = Screen()
        mounted.append(screen)
        return screen

    def refresh_home() -> HomeProjectionV1:
        loop.call_soon_threadsafe(started.set)
        if not release.wait(5):
            raise TimeoutError("test Home read was not released")
        loop.call_soon_threadsafe(finished.set)
        return build_home_projection_fixture(HomeFixtureScenario.READY)

    root = replace(_root(child_factory=child_factory), refresh_home=refresh_home)
    app = CadrumoTuiApp(
        destination_catalogue=root.destination_catalogue,
        refresh_home=root.refresh_home,
        account_factories=root.account_factories,
    )
    async with app.run_test() as pilot:
        try:
            await asyncio.wait_for(started.wait(), 5)
            app.navigate_to(_ledger_target())
            await pilot.pause()
            assert len(mounted) == 1 and app.screen is mounted[0]
        finally:
            release.set()
        await asyncio.wait_for(finished.wait(), 5)
        async with asyncio.timeout(5):
            while app._home_rebuilding:
                await pilot.pause(0.02)
        assert app.screen is mounted[0]
        assert not isinstance(app.screen, HomeScreen)


@pytest.mark.asyncio
@pytest.mark.parametrize("queue_workspace_body", [False, True])
async def test_queued_destination_cannot_mount_after_root_severance(*, queue_workspace_body: bool) -> None:
    mounted = Event()

    class MarkerScreen(Screen[None]):
        def on_mount(self) -> None:
            mounted.set()

    def child_factory(_context: object) -> Screen[None]:
        return MarkerScreen()

    root = _root(child_factory=child_factory)
    app = CadrumoTuiApp(
        destination_catalogue=root.destination_catalogue,
        refresh_home=root.refresh_home,
        account_factories=root.account_factories,
    )
    async with app.run_test() as pilot:
        await asyncio.wait_for(app.workers.wait_for_complete(), 5)
        await pilot.pause()
        assert isinstance(app.screen, HomeScreen) and app.screen.is_mounted
        app.navigate_to(_ledger_target())
        if queue_workspace_body:
            app.replace_workspace_body(MarkerScreen())
        app._request_recompose(AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED))
        await pilot.pause()
        assert not mounted.is_set()
        assert app._destination_catalogue is None
