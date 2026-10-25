"""A register view the person picks at their desktop opens in the running TUI as a palette choice would."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest
from textual.screen import ModalScreen
from textual.widgets import DataTable, Static

from cadrumo_client.contracts.navigation import NavigationSurface, ViewLink, load_navigation_register

from ....application.search.workbench import WorkbenchDestinationAdmissionState
from ....core.i18n.render import tr
from ..app import CadrumoTuiApp
from ..components.account_chrome import AccountChromeScreen
from ..home import HomeScreen
from ..ledger.controller import LEDGER_TRANSACTION_FOCUS
from ..ledger.entries import LedgerEntriesScreen
from ..ledger.routes import ledger_screen_factory
from ..ledger.tests.workspace_fixtures import LEDGER_TX_B, ledger_projection, ledger_review_action
from ..navigation import (
    TUI_DESTINATION_CATALOGUE,
    TuiDestinationAdmissionV1,
    TuiDestinationCatalogueV1,
    TuiScreenContextV1,
    TuiScreenFactoryV1,
    build_destination_catalogue,
    declared_destination_ids,
)
from ..presentation import (
    PROFILE_AEAT_AUTH_FOCUS,
    TUI_PARAM_FOCUS,
    TUI_ROUTES,
    opens_aeat_auth,
    presentation_target,
)
from .home_fixtures import HomeFixtureScenario, build_home_projection_fixture
from .settling import settle
from .test_app import _account_factories

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

type _Receiver = Callable[[ViewLink], None]


class _Subscription:
    """The transport side of the subscription: it holds the receiver until the root lets go."""

    def __init__(self) -> None:
        self.receiver: _Receiver | None = None
        self.released = False

    def __call__(self, receive: _Receiver) -> Callable[[], None]:
        self.receiver = receive

        def unsubscribe() -> None:
            self.released = True

        return unsubscribe

    async def deliver(self, view_id: str, **params: str) -> None:
        receiver = self.receiver
        assert receiver is not None
        # The transport delivers on its own thread, never on the UI loop.
        await asyncio.to_thread(receiver, ViewLink(view_id=view_id, params=tuple(sorted(params.items()))))


class _Destination(AccountChromeScreen):
    """A destination as the production ones are: an account-chrome page whose context is observable."""

    def __init__(self, context: TuiScreenContextV1) -> None:
        super().__init__()
        self.context = context


def _catalogue(
    contexts: list[TuiScreenContextV1],
    ledger_state: WorkbenchDestinationAdmissionState,
    *,
    real_ledger: bool = False,
) -> TuiDestinationCatalogueV1:
    def factory(context: TuiScreenContextV1) -> _Destination:
        contexts.append(context)
        return _Destination(context)

    admissions: dict[str, TuiDestinationAdmissionV1] = {
        descriptor.destination: TuiDestinationAdmissionV1(
            destination=descriptor.destination, state=WorkbenchDestinationAdmissionState.AVAILABLE
        )
        for descriptor in TUI_DESTINATION_CATALOGUE
    }
    factories: dict[str, TuiScreenFactoryV1] = {
        descriptor.destination: factory for descriptor in TUI_DESTINATION_CATALOGUE
    }
    if ledger_state is not WorkbenchDestinationAdmissionState.AVAILABLE:
        admissions["workbench.ledger"] = TuiDestinationAdmissionV1(
            destination="workbench.ledger", state=ledger_state, reason_code="workbench.destination.unavailable"
        )
        del factories["workbench.ledger"]
    elif real_ledger:
        factories["workbench.ledger"] = ledger_screen_factory(ledger_projection(), review_action=ledger_review_action())
    return build_destination_catalogue(admissions=admissions, factories=factories)


def _app(
    contexts: list[TuiScreenContextV1],
    subscription: _Subscription,
    *,
    ledger_state: WorkbenchDestinationAdmissionState = WorkbenchDestinationAdmissionState.AVAILABLE,
    real_ledger: bool = False,
) -> CadrumoTuiApp:
    factories = _account_factories()
    object.__setattr__(factories, "subscribe_presentation", subscription)
    return CadrumoTuiApp(
        destination_catalogue=_catalogue(contexts, ledger_state, real_ledger=real_ledger),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        account_factories=factories,
    )


def test_the_tui_table_covers_exactly_the_registers_tui_views_and_their_parameters() -> None:
    register = load_navigation_register()
    tui_views = register.ids_for(NavigationSurface.TUI)
    assert frozenset(TUI_ROUTES) == tui_views
    assert set(TUI_PARAM_FOCUS) <= tui_views
    for view_id in tui_views:
        element = register.element(view_id)
        assert element is not None
        assert frozenset(TUI_PARAM_FOCUS.get(view_id, {})) == frozenset(element.params), view_id


def test_every_tui_view_opens_a_declared_destination_and_every_destination_is_requestable() -> None:
    targets = {view_id: presentation_target(ViewLink(view_id=view_id)) for view_id in TUI_ROUTES}
    assert {target.destination for target in targets.values()} == declared_destination_ids()
    for target in targets.values():
        assert target.focus.destination == target.destination
        assert target.focus.restore_token is None
    assert targets["profile/aeat-access"].destination == "workbench.profile"
    assert targets["profile/aeat-access"].focus.semantic_key == PROFILE_AEAT_AUTH_FOCUS


def test_a_selected_transaction_becomes_the_ledger_focus() -> None:
    target = presentation_target(ViewLink(view_id="ledger", params=(("select", LEDGER_TX_B),)))
    assert target.destination == "workbench.ledger"
    assert (target.focus.semantic_key, target.focus.restore_token) == (LEDGER_TRANSACTION_FOCUS, LEDGER_TX_B)


@pytest.mark.asyncio
async def test_a_requested_page_opens_with_its_focus_and_releases_the_subscription() -> None:
    contexts: list[TuiScreenContextV1] = []
    subscription = _Subscription()
    app = _app(contexts, subscription)
    async with app.run_test() as pilot:
        await settle(pilot)
        assert isinstance(app.screen, HomeScreen)

        await subscription.deliver("declarations")
        await settle(pilot)
        assert isinstance(app.screen, _Destination)
        assert app.screen.context.destination == "workbench.declarations"
        assert app.screen.context.focus is not None
        assert app.screen.context.focus.semantic_key == "presentation.declarations"

        # A second request replaces the page the first one opened.
        await subscription.deliver("profile/aeat-access")
        await settle(pilot)
        assert isinstance(app.screen, _Destination)
        assert app.screen.context.destination == "workbench.profile"
        assert opens_aeat_auth(app.screen.context)
        assert len(app.screen_stack) == 2

        await subscription.deliver("home")
        await settle(pilot)
        assert isinstance(app.screen, HomeScreen)
    assert subscription.released


@pytest.mark.asyncio
async def test_a_page_the_session_cannot_open_is_refused_visibly() -> None:
    contexts: list[TuiScreenContextV1] = []
    subscription = _Subscription()
    app = _app(contexts, subscription, ledger_state=WorkbenchDestinationAdmissionState.NEVER_CAPTURED)
    async with app.run_test() as pilot:
        await settle(pilot)
        await subscription.deliver("ledger")
        await settle(pilot)
        assert isinstance(app.screen, HomeScreen)
        assert not any(context.destination == "workbench.ledger" for context in contexts)
        refusal = app.query_one("#root-navigation-refusal", Static)
        assert str(refusal.render()) == tr("tui.root.navigation.unavailable")


@pytest.mark.asyncio
async def test_over_an_open_form_the_request_stands_down_and_keeps_the_form() -> None:
    contexts: list[TuiScreenContextV1] = []
    subscription = _Subscription()
    app = _app(contexts, subscription)
    form: ModalScreen[None] = ModalScreen()
    async with app.run_test() as pilot:
        await settle(pilot)
        await app.push_screen(form)
        await settle(pilot)

        await subscription.deliver("ledger")
        await settle(pilot)
        assert app.screen is form
        assert contexts == []
        refusal = app.query_one("#root-navigation-refusal", Static)
        assert str(refusal.render()) == tr("tui.root.navigation.busy")

        form.dismiss(None)
        await settle(pilot)
        await subscription.deliver("ledger")
        await settle(pilot)
        assert isinstance(app.screen, _Destination)
        assert app.screen.context.destination == "workbench.ledger"
        assert str(app.query_one("#root-navigation-refusal", Static).render()) == ""


@pytest.mark.asyncio
async def test_a_ledger_link_selecting_a_transaction_opens_the_entries_with_it_selected() -> None:
    contexts: list[TuiScreenContextV1] = []
    subscription = _Subscription()
    app = _app(contexts, subscription, real_ledger=True)
    async with app.run_test() as pilot:
        await settle(pilot)

        await subscription.deliver("ledger", select=LEDGER_TX_B)
        await settle(pilot)
        assert isinstance(app.screen, LedgerEntriesScreen)
        table = app.screen.query_one("#ledger-entries", DataTable)
        assert table.ordered_rows[table.cursor_row].key.value == LEDGER_TX_B
        assert app.focused is table
        assert str(app.screen.query_one("#ledger-refusal", Static).render()) == ""


@pytest.mark.asyncio
async def test_a_ledger_link_selecting_a_transaction_not_shown_keeps_the_page_and_says_so() -> None:
    contexts: list[TuiScreenContextV1] = []
    subscription = _Subscription()
    app = _app(contexts, subscription, real_ledger=True)
    async with app.run_test() as pilot:
        await settle(pilot)

        await subscription.deliver("ledger", select="f" * 64)
        await settle(pilot)
        assert isinstance(app.screen, LedgerEntriesScreen)
        notice = str(app.screen.query_one("#ledger-refusal", Static).render())
        assert notice == tr("tui.ledger.entries.selection_absent")
        assert notice != "tui.ledger.entries.selection_absent"
