"""Production root recovery after transient reads and delayed navigation."""

from __future__ import annotations

import asyncio
from threading import Event

import pytest
from textual.widgets import Button, Static

from ....application.overview.home import HomeProjectionV1
from ..account import AccountRecomposeReasonV1, AccountRecomposeRequiredV1
from ..app import CadrumoTuiApp, RootBindingV1
from ..home import HomeScreen
from ..navigation import TuiFocusIdentityV1, TuiNavigationTargetV1
from .home_fixtures import HomeFixtureScenario, build_home_projection_fixture
from .test_app import MarkerScreen, _account_factories, _catalogue, _settle

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _target() -> TuiNavigationTargetV1:
    return TuiNavigationTargetV1(
        destination="workbench.ledger",
        focus=TuiFocusIdentityV1(destination="workbench.ledger", semantic_key="ledger.overview"),
    )


@pytest.mark.asyncio
async def test_failed_initial_root_can_be_retried_with_the_mouse() -> None:
    calls = 0

    def load() -> RootBindingV1:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("synthetic transient capture refusal")
        return RootBindingV1(
            destination_catalogue=_catalogue([]),
            refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
            workbench_search_service=None,
            refresh_workbench_search=None,
            refresh_destination_catalogue=None,
            account_factories=_account_factories(),
            read_account_session=None,
        )

    app = CadrumoTuiApp(load_root=load)
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        assert app.query_one("#root-retry", Button).display
        assert await pilot.click("#root-retry")
        await _settle(app, pilot)
        assert isinstance(app.screen, HomeScreen)
        assert calls == 2
        assert not app.query_one("#root-retry", Button).display


@pytest.mark.asyncio
async def test_failed_return_home_offers_keyboard_retry_instead_of_stranding_operator() -> None:
    calls = 0

    def refresh() -> HomeProjectionV1:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic transient capture refusal")
        return build_home_projection_fixture(HomeFixtureScenario.READY)

    app = CadrumoTuiApp(
        destination_catalogue=_catalogue([]), refresh_home=refresh, account_factories=_account_factories()
    )
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        app.navigate_to(_target())
        await pilot.pause()
        assert isinstance(app.screen, MarkerScreen)
        await pilot.press("escape")
        await _settle(app, pilot)
        retry = app.query_one("#root-retry", Button)
        assert retry.display and not retry.disabled
        assert app.focused is retry
        await pilot.press("enter")
        await _settle(app, pilot)
        assert isinstance(app.screen, HomeScreen)
        assert calls == 3
        assert app._home_refresh_refusal_code is None
        assert not app.query_one("#root-updating", Static).display


@pytest.mark.asyncio
@pytest.mark.parametrize("retire", [False, True])
async def test_delayed_catalogue_cannot_replace_newer_navigation_or_retired_profile(*, retire: bool) -> None:
    started, release = Event(), Event()
    original, obsolete = _catalogue([]), _catalogue([])

    def refresh_catalogue():
        started.set()
        assert release.wait(5)
        return obsolete

    app = CadrumoTuiApp(
        destination_catalogue=original,
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        refresh_destination_catalogue=refresh_catalogue,
    )
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        app.navigate_to(_target())
        await pilot.pause()
        await pilot.press("escape")
        try:
            assert await asyncio.to_thread(started.wait, 3)
            if retire:
                app._request_recompose(AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED))
            else:
                app.navigate_to(_target())
                await pilot.pause()
        finally:
            release.set()
        if not retire:
            await _settle(app, pilot)
            assert app.destination_catalogue is original
            assert isinstance(app.screen, MarkerScreen)
            assert not app.query_one("#root-updating", Static).display
    if retire:
        # The context waits for shutdown, including the worker cancellation
        # caused by retirement. Its completed read cannot re-admit the profile.
        assert app._destination_catalogue is None
        assert app._active_destination_catalogue is None
        assert app.return_value == AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED)


@pytest.mark.asyncio
async def test_delayed_failed_home_read_cannot_change_a_newer_destination() -> None:
    started, release = Event(), Event()
    calls = 0

    def refresh() -> HomeProjectionV1:
        nonlocal calls
        calls += 1
        if calls > 1:
            started.set()
            assert release.wait(5)
            raise RuntimeError("synthetic obsolete read failure")
        return build_home_projection_fixture(HomeFixtureScenario.READY)

    app = CadrumoTuiApp(destination_catalogue=_catalogue([]), refresh_home=refresh)
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        app._show_home(None)
        try:
            assert await asyncio.to_thread(started.wait, 3)
            app.navigate_to(_target())
            await pilot.pause()
            assert isinstance(app.screen, MarkerScreen)
        finally:
            release.set()
        await _settle(app, pilot)
        assert isinstance(app.screen, MarkerScreen)
        assert app._active_target == _target()
        assert app._home_refresh_refusal_code is None
