"""Focused contracts for the TUI workbench root."""

from __future__ import annotations

import asyncio
from typing import ClassVar

import pytest
from textual.binding import Binding
from textual.pilot import Pilot
from textual.screen import Screen
from textual.widgets import Static

from ....application.overview.home import HomeProjectionV1, HomeSessionPosture
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.search.workbench import WorkbenchDestinationAdmissionState, WorkbenchSearchService
from ....application.user_profile.passphrase_rotation import ProfilePassphraseRotationOutcome
from ....core.errors.hierarchy import InternalInvariantError
from ....core.i18n.render import tr
from ..account import (
    AccountDirectSessionActionV1,
    AccountFactoriesV1,
    AccountRecomposeReasonV1,
    AccountRecomposeRequiredV1,
    AccountSessionExpiredError,
)
from ..app import CadrumoTuiApp, RootPresentationV1
from ..components.account_chrome import AccountActionV1, AccountChromeScreen
from ..home import HomeScreen
from ..navigation import (
    TUI_DESTINATION_CATALOGUE,
    TuiDestinationAdmissionV1,
    TuiDestinationCatalogueV1,
    TuiDestinationIdV1,
    TuiFocusIdentityV1,
    TuiNavigationTargetV1,
    TuiScreenContextV1,
    TuiScreenFactoryV1,
    build_destination_catalogue,
)
from ..runtime_access_management import RuntimeAccessManagementScreen
from .home_fixtures import HomeFixtureScenario, build_home_projection_fixture

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class MarkerScreen(Screen[None]):
    """A destination body whose injected semantic context is observable."""

    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False)]

    def __init__(self, context: TuiScreenContextV1) -> None:
        super().__init__()
        self.context = context

    def action_close(self) -> None:
        """Dismiss through Textual's real child-screen return protocol."""
        self.dismiss(None)


async def _settle(app: CadrumoTuiApp, pilot: Pilot[AccountRecomposeRequiredV1 | None]) -> None:
    """Let Home's off-loop rebuild land and the screen it pushes lay out."""
    await app.workers.wait_for_complete()
    await pilot.pause()
    await pilot.pause()


def _catalogue(
    contexts: list[TuiScreenContextV1],
    *,
    destination: TuiDestinationIdV1 = "workbench.ledger",
    destination_state: WorkbenchDestinationAdmissionState = WorkbenchDestinationAdmissionState.AVAILABLE,
    destination_factory: TuiScreenFactoryV1 | None = None,
) -> TuiDestinationCatalogueV1:
    """Build the complete admitted catalogue around one observable factory seam."""

    def factory(context: TuiScreenContextV1) -> Screen[None]:
        contexts.append(context)
        return MarkerScreen(context)

    admissions: dict[str, TuiDestinationAdmissionV1] = {
        descriptor.destination: TuiDestinationAdmissionV1(
            destination=descriptor.destination,
            state=WorkbenchDestinationAdmissionState.AVAILABLE,
        )
        for descriptor in TUI_DESTINATION_CATALOGUE
    }
    if destination_state is not WorkbenchDestinationAdmissionState.AVAILABLE:
        admissions[destination] = TuiDestinationAdmissionV1(
            destination=destination,
            state=destination_state,
            reason_code="workbench.destination.unavailable",
        )
    factories: dict[str, TuiScreenFactoryV1] = {
        descriptor.destination: factory for descriptor in TUI_DESTINATION_CATALOGUE
    }
    if destination_state is WorkbenchDestinationAdmissionState.AVAILABLE and destination_factory is not None:
        factories[destination] = destination_factory
    elif destination_state is not WorkbenchDestinationAdmissionState.AVAILABLE:
        del factories[destination]
    return build_destination_catalogue(admissions=admissions, factories=factories)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "destination_state",
    [WorkbenchDestinationAdmissionState.LOCKED, WorkbenchDestinationAdmissionState.STALE],
)
async def test_navigate_to_refuses_unavailable_destination_without_replacing_home(
    destination_state: WorkbenchDestinationAdmissionState,
) -> None:
    """A route revoked after composition leaves Home mounted and reports the shared refusal."""
    target = TuiNavigationTargetV1(
        destination="workbench.ledger",
        focus=TuiFocusIdentityV1(destination="workbench.ledger", semantic_key="ledger.entry"),
    )
    app = CadrumoTuiApp(
        destination_catalogue=_catalogue([], destination_state=destination_state),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        account_factories=_account_factories(),
    )

    async with app.run_test() as pilot:
        # Home is pushed after startup; capture it only once it is mounted.
        await pilot.pause()
        home = app.screen
        assert home.id == "home-screen"

        app.navigate_to(target)
        await pilot.pause()

        assert app.screen is home
        assert len(app.screen_stack) == 2
        assert app._active_target is None
        assert app.is_running
        assert str(app.query_one("#root-navigation-refusal", Static).render()) == tr("tui.root.navigation.unavailable")
        assert str(app.query_one("#root-account-refusal", Static).render()) == ""


