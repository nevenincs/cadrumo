"""The root does not remove a Records page while that page has a write out.

The workspace refuses its own area, tool and Back changes during a write, but
the root has its own ways of removing the page: palette navigation, a page
requested from the desktop, the account keys and quitting. Each of them would
unmount the page, cancel its awaited door after submission and lose the
outcome. These tests hold a real exclusion write mid-flight in the real
``CadrumoTuiApp`` and try each way out by the key or message the operator's
action actually produces. Each is refused on the page; once the write
settles, its outcome is shown and the same action leaves.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

import pytest
from textual.command import CommandPalette
from textual.pilot import Pilot
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Static

from cadrumo_client.contracts.presentation import PresentationDestination

from ....application.ledger.models import ManualLedgerTransactionResult
from ....application.operator_actions.catalogue import lookup_action
from ....application.operator_actions.models import ActionReference
from ....application.overview.home import HomeProjectionV1
from ....application.search.workbench import WorkbenchDestinationAdmissionState
from ....core.config import override_settings
from ....core.i18n.render import tr
from ....domain.transactions.models import BucketTransactionRef
from ..account import (
    AccountDirectSessionActionV1,
    AccountFactoriesV1,
    AccountRecomposeReasonV1,
    AccountRecomposeRequiredV1,
)
from ..app import CadrumoTuiApp, HomeRefreshDoorV1
from ..components.account_chrome import AccountChromeScreen
from ..home import HomeScreen
from ..ledger.actividad_asset import ActivityAssetScreen, ActivityAssetTuiActionsV1
from ..ledger.models import LedgerExclusionSubmissionV1
from ..ledger.models_actividad_asset import ActivityAssetCreationRequestV1, ActivityAssetInspectionV1
from ..ledger.overview import LedgerOverviewScreen
from ..ledger.review import LedgerReviewScreen
from ..ledger.routes import ledger_screen_factory
from ..ledger.tests.actividad_asset_fixtures import ActivityAssetActionStub, activity_asset_revision
from ..ledger.tests.workspace_fixtures import ledger_projection, ledger_review_action, ledger_review_door
from ..navigation import (
    TUI_DESTINATION_CATALOGUE,
    TuiDestinationAdmissionV1,
    TuiDestinationCatalogueV1,
    TuiFocusIdentityV1,
    TuiNavigationTargetV1,
    TuiScreenContextV1,
    TuiScreenFactoryV1,
    build_destination_catalogue,
)
from ..presentation import PagePresentationRequested
from .home_fixtures import HomeFixtureScenario, build_home_projection_fixture
from .settling import SETTLE_TIMEOUT_SECONDS, settle, settle_until

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

type _AppPilot = Pilot[AccountRecomposeRequiredV1 | None]

_LEDGER_TARGET = TuiNavigationTargetV1(
    destination="workbench.ledger",
    focus=TuiFocusIdentityV1(destination="workbench.ledger", semantic_key="ledger.entry"),
)
_HOME_TARGET = TuiNavigationTargetV1(
    destination="workbench.home",
    focus=TuiFocusIdentityV1(destination="workbench.home", semantic_key="navigation.home"),
)


class _HeldExclusionDoor:
    """An exclusion writer that holds each submission until released, then records it as written."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.written: list[LedgerExclusionSubmissionV1] = []

    async def __call__(self, submission: LedgerExclusionSubmissionV1) -> ManualLedgerTransactionResult:
        self.started.set()
        await self.release.wait()
        # Reached only by a door call that was not cancelled while it was held.
        self.written.append(submission)
        return ManualLedgerTransactionResult.model_construct(
            ref=BucketTransactionRef.model_construct(transaction_id=submission.transaction_id),
        )


class _Destination(AccountChromeScreen):
    """Any destination other than Ledger, with the context it was opened for."""

    def __init__(self, context: TuiScreenContextV1) -> None:
        super().__init__()
        self.context = context


class _PasswordForm(Screen[None]):
    """The password form, observable by identity once it opens."""


