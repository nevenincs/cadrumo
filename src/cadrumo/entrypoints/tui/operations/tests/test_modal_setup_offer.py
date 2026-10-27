"""A refusal that needs a setup item keeps the operation modal open on that item's current row.

The recorded details come from the real producers: the browser launch guard
over an empty browser cache, and the local reader probe over an inventory
without the role's model, each projected by the operation error detail
builder. The item's row comes from the real row derivation: absent, so its
action sets it up, or blocked as not in this build, as every item reads while
this build sets nothing up. The modal runs under Textual's pilot with a
scripted controller that serves one refused terminal observation and that
detail. An offerable row gets the setup offer; a blocked row shows its own
sentence and offers nothing; a host that reads no setup status closes the
modal at once. One host records the navigation request the offer posts; the
real TUI root reads the row through its setup door, admits the request and
opens the setup page on that item's row.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

import pytest
from pydantic import BaseModel
from textual.app import App
from textual.screen import Screen
from textual.widgets import Button, DataTable, Static

from .....adapters.outbound.aeat.browser.session import require_browser_ready
from .....adapters.outbound.components.tests.recorded_rows import not_in_this_build_row, recorded_absent_row
from .....application.dependency_contracts import DependencyStatusRow
from .....application.ledger.evidence_errors import PurchaseInvoiceEvidenceReaderError
from .....application.modelo.operation_definitions import (
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    build_modelo_work_calculate_definition,
    build_modelo_work_calculate_registration,
)
from .....application.operations.error_detail import OperationErrorDetailV1, build_operation_error_detail
from .....application.operations.frontend_contracts import (
    OperationCancellationResultV1,
    OperationDetachResultV1,
    OperationReviewProjectionResultV1,
)
from .....application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
    OperationReviewProjectionReferenceV1,
)
from .....application.operations.frontend_requests import OperationObservationSuccessV1, OperationPublicEventPageV1
from .....application.operations.persistence.replay import OperationReplayStatus
from .....application.operations.registry import OperationPublicContractSetV1, OperationPublicDefinitionContractV1
from .....application.provisioning_contracts import (
    LOCAL_AI_PROVISION_ACTION_ID,
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
    provisioning_setup_verdict,
)
from .....application.search.workbench import WorkbenchDestinationAdmissionState
from .....core.config import Settings, override_settings
from .....core.errors.hierarchy import CadrumoError
from .....core.model_roles import ModelRole
from .....core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition
from ...app import CadrumoTuiApp
from ...navigation import (
    TUI_DESTINATION_CATALOGUE,
    TuiDestinationAdmissionV1,
    TuiDestinationCatalogueV1,
    TuiFocusIdentityV1,
    TuiNavigationTargetV1,
    TuiScreenContextV1,
    build_destination_catalogue,
)
from ...setup.focus import SetupItemRequested, setup_item_focus, setup_item_target
from ...setup.screen import SetupScreen
from ...setup.tests.operations_fixture import SetupFixture
from ...tests.home_fixtures import HomeFixtureScenario, build_home_projection_fixture
from ...tests.settling import settle, settle_until
from ..controller_port import OperationResponseControlPort
from ..modal import OperationModal, OperationModalSettledOutcomeV1
from ..refusal_explanation import operation_error_explanation, recorded_setup_item

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_OPERATION_ID = "c" * 64
_NOW = datetime(2026, 10, 24, tzinfo=UTC)
_SIZE = (120, 40)
_READER_MESSAGE_KEY = "errors.refused.refused_ledger_evidence_reader_unavailable"


def _unavailable(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("contract construction must not open a private profile")


def _contract() -> OperationPublicDefinitionContractV1:
    definition = build_modelo_work_calculate_definition(
        calculation_action_ports_factory=_unavailable,
        attachment_store_factory=_unavailable,
    )
    return build_modelo_work_calculate_registration(definition).contract


def _recorded(error: CadrumoError) -> OperationErrorDetailV1:
    detail = build_operation_error_detail(error)
    assert detail is not None
    return detail


def _browser_detail(empty_cache: Path) -> OperationErrorDetailV1:
    """The detail a tax agency read records when the browser build is missing."""
    try:
        require_browser_ready(Settings(cadrumo_playwright_browsers_dir=empty_cache), profile_name="setup-offer")
    except CadrumoError as error:
        return _recorded(error)
    raise AssertionError("an empty browser cache must refuse browser work")


def _reader_detail() -> OperationErrorDetailV1:
    """The detail an evidence read records when the role's selected model is not installed."""
    verdict = provisioning_setup_verdict(
        ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED,
        facts={"role": ModelRole.TEXT_EXTRACTION.value, "role_model_installed": False},
        action_id=LOCAL_AI_PROVISION_ACTION_ID,
    )
    return _recorded(
        PurchaseInvoiceEvidenceReaderError(translated_message=_READER_MESSAGE_KEY, precondition_verdict=verdict)
    )


