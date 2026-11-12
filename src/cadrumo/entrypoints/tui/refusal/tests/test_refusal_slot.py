"""A surface shows its refusal through the slot, and a chosen way out opens through the host's admitted routes."""

from __future__ import annotations

from typing import cast, override

import pytest
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Static

from cadrumo_client.transport.frontend_client import FrontendClient

from .....application.operations.error_detail import OperationErrorDetailKind, OperationErrorDetailV1
from .....application.search.workbench import (
    WorkbenchDestinationAdmissionState,
    WorkbenchSearchRequest,
    WorkbenchSearchResponse,
)
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .....core.operator_action_enums import ActionArgumentStatus
from ....tests.production_operation_registry import production_operation_registry
from ...navigation import (
    TUI_DESTINATION_CATALOGUE,
    TuiDestinationAdmissionV1,
    TuiDestinationCatalogueV1,
    TuiFocusIdentityV1,
    TuiNavigationTargetV1,
    TuiScreenContextV1,
    TuiScreenFactoryV1,
    build_destination_catalogue,
)
from ...operations.catalogue import OperationCatalogueSourceV1
from ...operations.destination import OPERATION_FOCUS_KEY, OPERATIONS_DESTINATION, OperationsDestinationV1
from ...tests.settling import settle
from ..intent import RefusalRouterV1
from ..panel import RefusalPanel, RefusalSlot
from ..routing import host_refusal_router
from ..served import ServedRefusalV1, served_refusal
from .refusal_fixtures import CREATE_WORK, MarkerScreen, primary_verdict, words

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_REFUSED = "The declaration does not exist yet."


def _marker(_context: TuiScreenContextV1) -> Screen[None]:
    return MarkerScreen()


def _admitted_with_operations() -> TuiDestinationCatalogueV1:
    """Every destination admitted, the Operations one served by the real catalogue door."""
    factories: dict[str, TuiScreenFactoryV1] = {
        descriptor.destination: _marker for descriptor in TUI_DESTINATION_CATALOGUE
    }
    # The destination is never opened here: the host records where it was asked to go.
    factories[OPERATIONS_DESTINATION] = OperationsDestinationV1(
        cast(FrontendClient, object()), OperationCatalogueSourceV1(production_operation_registry)
    )
    return build_destination_catalogue(
        admissions={
            descriptor.destination: TuiDestinationAdmissionV1(
                destination=descriptor.destination, state=WorkbenchDestinationAdmissionState.AVAILABLE
            )
            for descriptor in TUI_DESTINATION_CATALOGUE
        },
        factories=factories,
    )


class _Plain(App[None]):
    """An app that admits no destination."""

    def __init__(self, refusal: ServedRefusalV1 | None) -> None:
        super().__init__()
        self._refusal = refusal

    @override
    def compose(self) -> ComposeResult:
        yield RefusalSlot(self._refusal, id="slot")


class _Host(_Plain):
    """A workbench root: it admits destinations, routes refusals through them and opens the chosen one."""

    def __init__(self, refusal: ServedRefusalV1 | None) -> None:
        super().__init__(refusal)
        self._destinations = _admitted_with_operations()
        self.opened: list[TuiNavigationTargetV1] = []

    @property
    def workbench_search_service(self) -> _NoSearch:
        return _NoSearch()

    @property
    def workbench_search_refusal_code(self) -> str | None:
        return None

    @property
    def destination_catalogue(self) -> TuiDestinationCatalogueV1:
        return self._destinations

    def navigate_to(self, target: TuiNavigationTargetV1, /) -> None:
        self.opened.append(target)

    async def refusal_router(self, refusal: ServedRefusalV1, /) -> RefusalRouterV1:
        return await host_refusal_router(self, refusal)

    def on_refusal_panel_action_chosen(self, message: RefusalPanel.ActionChosen) -> None:
        message.stop()
        self.navigate_to(message.intent.navigation_target())


class _NoSearch:
    def search(self, request: WorkbenchSearchRequest, /) -> WorkbenchSearchResponse:
        raise AssertionError("the refusal slot never searches")