@dataclass
class _Account:
    """Account doors whose every use is observable."""

    completed: list[AccountRecomposeReasonV1]
    language_screens: list[Screen[None]]
    password_form: _PasswordForm

    def factories(self) -> AccountFactoriesV1:
        def direct(reason: AccountRecomposeReasonV1) -> AccountDirectSessionActionV1:
            async def complete() -> AccountRecomposeRequiredV1:
                self.completed.append(reason)
                return AccountRecomposeRequiredV1(reason=reason)

            return AccountDirectSessionActionV1(complete=complete)

        # Built field by field, as the root's own account tests do, because the
        # production profile factory returns the concrete profile manager.
        factories = object.__new__(AccountFactoriesV1)
        for name, value in {
            "profile": _Destination,
            "change_user": lambda: direct(AccountRecomposeReasonV1.CHANGE_USER),
            "password": lambda: self.password_form,
            "appearance": lambda _app: None,
            "language": self.language_screens.append,
            "sign_out": lambda: direct(AccountRecomposeReasonV1.SIGNED_OUT),
            "access": None,
            "onboarding_pending": False,
            "subscribe_retirement": None,
            "subscribe_notices": None,
            "subscribe_language": None,
            "subscribe_presentation": None,
            "refresh_language": None,
        }.items():
            object.__setattr__(factories, name, value)
        return factories


def _catalogue(
    door: _HeldExclusionDoor, activity_asset_actions: ActivityAssetTuiActionsV1 | None = None
) -> TuiDestinationCatalogueV1:
    """Admit every destination; Ledger is the real production factory with an exclusion writer."""
    projection = ledger_projection()
    admissions: dict[str, TuiDestinationAdmissionV1] = {
        descriptor.destination: TuiDestinationAdmissionV1(
            destination=descriptor.destination, state=WorkbenchDestinationAdmissionState.AVAILABLE
        )
        for descriptor in TUI_DESTINATION_CATALOGUE
    }
    factories: dict[str, TuiScreenFactoryV1] = {
        descriptor.destination: _Destination for descriptor in TUI_DESTINATION_CATALOGUE
    }
    factories["workbench.ledger"] = ledger_screen_factory(
        projection,
        review_action=ledger_review_action(),
        review_door=ledger_review_door(projection),
        classify_action=ActionReference(action_id=lookup_action("operator.ledger.classify").action_id),
        exclusion_submitter=door,
        activity_asset_actions=activity_asset_actions,
    )
    return build_destination_catalogue(admissions=admissions, factories=factories)


def _app(
    door: _HeldExclusionDoor,
    account: _Account,
    refresh_home: HomeRefreshDoorV1 | None = None,
    activity_asset_actions: ActivityAssetTuiActionsV1 | None = None,
) -> CadrumoTuiApp:
    projection = build_home_projection_fixture(HomeFixtureScenario.READY)
    return CadrumoTuiApp(
        destination_catalogue=_catalogue(door, activity_asset_actions),
        refresh_home=(lambda: projection) if refresh_home is None else refresh_home,
        account_factories=account.factories(),
    )


async def _open_review(pilot: _AppPilot, app: CadrumoTuiApp) -> LedgerReviewScreen:
    """Open Records, then its Review area, by the keys the operator presses."""
    app.navigate_to(_LEDGER_TARGET)
    await settle(pilot)
    navigation = app.screen.query_one("#ledger-navigation", DataTable)
    navigation.focus()
    # Overview, Entries, then Review in canonical area order.
    await pilot.press("down", "down", "enter")
    await settle(pilot)
    review = app.screen
    assert isinstance(review, LedgerReviewScreen)
    return review


async def _start_exclusion(pilot: _AppPilot, review: LedgerReviewScreen, door: _HeldExclusionDoor) -> None:
    """Exclude the first queued entry and confirm, leaving the write held at its door.

    A Home read may be held while this runs, so only the messages are waited for.
    """
    rows = review.query_one("#ledger-review", DataTable)
    rows.focus()
    rows.move_cursor(row=0)
    await pilot.press("x")
    await settle(pilot, workers=False)
    review.query_one("#ledger-exclusion-confirm", Button).press()
    await asyncio.wait_for(door.started.wait(), timeout=SETTLE_TIMEOUT_SECONDS)
    await settle(pilot, workers=False)
    assert review.in_flight


def _status(review: LedgerReviewScreen) -> str:
    return str(review.query_one("#ledger-flow-status", Static).render())


async def _choose_in_palette(pilot: _AppPilot, text: str) -> None:
    """Open Ctrl+P, type ``text`` and choose the best match, as the operator does."""
    await pilot.press("ctrl+p")
    await settle(pilot, workers=False)
    palette = pilot.app.screen
    assert isinstance(palette, CommandPalette)
    await pilot.press(*text)
    await settle_until(
        pilot,
        lambda: bool(palette.query("CommandList").first().option_count),
        "the palette to list a match",
        workers=False,
    )
    await pilot.press("enter")
    await settle(pilot, workers=False)