def _hardware_detail() -> OperationErrorDetailV1:
    """The detail of a reader refusal that setup cannot fix, so its verdict names no action."""
    verdict = provisioning_no_recovery_verdict(
        ProvisioningPreconditionCondition.SELECTED_MODEL_AVAILABLE,
        facts={"role": ModelRole.TEXT_EXTRACTION.value, "role_model_selected": False},
    )
    return _recorded(
        PurchaseInvoiceEvidenceReaderError(translated_message=_READER_MESSAGE_KEY, precondition_verdict=verdict)
    )


def _refused(contract: OperationPublicDefinitionContractV1, code: str) -> OperationObservationSuccessV1:
    projection = OperationPublicProjectionV1(
        operation_id=_OPERATION_ID,
        definition_id=MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        subject_ref="b" * 64,
        revision=3,
        anchor_cursor=0,
        definition_contract=contract,
        contract_set_digest=OperationPublicContractSetV1.build((contract,)).contract_set_digest,
        lifecycle=OperationLifecycle.TERMINAL,
        terminal_condition=OperationTerminalCondition.REFUSED,
        effect=OperationEffect.NONE,
        phase_code=None,
        started_at=_NOW,
        updated_at=_NOW,
        progress=None,
        close_policy=contract.close_policy,
        cancellation=contract.cancellation,
        cancellable_now=False,
        cancellation_requested=False,
        cancellation_acknowledged=False,
        execution_deadline_at=None,
        cleanup_deadline_at=None,
        pending_interaction=OperationNoPendingInteractionV1(),
        result_ref=None,
        refusal_ref=code,
        failure_error_code=None,
        diagnostic_ref=None,
    )
    page = OperationPublicEventPageV1(
        operation_id=_OPERATION_ID,
        anchor_cursor=0,
        requested_cursor=0,
        status=OperationReplayStatus.CAUGHT_UP,
        events=(),
        next_cursor=0,
        restart_cursor=None,
    )
    return OperationObservationSuccessV1(projection=projection, event_page=page)


class _RefusedController:
    """A runtime binding whose one observation is a refused settlement with a recorded detail."""

    def __init__(self, detail: OperationErrorDetailV1 | None, code: str) -> None:
        self.detail = detail
        self.observation = _refused(_contract(), code)

    @property
    def operation_id(self) -> str:
        return _OPERATION_ID

    @property
    def actor_ref(self) -> str:
        return "operator:setup-offer"

    async def start(self) -> str:
        return _OPERATION_ID

    async def observe(self, after_cursor: int, *, page_limit: int = 256) -> OperationObservationSuccessV1:
        return self.observation

    async def settled_error_detail(self, projection: OperationPublicProjectionV1) -> OperationErrorDetailV1 | None:
        assert projection == self.observation.projection
        return self.detail

    async def resolve_review[ReviewT: BaseModel](
        self, reference: OperationReviewProjectionReferenceV1, projection_type: type[ReviewT]
    ) -> OperationReviewProjectionResultV1[ReviewT]:
        raise AssertionError("no review is pending")

    async def response_control(self, *, interaction_id: str, revision: int) -> OperationResponseControlPort:
        raise AssertionError("no review is pending")

    async def cancel(self, *, expected_revision: int) -> OperationCancellationResultV1:
        raise AssertionError("a settled operation is not cancelled")

    async def detach(self, *, expected_revision: int) -> OperationDetachResultV1:
        raise AssertionError("a settled operation is not detached")


class _Host(App[None]):
    """Opens one modal, keeps its outcome, and records every setup navigation request it receives.

    It reads each item's row from ``rows``, as the TUI root reads the quick setup status.
    """

    def __init__(self, controller: _RefusedController, rows: tuple[DependencyStatusRow, ...] = ()) -> None:
        super().__init__()
        self.controller = controller
        self.rows = rows
        self.row_reads: list[str] = []
        self.modal = OperationModal(controller)
        self.outcome: object = None
        self.closed = False
        self.requested: list[str] = []

    def _dismissed(self, outcome: object) -> None:
        self.outcome = outcome
        self.closed = True

    def on_mount(self) -> None:
        self.push_screen(self.modal, self._dismissed)

    def on_setup_item_requested(self, message: SetupItemRequested) -> None:
        self.requested.append(message.item_id)

    async def read_setup_row(self, item_id: str) -> DependencyStatusRow | None:
        self.row_reads.append(item_id)
        return next((row for row in self.rows if row.item_id == item_id), None)