@pytest.mark.asyncio
async def test_navigate_to_refuses_a_factory_invocation_failure_without_replacing_home() -> None:
    """A broken injected factory is contained at the root boundary, after real invocation."""
    seen: list[TuiScreenContextV1] = []

    def broken_factory(context: TuiScreenContextV1) -> Screen[None]:
        seen.append(context)
        raise TypeError("factory implementation failure")

    target = TuiNavigationTargetV1(
        destination="workbench.ledger",
        focus=TuiFocusIdentityV1(destination="workbench.ledger", semantic_key="ledger.entry"),
    )
    app = CadrumoTuiApp(
        destination_catalogue=_catalogue(
            [],
            destination_factory=broken_factory,
        ),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        account_factories=_account_factories(),
    )

    async with app.run_test() as pilot:
        # Home is pushed after startup; capture it only once it is mounted.
        await pilot.pause()
        home = app.screen
        assert home.id == "home-screen"

        app.navigate_to(target)
        await pilot.pause()

        assert seen == [TuiScreenContextV1(destination="workbench.ledger", focus=target.focus)]
        assert app.screen is home
        assert len(app.screen_stack) == 2
        assert app._active_target is None
        assert app.is_running
        assert str(app.query_one("#root-navigation-refusal", Static).render()) == tr("tui.root.navigation.unavailable")
        assert str(app.query_one("#root-account-refusal", Static).render()) == ""


@pytest.mark.asyncio
async def test_child_dismissal_refreshes_home_and_restores_its_semantic_focus() -> None:
    """A real child return restores the selected Home identity rather than a row index."""
    contexts: list[TuiScreenContextV1] = []
    projection = build_home_projection_fixture(HomeFixtureScenario.READY)
    app = CadrumoTuiApp(
        destination_catalogue=_catalogue(contexts),
        refresh_home=lambda: projection,
    )
    target = TuiNavigationTargetV1(
        destination="workbench.ledger",
        focus=TuiFocusIdentityV1(
            destination="workbench.ledger",
            semantic_key="ledger.entry",
            restore_token="a" * 64,
        ),
    )

    async with app.run_test() as pilot:
        await _settle(app, pilot)
        initial_home = app.screen
        assert isinstance(initial_home, HomeScreen)
        assert len(app.screen_stack) == 2
        selected = initial_home.highlighted_target
        assert selected is not None

        await pilot.press("enter")
        await pilot.pause()
        assert initial_home.selected_target == selected

        app.navigate_to(target)
        await pilot.pause()

        assert isinstance(app.screen, MarkerScreen)
        assert app.screen.context == TuiScreenContextV1(destination="workbench.ledger", focus=target.focus)
        assert contexts == [app.screen.context]
        assert len(app.screen_stack) == 2

        await pilot.press("escape")
        await _settle(app, pilot)

        returned_home = app.screen
        assert isinstance(returned_home, HomeScreen)
        assert returned_home.highlighted_target == selected
        assert len(app.screen_stack) == 2


