"""A page the person picks at their desktop opens in the running TUI as a palette choice would."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import get_args

import pytest
from textual.screen import ModalScreen
from textual.widgets import Static

from cadrumo_client.contracts.presentation import PresentationDestination

from ....application.search.workbench import WorkbenchDestinationAdmissionState
from ....core.i18n.render import tr
from ..app import CadrumoTuiApp
from ..components.account_chrome import AccountChromeScreen
from ..home import HomeScreen
from ..navigation import (
    TUI_DESTINATION_CATALOGUE,
    TuiDestinationAdmissionV1,
    TuiDestinationCatalogueV1,
    TuiScreenContextV1,
    TuiScreenFactoryV1,
    build_destination_catalogue,
    declared_destination_ids,
)
from ..presentation import PROFILE_AEAT_AUTH_FOCUS, opens_aeat_auth, presentation_target
from .home_fixtures import HomeFixtureScenario, build_home_projection_fixture
from .settling import settle
from .test_app import _account_factories

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

type _Receiver = Callable[[PresentationDestination], None]


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

    async def deliver(self, destination: PresentationDestination) -> None:
        receiver = self.receiver
        assert receiver is not None
        # The transport delivers on its own thread, never on the UI loop.
        await asyncio.to_thread(receiver, destination)


class _Destination(AccountChromeScreen):
    """A destination as the production ones are: an account-chrome page whose context is observable."""

    def __init__(self, context: TuiScreenContextV1) -> None:
        super().__init__()
        self.context = context


def _catalogue(
    contexts: list[TuiScreenContextV1], ledger_state: WorkbenchDestinationAdmissionState
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
    return build_destination_catalogue(admissions=admissions, factories=factories)


def _app(
    contexts: list[TuiScreenContextV1],
    subscription: _Subscription,
    *,
    ledger_state: WorkbenchDestinationAdmissionState = WorkbenchDestinationAdmissionState.AVAILABLE,
) -> CadrumoTuiApp:
    factories = _account_factories()
    object.__setattr__(factories, "subscribe_presentation", subscription)
    return CadrumoTuiApp(
        destination_catalogue=_catalogue(contexts, ledger_state),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        account_factories=factories,
    )


def test_every_requestable_page_is_a_declared_destination_and_every_destination_is_requestable() -> None:
    targets = {token: presentation_target(token) for token in get_args(PresentationDestination.__value__)}
    assert {target.destination for target in targets.values()} == declared_destination_ids()
    for target in targets.values():
        assert target.focus.destination == target.destination
    assert targets["aeat_auth"].destination == "workbench.profile"
    assert targets["aeat_auth"].focus.semantic_key == PROFILE_AEAT_AUTH_FOCUS


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
        await subscription.deliver("aeat_auth")
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