class _HostWithoutSetupStatus(App[None]):
    """Opens one modal in a session that reads no setup status, and records its outcome."""

    def __init__(self, controller: _RefusedController) -> None:
        super().__init__()
        self.modal = OperationModal(controller)
        self.outcome: object = None
        self.closed = False

    def _dismissed(self, outcome: object) -> None:
        self.outcome = outcome
        self.closed = True

    def on_mount(self) -> None:
        self.push_screen(self.modal, self._dismissed)


def _controller(detail: OperationErrorDetailV1 | None) -> _RefusedController:
    code = "REFUSED_LEDGER_EVIDENCE_READER" if detail is None or detail.error_code is None else detail.error_code
    return _RefusedController(detail, code)


def _offer(host: _Host) -> Button:
    return host.modal.query_one("#btn-operation-setup", Button)


def test_a_refusal_names_the_setup_item_its_recorded_verdict_asks_for(tmp_path: Path) -> None:
    assert recorded_setup_item(_browser_detail(tmp_path)) == "browser"
    assert recorded_setup_item(_reader_detail()) == "local_ai"
    assert recorded_setup_item(_hardware_detail()) is None
    assert recorded_setup_item(None) is None


@pytest.mark.asyncio
async def test_a_missing_browser_refusal_offers_its_setup_and_asks_the_root_to_open_it(tmp_path: Path) -> None:
    detail = _browser_detail(tmp_path)
    host = _Host(_controller(detail), rows=(recorded_absent_row("browser"), recorded_absent_row("local_ai")))
    with override_settings(cadrumo_output_language="en"):
        async with host.run_test(size=_SIZE) as pilot:
            await settle_until(pilot, lambda: _offer(host).display, "the setup offer to be shown")

            assert not host.closed
            assert str(_offer(host).label) == "Set up: Browser for the tax agency website"
            assert host.focused is _offer(host)
            explanation = operation_error_explanation(detail)
            assert explanation is not None and explanation != ""
            assert str(host.modal.query_one("#operation-modal-setup", Static).render()) == explanation

            await pilot.click("#btn-operation-setup")
            await settle_until(pilot, lambda: host.closed and bool(host.requested), "the offer to be taken")

    assert host.requested == ["browser"]
    assert host.row_reads == ["browser"]
    assert isinstance(host.outcome, OperationModalSettledOutcomeV1)
    assert host.outcome.view_model.projection == host.controller.observation.projection
    assert host.outcome.error_explanation == explanation


@pytest.mark.asyncio
async def test_a_local_ai_refusal_points_to_the_desktop_app_and_offers_no_setup() -> None:
    host = _Host(_controller(_reader_detail()), rows=(recorded_absent_row("local_ai"),))
    with override_settings(cadrumo_output_language="en"):
        async with host.run_test(size=_SIZE) as pilot:
            reason = host.modal.query_one("#operation-modal-setup", Static)
            await settle_until(pilot, lambda: bool(str(reason.render())), "the desktop pointer to be shown")

            assert not host.closed
            assert not _offer(host).display
            assert str(reason.render()).splitlines()[-1] == (
                "Local AI: Not set up yet. Set it up in the Cadrumo desktop app."
            )

            await pilot.press("escape")
            await settle_until(pilot, lambda: host.closed, "the modal to close")

    assert host.requested == []
    assert host.row_reads == ["local_ai"]
    assert isinstance(host.outcome, OperationModalSettledOutcomeV1)


@pytest.mark.asyncio
@pytest.mark.parametrize("detail", [_hardware_detail(), None], ids=["no-recovery verdict", "no detail"])
async def test_a_refusal_setup_cannot_fix_closes_the_modal_at_once(detail: OperationErrorDetailV1 | None) -> None:
    host = _Host(_controller(detail), rows=(recorded_absent_row("local_ai"),))
    async with host.run_test(size=_SIZE) as pilot:
        await settle_until(pilot, lambda: host.closed, "the modal to close on settlement")

    assert host.requested == []
    assert host.row_reads == []
    assert isinstance(host.outcome, OperationModalSettledOutcomeV1)
    assert host.outcome.error_explanation == operation_error_explanation(detail)