@pytest.mark.asyncio
async def test_expired_child_return_tears_down_profile_bound_doors_and_recomposes() -> None:
    """Expiry discards the complete old root before asking bootstrap to resume."""
    contexts: list[TuiScreenContextV1] = []
    ready = build_home_projection_fixture(HomeFixtureScenario.READY)
    expired = ready.model_copy(
        update={
            "account": ready.account.model_copy(
                update={"posture": HomeSessionPosture.EXPIRED, "profile_label": "Expired profile"}
            )
        }
    )
    projections = [ready, expired]
    app = CadrumoTuiApp(
        destination_catalogue=_catalogue(contexts),
        refresh_home=lambda: projections.pop(0),
    )

    async with app.run_test() as pilot:
        app.navigate_to(
            TuiNavigationTargetV1(
                destination="workbench.declarations",
                focus=TuiFocusIdentityV1(destination="workbench.declarations", semantic_key="declaration.case"),
            )
        )
        await pilot.pause()
        assert isinstance(app.screen, MarkerScreen)

        await pilot.press("escape")
        await pilot.pause()

        # Expiry severs private presentation together with its read doors.
        assert app.account_session is None
        assert app._active_target is None
        assert app.return_value == AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED)
        with pytest.raises(InternalInvariantError, match="no composed destination"):
            _ = app.destination_catalogue
        with pytest.raises(InternalInvariantError, match="no composed workbench search"):
            _ = app.workbench_search_service


@pytest.mark.asyncio
async def test_expired_custody_refresh_recomposes_without_rendering_a_stale_root() -> None:
    """A precise custody expiry becomes the same non-secret expiry handoff."""
    app = CadrumoTuiApp(
        destination_catalogue=_catalogue([]),
        refresh_home=lambda: (_ for _ in ()).throw(AccountSessionExpiredError()),
        workbench_search_service=WorkbenchSearchService(()),
        account_factories=_account_factories(),
    )

    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.return_value == AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED)
        assert app._account_factories is None
        with pytest.raises(InternalInvariantError, match="no composed destination"):
            _ = app.destination_catalogue
        with pytest.raises(InternalInvariantError, match="no composed workbench search"):
            _ = app.workbench_search_service


@pytest.mark.asyncio
async def test_a_refused_home_refresh_keeps_the_session_and_reports_a_code() -> None:
    """A concurrent write must not end the session with a traceback.

    The read door refuses when a sibling process writes the profile between its
    two reads. That refusal is correct and says nothing about this session's
    validity, so the operator keeps the Home they are looking at and is told the
    refresh did not happen. Before this, the RuntimeError escaped into a Textual
    message handler and terminated the run -- while the sibling search path one
    method away already handled its own refusal exactly this way.
    """
    projections = [build_home_projection_fixture(HomeFixtureScenario.READY)]

    def refresh() -> HomeProjectionV1:
        if projections:
            return projections.pop(0)
        raise RuntimeError("secure workbench generation changed during capture")

    app = CadrumoTuiApp(
        destination_catalogue=_catalogue([]),
        refresh_home=refresh,
        workbench_search_service=WorkbenchSearchService(()),
        account_factories=_account_factories(),
    )

    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.home_refresh_refusal_code is None

        app._show_home(None)
        await pilot.pause()

        assert app.home_refresh_refusal_code == "workbench.home.refresh_unavailable"
        assert app.return_value is None
        assert app.is_running
        app.exit(None)


@pytest.mark.asyncio
async def test_a_refused_refresh_never_reports_an_expiry_it_did_not_observe() -> None:
    """A refusal and an expiry are different outcomes and stay so.

    Widening the expiry branch to catch everything would end the session in the
    other direction -- discarding a live profile-bound root over a concurrent
    write -- so the refusal must not be reported as a recomposition.
    """
    app = CadrumoTuiApp(
        destination_catalogue=_catalogue([]),
        refresh_home=lambda: (_ for _ in ()).throw(RuntimeError("secure workbench generation changed during capture")),
        workbench_search_service=WorkbenchSearchService(()),
        account_factories=_account_factories(),
    )

    async with app.run_test() as pilot:
        await pilot.pause()

        assert app.return_value is None
        assert app.home_refresh_refusal_code == "workbench.home.refresh_unavailable"
        assert app._account_factories is not None
        app.exit(None)


def _direct_session_action(reason: AccountRecomposeReasonV1) -> AccountDirectSessionActionV1:
    """Supply the canonical non-secret account completion for unrelated tests."""

    async def complete() -> AccountRecomposeRequiredV1:
        return AccountRecomposeRequiredV1(reason=reason)

    return AccountDirectSessionActionV1(complete=complete)