async def _post_desktop_request(pilot: _AppPilot, destination: PresentationDestination) -> None:
    """Deliver a page request from the desktop exactly as the presentation subscription posts it."""
    pilot.app.post_message(PagePresentationRequested(destination))
    await settle(pilot, workers=False)


async def _press(pilot: _AppPilot, key: str) -> None:
    """Press a key and wait for the messages it posts; a write the page holds stays out."""
    await pilot.press(key)
    await settle(pilot, workers=False)


async def _ended(pilot: _AppPilot) -> None:
    await settle_until(pilot, lambda: not pilot.app.is_running, "the app to end", workers=False)


def _opened(destination: str) -> Callable[[CadrumoTuiApp, _Account], None]:
    def check(app: CadrumoTuiApp, _account: _Account) -> None:
        screen = app.screen
        assert isinstance(screen, _Destination)
        assert screen.context.destination == destination

    return check


def _ended_with(reason: AccountRecomposeReasonV1) -> Callable[[CadrumoTuiApp, _Account], None]:
    def check(app: CadrumoTuiApp, account: _Account) -> None:
        assert account.completed == [reason]
        assert app.return_value == AccountRecomposeRequiredV1(reason=reason)

    return check


def _language_opened(app: CadrumoTuiApp, account: _Account) -> None:
    _opened("workbench.profile")(app, account)
    assert account.language_screens == [app.screen]


def _password_opened(app: CadrumoTuiApp, account: _Account) -> None:
    assert app.screen is account.password_form


def _quit(app: CadrumoTuiApp, _account: _Account) -> None:
    assert not app.is_running
    assert app.return_value is None


@dataclass(frozen=True)
class _Way:
    """One way the operator can ask the root to take them off the page."""

    attempt: Callable[[_AppPilot], Awaitable[None]]
    left: Callable[[CadrumoTuiApp, _Account], None]
    ends_session: bool = False


