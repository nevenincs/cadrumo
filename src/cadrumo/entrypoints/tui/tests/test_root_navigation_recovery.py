"""Production root recovery after transient reads and delayed navigation."""

from __future__ import annotations

import asyncio
from threading import Event

import pytest
from textual.screen import Screen
from textual.widgets import Button, Static

from ....application.overview.home import HomeProjectionV1
from ....core.i18n.render import tr
from ..account import AccountRecomposeReasonV1, AccountRecomposeRequiredV1
from ..app import CadrumoTuiApp, RootBindingV1
from ..components.account_chrome import AccountActionV1, AccountChromeScreen
from ..home import HomeScreen
from ..navigation import TuiFocusIdentityV1, TuiNavigationTargetV1, TuiScreenContextV1
from .home_fixtures import HomeFixtureScenario, build_home_projection_fixture
from .settling import SETTLE_TIMEOUT_SECONDS, settle, settle_until
from .test_app import MarkerScreen, _account_factories, _catalogue

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
        await settle(pilot)
        assert app.query_one("#root-retry", Button).display
        assert await pilot.click("#root-retry")
        await settle(pilot)
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
        await settle(pilot)
        app.navigate_to(_target())
        await settle(pilot)
        assert isinstance(app.screen, MarkerScreen)
        await pilot.press("escape")
        await settle(pilot)
        retry = app.query_one("#root-retry", Button)
        assert retry.display and not retry.disabled
        assert app.focused is retry
        await pilot.press("enter")
        await settle(pilot)
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
        assert release.wait(SETTLE_TIMEOUT_SECONDS)
        return obsolete

    app = CadrumoTuiApp(
        destination_catalogue=original,
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        refresh_destination_catalogue=refresh_catalogue,
    )
    async with app.run_test() as pilot:
        await settle(pilot)
        app.navigate_to(_target())
        await settle(pilot, workers=False)
        await pilot.press("escape")
        try:
            assert await asyncio.to_thread(started.wait, SETTLE_TIMEOUT_SECONDS)
            if retire:
                app._request_recompose(AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED))
            else:
                app.navigate_to(_target())
                await settle(pilot, workers=False)
        finally:
            release.set()
        if not retire:
            await settle(pilot)
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
            assert release.wait(SETTLE_TIMEOUT_SECONDS)
            raise RuntimeError("synthetic obsolete read failure")
        return build_home_projection_fixture(HomeFixtureScenario.READY)

    app = CadrumoTuiApp(destination_catalogue=_catalogue([]), refresh_home=refresh)
    async with app.run_test() as pilot:
        await settle(pilot)
        app._show_home(None)
        try:
            assert await asyncio.to_thread(started.wait, SETTLE_TIMEOUT_SECONDS)
            app.navigate_to(_target())
            await settle(pilot, workers=False)
            assert isinstance(app.screen, MarkerScreen)
        finally:
            release.set()
        await settle(pilot)
        assert isinstance(app.screen, MarkerScreen)
        assert app._active_target == _target()
        assert app._home_refresh_refusal_code is None


class _Destination(AccountChromeScreen):
    """A destination the account keys act from."""

    def __init__(self, context: TuiScreenContextV1) -> None:
        super().__init__()
        self.context = context


@pytest.mark.asyncio
async def test_access_requested_while_the_first_destination_opens_is_not_discarded_by_it() -> None:
    """Access opens only once the startup swap has removed the screens it replaces.

    Binding the session publishes it before the startup destination is
    swapped in from the root's pump. Access asked for in that window opened
    over the bare root, and the swap then removed it without a dismissal.
    """
    opened: list[Screen[None]] = []
    app: CadrumoTuiApp | None = None

    def destination(context: TuiScreenContextV1) -> Screen[None]:
        # The request reaches the root's pump after the session is bound and
        # before the swap that shows this page has run, as a palette or Home
        # link request does when it lands while the root is opening.
        assert app is not None
        app.call_next(app.run_account_action, AccountActionV1.ACCESS)
        return _Destination(context)

    def open_access() -> Screen[None]:
        screen: Screen[None] = Screen()
        opened.append(screen)
        return screen

    factories = _account_factories()
    object.__setattr__(factories, "access", open_access)

    def load() -> RootBindingV1:
        return RootBindingV1(
            destination_catalogue=_catalogue([], destination_factory=destination),
            refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
            workbench_search_service=None,
            refresh_workbench_search=None,
            refresh_destination_catalogue=None,
            account_factories=factories,
            read_account_session=None,
            initial_destination=_target(),
        )

    app = CadrumoTuiApp(load_root=load)
    async with app.run_test() as pilot:
        await settle_until(
            pilot,
            lambda: (
                all(worker.is_finished for worker in app.workers)
                and any(isinstance(screen, _Destination) for screen in app.screen_stack)
            ),
            "the startup swap to land on the destination",
        )
        assert any(isinstance(screen, _Destination) for screen in app.screen_stack)
        assert all(screen in app.screen_stack for screen in opened), "the startup swap removed an open Access form"
        # Refused where it can be read, rather than opened and then lost.
        assert not opened
        assert str(app.query_one("#root-account-refusal", Static).content) == tr("tui.root.account.unavailable")
        assert app.account_action_available(AccountActionV1.ACCESS)
        await pilot.press("f7")
        assert opened and app.screen is opened[-1]
        assert isinstance(app.screen_stack[-2], _Destination)