def _account_factories(
    change_user: AccountDirectSessionActionV1 | None = None,
    *,
    password: Screen[ProfilePassphraseRotationOutcome | None] | None = None,
    password_available: bool = True,
    sign_out: AccountDirectSessionActionV1 | None = None,
    access: Screen[None] | None = None,
    onboarding_pending: bool = False,
) -> AccountFactoriesV1:
    """Supply observable account doors without reproducing an account surface."""
    factories = object.__new__(AccountFactoriesV1)
    object.__setattr__(factories, "profile", lambda context: MarkerScreen(context))
    object.__setattr__(
        factories, "change_user", lambda: change_user or _direct_session_action(AccountRecomposeReasonV1.CHANGE_USER)
    )
    object.__setattr__(factories, "password", (lambda: password or Screen()) if password_available else None)
    object.__setattr__(factories, "access", (lambda: access) if access is not None else None)
    object.__setattr__(factories, "appearance", lambda _app: "appearance.changed")
    object.__setattr__(factories, "language", lambda _screen: None)
    object.__setattr__(
        factories, "sign_out", lambda: sign_out or _direct_session_action(AccountRecomposeReasonV1.SIGNED_OUT)
    )
    object.__setattr__(factories, "onboarding_pending", onboarding_pending)
    return factories


@pytest.mark.asyncio
async def test_an_unfinished_profile_opens_on_setup_once_then_returns_home() -> None:
    """The first Home of a session hands on to the Profile setup walk, and only once."""
    contexts: list[TuiScreenContextV1] = []
    app = CadrumoTuiApp(
        destination_catalogue=_catalogue(contexts),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        account_factories=_account_factories(onboarding_pending=True),
    )
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        await _settle(app, pilot)
        assert isinstance(app.screen, MarkerScreen)
        assert [context.destination for context in contexts] == ["workbench.profile"]

        await pilot.press("escape")
        await _settle(app, pilot)
        await _settle(app, pilot)
        assert isinstance(app.screen, HomeScreen)
        assert [context.destination for context in contexts] == ["workbench.profile"]
        app.exit(None)


@pytest.mark.asyncio
async def test_change_user_requests_fresh_selection_and_revokes_old_profile_root() -> None:
    """The account key retires the old root before requesting a fresh selection."""
    contexts: list[TuiScreenContextV1] = []

    async def complete() -> AccountRecomposeRequiredV1:
        assert app._account_factories is None
        assert app._destination_catalogue is None
        assert app._workbench_search_service is None
        assert len(app.screen_stack) == 1
        return AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.CHANGE_USER)

    app = CadrumoTuiApp(
        destination_catalogue=_catalogue(contexts),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        workbench_search_service=WorkbenchSearchService(()),
        account_factories=_account_factories(AccountDirectSessionActionV1(complete=complete)),
    )

    async with app.run_test(size=(80, 24)) as pilot:
        await _settle(app, pilot)
        await pilot.press("f5")
        async with asyncio.timeout(5):
            while app.return_value is None:
                await pilot.pause(0.02)

        assert app.return_value == AccountRecomposeRequiredV1(
            reason=AccountRecomposeReasonV1.CHANGE_USER,
        )
        assert app._account_factories is None
        with pytest.raises(InternalInvariantError, match="no composed destination"):
            _ = app.destination_catalogue
        with pytest.raises(InternalInvariantError, match="no composed workbench search"):
            _ = app.workbench_search_service


@pytest.mark.asyncio
async def test_password_rotation_recomposes_before_the_old_session_root_can_be_reused() -> None:
    """A new custody generation cannot leave prior profile-bound doors live."""
    password = Screen[ProfilePassphraseRotationOutcome | None]()
    app = CadrumoTuiApp(
        destination_catalogue=_catalogue([]),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        workbench_search_service=WorkbenchSearchService(()),
        account_factories=_account_factories(password=password),
    )
    outcome = ProfilePassphraseRotationOutcome(
        profile_id="11111111-1111-4111-8111-111111111111",
        password_generation=2,
        dek_epoch_preserved=True,
        recovery_enrollment_retained=True,
    )

    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f6")
        await pilot.pause()
        assert app.screen is password
        password.dismiss(outcome)
        await pilot.pause()

        assert app.return_value == AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.PASSWORD_CHANGED)
        assert app._account_factories is None
        with pytest.raises(InternalInvariantError, match="no composed destination"):
            _ = app.destination_catalogue
        with pytest.raises(InternalInvariantError, match="no composed workbench search"):
            _ = app.workbench_search_service