_WAYS: dict[str, _Way] = {
    "palette-destination": _Way(
        lambda pilot: _choose_in_palette(pilot, "Declarations"), _opened("workbench.declarations")
    ),
    "desktop-page-request": _Way(
        lambda pilot: _post_desktop_request(pilot, "declarations"), _opened("workbench.declarations")
    ),
    "f4-profile": _Way(lambda pilot: _press(pilot, "f4"), _opened("workbench.profile")),
    "f2-language": _Way(lambda pilot: _press(pilot, "f2"), _language_opened),
    "f6-password": _Way(lambda pilot: _press(pilot, "f6"), _password_opened),
    "f5-change-user": _Way(lambda pilot: _press(pilot, "f5"), _ended_with(AccountRecomposeReasonV1.CHANGE_USER), True),
    "f10-sign-out": _Way(lambda pilot: _press(pilot, "f10"), _ended_with(AccountRecomposeReasonV1.SIGNED_OUT), True),
    "ctrl-q-quit": _Way(lambda pilot: _press(pilot, "ctrl+q"), _quit, True),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("way", sorted(_WAYS))
async def test_the_root_keeps_a_page_with_a_write_out_until_the_write_settles(way: str) -> None:
    door = _HeldExclusionDoor()
    account = _Account(completed=[], language_screens=[], password_form=_PasswordForm())
    leave = _WAYS[way]
    with override_settings(cadrumo_output_language="en"):
        app = _app(door, account)
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            review = await _open_review(pilot, app)
            await _start_exclusion(pilot, review, door)

            await leave.attempt(pilot)

            assert app.is_running
            assert app.screen is review, f"{way} replaced the page while its write was out"
            assert review.is_attached
            assert _status(review) == tr("tui.ledger.flow.in_flight_refusal")
            assert account.completed == []
            assert account.language_screens == []
            assert not app._recomposition_pending

            # Kept by reference: the page re-reads its queue into a new body once the write is saved.
            status_line = review.query_one("#ledger-flow-status", Static)
            door.release.set()
            await settle(pilot)
            # The held door call was not cancelled: the write went through, its
            # outcome was said on the page, and the page re-read its queue.
            assert len(door.written) == 1
            assert not review.in_flight
            assert str(status_line.render()) == tr(
                "tui.ledger.review.excluded", entry=review._label(door.written[0].transaction_id)
            )
            reopened = app.screen
            assert isinstance(reopened, LedgerReviewScreen)
            assert reopened is not review

            await leave.attempt(pilot)
            if leave.ends_session:
                await _ended(pilot)
            else:
                await settle(pilot)
            leave.left(app, account)


@pytest.mark.asyncio
async def test_a_home_read_that_lands_while_a_write_is_out_does_not_remove_the_page() -> None:
    """A replacement asked for before the write began is refused when it arrives during it.

    Home reads a whole generation off the event loop, and the page stays
    usable meanwhile, so the operator can start a write after asking for Home.
    The root asks the page again at the moment it would remove it.
    """
    door = _HeldExclusionDoor()
    account = _Account(completed=[], language_screens=[], password_form=_PasswordForm())
    projection = build_home_projection_fixture(HomeFixtureScenario.READY)
    reads = 0
    hold = threading.Event()
    held = threading.Event()

    def refresh_home() -> HomeProjectionV1:
        nonlocal reads
        reads += 1
        if reads == 2:
            held.set()
            assert hold.wait(10)
        return projection

    with override_settings(cadrumo_output_language="en"):
        app = _app(door, account, refresh_home)
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            review = await _open_review(pilot, app)

            app.navigate_to(_HOME_TARGET)
            assert await asyncio.to_thread(held.wait, SETTLE_TIMEOUT_SECONDS)
            await _start_exclusion(pilot, review, door)
            hold.set()
            await settle_until(pilot, lambda: not app._home_rebuilding, "the Home rebuild to finish", workers=False)
            await settle(pilot, workers=False)

            assert app.screen is review, "Home replaced the page while its write was out"
            assert _status(review) == tr("tui.ledger.flow.in_flight_refusal")

            door.release.set()
            await settle(pilot)
            assert len(door.written) == 1
            assert isinstance(app.screen, LedgerReviewScreen)

            app.navigate_to(_HOME_TARGET)
            await settle(pilot)
            assert isinstance(app.screen, HomeScreen)


class _HeldAssetActions(ActivityAssetActionStub):
    """Activity-asset actions whose creation is held on its worker thread until released."""

    def __init__(self) -> None:
        super().__init__(activity_asset_revision("held-asset"))
        self.started = threading.Event()
        self.release = threading.Event()

    @override
    def create(self, request: ActivityAssetCreationRequestV1) -> ActivityAssetInspectionV1:
        self.started.set()
        if not self.release.wait(10):
            raise RuntimeError("the held creation was never released")
        return super().create(request)


@pytest.mark.asyncio
async def test_the_root_keeps_an_activity_asset_action_until_it_settles() -> None:
    """The asset screen sits over the Records overview; neither Back nor the root takes it away mid-action."""
    door = _HeldExclusionDoor()
    account = _Account(completed=[], language_screens=[], password_form=_PasswordForm())
    actions = _HeldAssetActions()
    with override_settings(cadrumo_output_language="en"):
        app = _app(door, account, activity_asset_actions=actions)
        async with app.run_test(size=(120, 40)) as pilot:
            await settle(pilot)
            app.navigate_to(_LEDGER_TARGET)
            await settle(pilot)
            overview = app.screen
            assert isinstance(overview, LedgerOverviewScreen)
            overview.query_one("#ledger-activity-assets", Button).press()
            await settle(pilot)
            assets = app.screen
            assert isinstance(assets, ActivityAssetScreen)
            assets.query_one("#asset-revision-json", Input).value = actions.revision.model_dump_json()
            assets.query_one("#asset-create", Button).press()
            assert await asyncio.to_thread(actions.started.wait, 10)
            assert assets.in_flight

            refusal = tr("tui.ledger.flow.in_flight_refusal")
            status_line = assets.query_one("#ledger-flow-status", Static)
            for attempt in (
                lambda: _press(pilot, "f4"),
                lambda: _press(pilot, "escape"),
                lambda: _post_desktop_request(pilot, "declarations"),
            ):
                await attempt()
                assert app.screen is assets, "the asset screen was removed while its action was out"
                assert str(status_line.render()) == refusal
                status_line.update("")

            actions.release.set()
            await settle_until(pilot, lambda: not assets.in_flight, "the asset action to finish", workers=False)
            assert str(assets.query_one("#asset-result", Static).render()).startswith("created\theld-asset")

            await _press(pilot, "f4")
            await settle(pilot)
            _opened("workbench.profile")(app, account)