@pytest.mark.asyncio
async def test_a_blocked_item_shows_its_own_sentence_and_offers_no_setup() -> None:
    """While this build sets nothing up, the local AI reads blocked: its sentence stands in for the offer."""
    detail = _reader_detail()
    host = _Host(_controller(detail), rows=(not_in_this_build_row("local_ai"),))
    with override_settings(cadrumo_output_language="en"):
        async with host.run_test(size=_SIZE) as pilot:
            reason = host.modal.query_one("#operation-modal-setup", Static)
            await settle_until(pilot, lambda: bool(str(reason.render())), "the item's sentence to be shown")

            assert not host.closed
            assert not _offer(host).display
            assert str(reason.render()).splitlines()[-1] == "Local AI: This version of Cadrumo does not include this."
            assert host.focused is host.modal.query_one("#btn-operation-close", Button)
            explanation = operation_error_explanation(detail)

            await pilot.press("escape")
            await settle_until(pilot, lambda: host.closed, "the modal to close")

    assert host.requested == []
    assert host.row_reads == ["local_ai"]
    assert isinstance(host.outcome, OperationModalSettledOutcomeV1)
    assert host.outcome.error_explanation == explanation


@pytest.mark.asyncio
async def test_a_session_that_reads_no_setup_status_closes_the_modal_at_once() -> None:
    host = _HostWithoutSetupStatus(_controller(_reader_detail()))
    async with host.run_test(size=_SIZE) as pilot:
        await settle_until(pilot, lambda: host.closed, "the modal to close on settlement")

    assert isinstance(host.outcome, OperationModalSettledOutcomeV1)


class _Page(Screen[None]):
    """A destination body the modal is opened over."""


def _root_catalogue(door: SetupFixture, contexts: list[TuiScreenContextV1]) -> TuiDestinationCatalogueV1:
    def page(context: TuiScreenContextV1) -> Screen[None]:
        return _Page()

    def setup(context: TuiScreenContextV1) -> Screen[None]:
        contexts.append(context)
        return SetupScreen(door, focus_item=setup_item_focus(context))

    available = WorkbenchDestinationAdmissionState.AVAILABLE
    destinations = [descriptor.destination for descriptor in TUI_DESTINATION_CATALOGUE]
    return build_destination_catalogue(
        admissions={
            destination: TuiDestinationAdmissionV1(destination=destination, state=available)
            for destination in destinations
        },
        factories={destination: setup if destination == "workbench.setup" else page for destination in destinations},
    )


@pytest.mark.asyncio
async def test_the_root_opens_the_setup_page_on_the_item_the_refusal_needs(tmp_path: Path) -> None:
    # The root and setup page consume the same typed application status rows.
    door = SetupFixture()
    contexts: list[TuiScreenContextV1] = []
    app = CadrumoTuiApp(
        destination_catalogue=_root_catalogue(door, contexts),
        refresh_home=lambda: build_home_projection_fixture(HomeFixtureScenario.READY),
        setup_status=door,
    )
    with override_settings(cadrumo_output_language="en"):
        async with app.run_test(size=_SIZE) as pilot:
            await settle(pilot)
            app.navigate_to(
                TuiNavigationTargetV1(
                    destination="workbench.ledger",
                    focus=TuiFocusIdentityV1(destination="workbench.ledger", semantic_key="navigation.ledger"),
                )
            )
            await settle_until(pilot, lambda: isinstance(app.screen, _Page), "the ledger page to open")
            modal = OperationModal(_controller(_browser_detail(tmp_path)))
            app.push_screen(modal)
            await settle_until(
                pilot, lambda: modal.query_one("#btn-operation-setup", Button).display, "the setup offer"
            )

            await pilot.click("#btn-operation-setup")
            await settle_until(pilot, lambda: isinstance(app.screen, SetupScreen), "the setup page to open")
            screen = app.screen
            assert isinstance(screen, SetupScreen)
            await settle_until(pilot, lambda: bool(screen.rows), "the setup rows to be read")
            table = screen.query_one("#setup-items", DataTable)

            assert [context.focus for context in contexts] == [setup_item_target("browser").focus]
            assert table.ordered_rows[table.cursor_row].key.value == "browser"
            assert screen.focused is table
            assert len(app.screen_stack) == 2
            # The offer read the item's row first; the setup page then read every row.