@pytest.mark.asyncio
@pytest.mark.parametrize("completion", ["success", "refusal", "wrong_reason"])
async def test_sign_out_direct_action_recomposes_success_or_requires_fresh_admission(completion: str) -> None:
    """A dispatched action retires the root; only its matching receipt claims logout."""

    async def complete() -> AccountRecomposeRequiredV1:
        if completion == "refusal":
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        return AccountRecomposeRequiredV1(
            reason=(
                AccountRecomposeReasonV1.SIGNED_OUT if completion == "success" else AccountRecomposeReasonV1.CHANGE_USER
            )
        )

    app = CadrumoTuiApp(
        destination_catalogue=_catalogue([]),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        workbench_search_service=WorkbenchSearchService(()),
        account_factories=_account_factories(sign_out=AccountDirectSessionActionV1(complete=complete)),
    )

    async with app.run_test() as pilot:
        await _settle(app, pilot)
        await pilot.press("f10")
        async with asyncio.timeout(5):
            while app.return_value is None:
                await pilot.pause(0.02)
        assert app.return_value == AccountRecomposeRequiredV1(
            reason=(
                AccountRecomposeReasonV1.SIGNED_OUT if completion == "success" else AccountRecomposeReasonV1.EXPIRED
            )
        )
        assert app._account_factories is None
        with pytest.raises(InternalInvariantError, match="no composed destination"):
            _ = app.destination_catalogue
        with pytest.raises(InternalInvariantError, match="no composed workbench search"):
            _ = app.workbench_search_service


@pytest.mark.asyncio
@pytest.mark.parametrize("width", [80, 100, 120])
async def test_account_header_is_keyboard_reachable_without_horizontal_overflow(width: int) -> None:
    """Every account control has a key named in the footer, and the bar fits the width."""
    app = CadrumoTuiApp(
        destination_catalogue=_catalogue([]),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        account_factories=_account_factories(),
    )

    async with app.run_test(size=(width, 24)) as pilot:
        await pilot.pause()
        actions = {active.binding.action for active in app.active_bindings.values()}
        bound = {action for action in actions if action.startswith("account(") or action == "toggle_appearance"}
        assert bound == {
            "toggle_appearance",
            *(
                f"account('{action.value}')"
                for action in AccountActionV1
                if action not in {AccountActionV1.APPEARANCE, AccountActionV1.ACCESS}
            ),
        }
        bar = app.query_one("#root-account-bar")
        assert bar.region.x >= 0
        assert bar.region.right <= width
        assert bar.scrollable_content_region.width <= width


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "expected"),
    [
        (AccountActionV1.SIGN_OUT, AccountRecomposeReasonV1.SIGNED_OUT),
        (AccountActionV1.CHANGE_USER, AccountRecomposeReasonV1.CHANGE_USER),
    ],
)
async def test_direct_account_action_severs_private_root_before_completion(
    action: AccountActionV1, expected: AccountRecomposeReasonV1
) -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    desired = AccountRecomposeRequiredV1(reason=expected)

    async def complete() -> AccountRecomposeRequiredV1:
        assert app._account_factories is None
        assert app._destination_catalogue is None
        assert app._workbench_search_service is None
        assert len(app.screen_stack) == 1
        started.set()
        await asyncio.wait_for(release.wait(), 5)
        return desired

    direct = AccountDirectSessionActionV1(complete=complete)
    factories = _account_factories(
        direct if action is AccountActionV1.CHANGE_USER else None,
        sign_out=direct if action is AccountActionV1.SIGN_OUT else None,
    )
    app = CadrumoTuiApp(
        destination_catalogue=_catalogue([]),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        workbench_search_service=WorkbenchSearchService(()),
        account_factories=factories,
    )
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        child = AccountChromeScreen()
        app._replace_destination(child, return_to_home=True)
        await pilot.pause()
        assert app.screen is child
        app.run_account_action(action)
        assert app._account_factories is None
        assert app._destination_catalogue is None
        assert not child.display
        await asyncio.wait_for(started.wait(), 5)
        assert app.return_value is None
        release.set()
        async with asyncio.timeout(5):
            while app.return_value is None:
                await pilot.pause(0.02)
        assert app.return_value == desired


