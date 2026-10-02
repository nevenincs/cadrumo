"""A precomposed TUI root can run without a second local operation graph."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
from threading import Event
from typing import TYPE_CHECKING, Literal, cast

import pytest
from textual.screen import Screen
from textual.widgets import Button, Static

from ....application.runtime.contracts import RuntimeRefusalError
from ....application.runtime.management_status import (
    RuntimeListenerState,
    RuntimeManagementSnapshot,
    RuntimeManagerAvailability,
)
from ....application.search.workbench import WorkbenchDestinationAdmission, WorkbenchDestinationAdmissionState
from ....core.async_cleanup import AsyncResourceCleanupError
from ....core.i18n.render import tr
from ...tests.test_runtime_management import StopFixture
from .. import runtime_management
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
from ..runtime_management import RuntimeManagementScreen, RuntimeStopConfirmationScreen
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


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["accepted", "lost"])
async def test_human_installed_runner_retains_stop_outcome_and_cleanup_after_modal_close(
    outcome: Literal["accepted", "lost"], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture = StopFixture(channel_failures=10, outcome=outcome)
    monkeypatch.setattr(runtime_management, "preview_installed_runtime_stop", fixture.open)

    async def read() -> RuntimeManagementSnapshot:
        return RuntimeManagementSnapshot(
            listener=RuntimeListenerState.READY,
            manager_availability=RuntimeManagerAvailability.UNAVAILABLE,
        )

    driver_failures: list[BaseException] = []

    async def drive_steps(pilot: Pilot[object]) -> None:
        app = pilot.app
        assert isinstance(app, CadrumoTuiApp)
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
        app._runtime_management_reader = read
        async with asyncio.timeout(10):
            app.action_runtime_management()
            while not isinstance(app.screen, RuntimeManagementScreen):
                await pilot.pause(0.02)
            screen = app.screen
            while screen._busy or tr("tui.runtime_management.listener.ready") not in str(
                screen.query_one("#runtime-management-listener", Static).content
            ):
                await pilot.pause(0.02)
            screen.query_one("#runtime-management-stop", Button).press()
            while not isinstance(app.screen, RuntimeStopConfirmationScreen):
                await pilot.pause(0.02)
            app.screen.query_one("#runtime-stop-confirm", Button).press()
            while screen._busy or fixture.channel.close_calls < 1:
                await pilot.pause(0.02)
            assert (fixture.consent.accepted is not None) == (outcome == "accepted")
            assert fixture.consent.uncertain == (outcome == "lost")
            assert screen.query_one("#runtime-management-stop", Button).disabled
            assert "synthetic private" not in str(screen.query_one("#runtime-management-status", Static).content)
            screen.action_close()
            while screen in app.screen_stack:
                await pilot.pause(0.02)
            app.action_runtime_management()
            while not isinstance(app.screen, RuntimeManagementScreen):
                await pilot.pause(0.02)
            reopened = app.screen
            while reopened._busy or tr("tui.runtime_management.listener.ready") not in str(
                reopened.query_one("#runtime-management-listener", Static).content
            ):
                await pilot.pause(0.02)
            assert reopened.query_one("#runtime-management-stop", Button).disabled
            assert fixture.channel.confirmations == 1
            app.exit()

    async def drive(pilot: Pilot[object]) -> None:
        try:
            async with asyncio.timeout(15):
                await drive_steps(pilot)
        except BaseException as error:
            driver_failures.append(error)
        finally:
            pilot.app.exit()

    expected = AsyncResourceCleanupError if outcome == "accepted" else RuntimeRefusalError
    with pytest.raises(expected) as failed:
        await run_precomposed_runtime_root_session(load_root=_root, headless=True, auto_pilot=drive)
    assert not driver_failures, driver_failures
    error = failed.value
    retained = error if isinstance(error, AsyncResourceCleanupError) else error.__dict__.get("async_cleanup_error")
    assert isinstance(retained, AsyncResourceCleanupError)
    attempts = fixture.channel.close_calls
    endpoint_attempts = fixture.endpoint.close_calls
    fixture.channel.failures = 0
    await retained.retry_cleanup()
    assert fixture.channel.close_calls == attempts + 1
    assert fixture.endpoint.close_calls == endpoint_attempts
    assert fixture.consent.released and fixture.channel.confirmations == 1
    captured = capsys.readouterr()
    assert "synthetic private" not in captured.out + captured.err


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
        assert app.home_refresh_refusal_code == "workbench.home.refresh_unavailable"
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