def _detail_refusal() -> ServedRefusalV1:
    detail = OperationErrorDetailV1(
        kind=OperationErrorDetailKind.REGISTERED_ERROR,
        error_code="REFUSED_FINANCIAL_AGGREGATION_UNSUPPORTED_MODELO",
        message_key=None,
        context=(),
        precondition_verdict_json=primary_verdict(CREATE_WORK, missing_year=True).to_verdict().model_dump_json(),
        refusal_words=_REFUSED,
        refusal_words_language=OutputLanguage.EN,
    )
    refusal = served_refusal(detail)
    assert refusal is not None
    return refusal


def _worded(refusal: ServedRefusalV1) -> ServedRefusalV1:
    """The same refusal once the backend serves words for its primary action."""
    return ServedRefusalV1(
        refusal_words=refusal.refusal_words,
        verdict=refusal.verdict,
        primary_action_words=words("Start the declaration"),
    )


def _text(app: App[None], selector: str) -> str:
    return str(app.query_one(selector, Static).render())


@pytest.mark.asyncio
async def test_a_recorded_refusal_shows_its_served_sentence_and_no_unworded_control() -> None:
    app = _Host(_detail_refusal())
    async with app.run_test() as pilot:
        await settle(pilot)
        assert _text(app, "#slot #refusal-words") == _REFUSED
        assert not app.query(Button)
        assert app.opened == []


@pytest.mark.asyncio
async def test_a_worded_way_out_opens_its_operation_with_the_arguments_it_was_served() -> None:
    app = _Host(_worded(_detail_refusal()))
    async with app.run_test() as pilot:
        await settle(pilot)
        (button,) = app.query(Button)
        assert not button.disabled
        assert str(button.label) == "Start the declaration …"
        await pilot.click("#refusal-action-0")
        await settle(pilot)
        (target,) = app.opened
        assert target.destination == OPERATIONS_DESTINATION
        assert target.focus.semantic_key == OPERATION_FOCUS_KEY
        assert [(binding.argument_name, binding.status, binding.value) for binding in target.request_prefill] == [
            ("modelo", ActionArgumentStatus.RESOLVED, "100"),
            ("year", ActionArgumentStatus.MISSING, None),
        ]


@pytest.mark.asyncio
async def test_a_host_that_admits_no_destination_shows_the_way_out_disabled_with_the_reason() -> None:
    app = _Plain(_worded(_detail_refusal()))
    async with app.run_test() as pilot:
        await settle(pilot)
        (button,) = app.query(Button)
        assert button.disabled
        assert _text(app, "#refusal-unroutable") == tr("tui.refusal.action_unroutable")
        assert "operator." not in str(button.label)


@pytest.mark.asyncio
async def test_showing_the_same_refusal_keeps_the_panel_and_none_clears_it() -> None:
    refusal = _detail_refusal()
    app = _Host(None)
    async with app.run_test() as pilot:
        slot = app.query_one("#slot", RefusalSlot)
        await settle(pilot)
        assert not slot.children
        slot.show(refusal)
        await settle(pilot)
        (panel,) = slot.query(RefusalPanel)
        slot.show(refusal)
        await settle(pilot)
        assert slot.query_one(RefusalPanel) is panel
        slot.show(None)
        await settle(pilot)
        assert not slot.children
        assert slot.refusal is None


def test_a_request_prefill_reaches_the_operations_destination_context() -> None:
    seen: list[TuiScreenContextV1] = []

    def capturing(context: TuiScreenContextV1) -> Screen[None]:
        seen.append(context)
        return MarkerScreen()

    catalogue = build_destination_catalogue(
        admissions={
            descriptor.destination: TuiDestinationAdmissionV1(
                destination=descriptor.destination, state=WorkbenchDestinationAdmissionState.AVAILABLE
            )
            for descriptor in TUI_DESTINATION_CATALOGUE
        },
        factories={descriptor.destination: capturing for descriptor in TUI_DESTINATION_CATALOGUE},
    )
    verdict = primary_verdict(CREATE_WORK)
    target = TuiNavigationTargetV1(
        destination=OPERATIONS_DESTINATION,
        focus=TuiFocusIdentityV1(destination=OPERATIONS_DESTINATION, semantic_key=OPERATION_FOCUS_KEY),
        request_prefill=verdict.argument_bindings,
    )

    catalogue.create_screen(target)

    (context,) = seen
    assert context.request_prefill == verdict.argument_bindings