@pytest.mark.asyncio
async def test_failed_direct_action_exits_to_fresh_admission_and_hides_unavailable_password() -> None:
    async def complete() -> AccountRecomposeRequiredV1:
        raise ValueError("synthetic-private-failure")

    factories = _account_factories(AccountDirectSessionActionV1(complete=complete), password_available=False)
    app = CadrumoTuiApp(
        destination_catalogue=_catalogue([]),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        account_factories=factories,
    )
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        assert not app.account_action_available(AccountActionV1.PASSWORD)
        assert not app.check_action("account", ("password",))
        assert "account('password')" not in {active.binding.action for active in app.active_bindings.values()}
        app.run_account_action(AccountActionV1.CHANGE_USER)
        async with asyncio.timeout(5):
            while app.return_value is None:
                await pilot.pause(0.02)
        assert app.return_value == AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED)


@pytest.mark.asyncio
async def test_cancelled_direct_action_retains_completion_until_runtime_effect_settles() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    completed = asyncio.Event()

    async def complete() -> AccountRecomposeRequiredV1:
        started.set()
        await release.wait()
        completed.set()
        return AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.SIGNED_OUT)

    app = CadrumoTuiApp(
        destination_catalogue=_catalogue([]),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        account_factories=_account_factories(sign_out=AccountDirectSessionActionV1(complete=complete)),
    )
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        app.run_account_action(AccountActionV1.SIGN_OUT)
        try:
            await asyncio.wait_for(started.wait(), 5)
            worker = next(worker for worker in app.workers if worker.name == "account-direct-action")
            worker.cancel()
            worker.cancel()
            await pilot.pause()
            assert not completed.is_set()
            assert app.return_value is None
        finally:
            release.set()
        await asyncio.wait_for(completed.wait(), 5)
        await pilot.pause()
        assert app.return_value == AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED)


@pytest.mark.asyncio
async def test_access_dismissal_with_lost_admission_exits_before_old_root_can_return() -> None:
    app = CadrumoTuiApp(
        destination_catalogue=_catalogue([]),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        account_factories=_account_factories(access=Screen()),
    )
    lost_screen = object.__new__(RuntimeAccessManagementScreen)
    object.__setattr__(lost_screen, "_access_lost", True)
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        assert app.account_action_available(AccountActionV1.ACCESS)
        private_screen = app.screen
        app._on_access_dismissed(lost_screen)
        assert not private_screen.display
        assert app._account_factories is None
        assert app.return_value == AccountRecomposeRequiredV1(reason=AccountRecomposeReasonV1.EXPIRED)


@pytest.mark.asyncio
async def test_captured_home_bundle_replaces_matching_catalogue_account_and_clears_search() -> None:
    old_catalogue = _catalogue([])
    new_catalogue = _catalogue([])
    old_factories = _account_factories()
    new_factories = _account_factories(password_available=False)
    bundle = RootPresentationV1(
        home=build_home_projection_fixture(HomeFixtureScenario.READY),
        destination_catalogue=new_catalogue,
        workbench_search_service=None,
        account_factories=new_factories,
    )
    app = CadrumoTuiApp(
        destination_catalogue=old_catalogue,
        refresh_home=lambda: bundle,
        workbench_search_service=WorkbenchSearchService(()),
        refresh_workbench_search=None,
        refresh_destination_catalogue=None,
        account_factories=old_factories,
    )
    async with app.run_test() as pilot:
        await _settle(app, pilot)
        assert isinstance(app.screen, HomeScreen)
        assert app.destination_catalogue is new_catalogue
        assert app._account_factories is new_factories
        assert app.workbench_search_refusal_code == "workbench.search.unavailable"
        with pytest.raises(InternalInvariantError, match="no composed workbench search"):
            _ = app.workbench_search_service
        assert not app.account_action_available(AccountActionV1.PASSWORD)
        app.navigate_to(
            TuiNavigationTargetV1(
                destination="workbench.profile",
                focus=TuiFocusIdentityV1(destination="workbench.profile", semantic_key="profile.overview"),
            )
        )
        await pilot.pause()
        child = app.screen
        assert isinstance(child, MarkerScreen)
        child.dismiss(None)
        await _settle(app, pilot)
        assert app.destination_catalogue is new_catalogue
        assert app.workbench_search_refusal_code == "workbench.search.unavailable"
        app.exit(None)


@pytest.mark.asyncio
async def test_authoritative_child_return_rebuilds_the_injected_search_snapshot_once() -> None:
    """Search changes only at the explicit child-return lifecycle boundary."""
    contexts: list[TuiScreenContextV1] = []
    initial_search = WorkbenchSearchService(())
    refreshed_search = WorkbenchSearchService(())
    refreshes: list[WorkbenchSearchService] = []
    app = CadrumoTuiApp(
        destination_catalogue=_catalogue(contexts),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        workbench_search_service=initial_search,
        refresh_workbench_search=lambda: (refreshes.append(refreshed_search), refreshed_search)[1],
    )

    async with app.run_test() as pilot:
        assert app.workbench_search_service is initial_search
        app.navigate_to(
            TuiNavigationTargetV1(
                destination="workbench.ledger",
                focus=TuiFocusIdentityV1(destination="workbench.ledger", semantic_key="ledger.entry"),
            )
        )
        await pilot.pause()
        assert app.workbench_search_service is initial_search

        await pilot.press("escape")
        await pilot.pause()

    assert refreshes == [refreshed_search]
    assert app.workbench_search_service is refreshed_search


@pytest.mark.asyncio
async def test_failed_search_refresh_retains_last_good_and_sanitizes_refusal() -> None:
    """A bad refreshed projection retains the last complete search generation."""
    contexts: list[TuiScreenContextV1] = []
    initial_search = WorkbenchSearchService(())

    def fail_refresh() -> WorkbenchSearchService:
        raise RuntimeError("12345678Z C:\\protected\\search.json")

    app = CadrumoTuiApp(
        destination_catalogue=_catalogue(contexts),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        workbench_search_service=initial_search,
        refresh_workbench_search=fail_refresh,
    )

    async with app.run_test() as pilot:
        app.navigate_to(
            TuiNavigationTargetV1(
                destination="workbench.ledger",
                focus=TuiFocusIdentityV1(destination="workbench.ledger", semantic_key="ledger.entry"),
            )
        )
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

    assert app.workbench_search_refusal_code == "workbench.search.refresh_unavailable"
    assert app.workbench_search_service is initial_search
    assert "12345678Z" not in app.workbench_search_refusal_code
    assert "protected" not in app.workbench_search_refusal_code


@pytest.mark.asyncio
async def test_the_return_to_home_rereads_off_the_event_loop_and_shows_that_it_is_updating() -> None:
    """A slow generation capture must not freeze the root while it runs."""
    import threading

    contexts: list[TuiScreenContextV1] = []
    release = threading.Event()
    refreshed_search = WorkbenchSearchService(())
    refreshes: list[int] = []

    def slow_refresh() -> WorkbenchSearchService:
        refreshes.append(1)
        release.wait(timeout=10)
        return refreshed_search

    app = CadrumoTuiApp(
        destination_catalogue=_catalogue(contexts),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        workbench_search_service=WorkbenchSearchService(()),
        refresh_workbench_search=slow_refresh,
    )

    async with app.run_test() as pilot:
        app.navigate_to(
            TuiNavigationTargetV1(
                destination="workbench.ledger",
                focus=TuiFocusIdentityV1(destination="workbench.ledger", semantic_key="ledger.entry"),
            )
        )
        await pilot.pause()
        await pilot.press("escape")
        for _ in range(5):
            await pilot.pause()
        # The loop keeps turning while the capture is out, and says why the page is empty.
        assert app.query_one("#root-updating", Static).display
        assert app.workbench_search_service is not refreshed_search
        release.set()
        await app.workers.wait_for_complete()
        for _ in range(4):
            await pilot.pause()
        assert not app.query_one("#root-updating", Static).display
        assert isinstance(app.screen, HomeScreen)

    assert refreshes == [1]
    assert app.workbench_search_service is refreshed_search


def test_a_screen_detached_before_its_mount_handler_gets_no_chrome() -> None:
    """Exiting or dismissing mid-transition must not crash on the chrome mount."""
    screen = AccountChromeScreen()

    assert not screen.is_attached
    screen._mount_account_chrome()

    assert not screen.query("#account-bar")
