"""The installed invoice-add door preserves its typed runtime request and receipt."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel
from textual.widgets import Button, Input, Static

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.invoices.catalogue_add_contracts import (
    INVOICE_ADD_OPERATION_DEFINITION_ID,
    INVOICE_ADD_VALIDATION_REFUSAL_CODE,
    InvoiceAddLine,
    InvoiceAddRequest,
    InvoiceAddResult,
)
from cadrumo.application.invoices.catalogue_add_operation import (
    build_invoice_add_definition,
    build_invoice_add_registration,
)
from cadrumo.application.invoices.catalogue_creation_ports import CatalogueCreationPortsFactory
from cadrumo.application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot, InvoiceLineSnapshot
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import OperationObservationSuccessV1, OperationPublicEventPageV1
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.public_scalar import PublicDecimal
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationRegistry,
)
from cadrumo.core.aggregation import IntracomOperationType
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.domain.invoices.enums import PaymentStatus
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.domain.iva.schema import IvaCategory
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.ledger.controller import LedgerWorkspaceController
from cadrumo.entrypoints.tui.ledger.invoice_entry import LedgerInvoiceEntryScreen
from cadrumo.entrypoints.tui.ledger.models import (
    LedgerFlowState,
    LedgerInvoiceAddDoorV1,
    LedgerInvoiceAddResultV1,
    LedgerInvoiceClassChoice,
    LedgerInvoiceEntryV1,
    LedgerInvoiceLineEntryV1,
)
from cadrumo.entrypoints.tui.ledger.runtime_invoice_add import RuntimeInvoiceAddTuiDoorV1, _request_from_entry
from cadrumo.entrypoints.tui.ledger.tests.workspace_fixtures import (
    ledger_context,
    ledger_projection,
    ledger_review_action,
)
from cadrumo.entrypoints.tui.ledger.workspace_injection import LedgerWorkspaceInjection
from cadrumo.entrypoints.tui.operations.runtime_controller import RuntimeOperationController

pytestmark = pytest.mark.hex_entrypoint

_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000aa")
_SESSION_ID = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "a" * 64
_NOW = datetime(2026, 9, 29, tzinfo=UTC)


class _Client:
    frontend = OperationFrontendProjection.TUI

    def __init__(self) -> None:
        self.profile_id = _PROFILE_ID
        self.session_id = _SESSION_ID


class _Controller:
    operation_id = _OPERATION_ID

    def __init__(
        self,
        *,
        observation: OperationObservationSuccessV1,
        result: InvoiceAddResult,
        client: _Client,
        expire_after_result: bool = False,
    ) -> None:
        self.observation = observation
        self.result = result
        self.client = client
        self.expire_after_result = expire_after_result
        self.started = False
        self.result_reads: list[tuple[type[BaseModel], int, bool]] = []

    async def start(self) -> str:
        self.started = True
        return self.operation_id

    async def observe(self, after_cursor: int, *, page_limit: int) -> OperationObservationSuccessV1:
        assert after_cursor == 0
        assert page_limit == 1
        return self.observation

    async def read_settled_result(
        self,
        projection: OperationPublicProjectionV1,
        result_type: type[BaseModel],
        *,
        result_version: int,
        allow_refusal_detail: bool = False,
    ) -> InvoiceAddResult:
        assert projection.operation_id == self.operation_id
        self.result_reads.append((result_type, result_version, allow_refusal_detail))
        if self.expire_after_result:
            self.client.session_id = UUID("7cc00000-0000-4000-8000-0000000000cc")
        return self.result


def _entry() -> LedgerInvoiceEntryV1:
    return LedgerInvoiceEntryV1(
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Proveedor Example SL",
        counterparty_nif="B12345678",
        country_code="ES",
        invoice_number="TUI-007",
        invoice_date=date(2026, 3, 16),
        taxable_base=None,
        iva_rate=None,
        lines=(
            LedgerInvoiceLineEntryV1(
                description="Consulting",
                quantity=Decimal("2.0"),
                unit_price=Decimal("50.00"),
                subtotal=Decimal("100.00"),
                iva_rate="RATE_21",
                iva_amount=Decimal("21.00"),
                spending_category_id="professional-services",
                oss_rate_kind="standard",
            ),
        ),
        operation_type=IntracomOperationType.A,
        operation_date=date(2026, 3, 15),
        recargo_amount=Decimal("0.77"),
        rectifies_invoice_number="TUI-006",
        iva_category=IvaCategory("general"),
        currency="USD",
        retention_rate=Decimal("15.0"),
        retention_amount=Decimal("15.00"),
        invoice_class=LedgerInvoiceClassChoice.RECTIFICATIVA,
        series="SER-1",
        notes="typed note",
    )


def _invoice_snapshot() -> CatalogueInvoiceSnapshot:
    return CatalogueInvoiceSnapshot(
        invoice_id="c" * 64,
        bucket_id=str(_PROFILE_ID),
        kind=InvoiceKind.RECEIVED,
        invoice_number="TUI-007",
        issued_at=date(2026, 3, 16),
        counterparty_name="Proveedor Example SL",
        counterparty_tax_id="B12345678",
        counterparty_country="ES",
        base_total=PublicDecimal(decimal="100.00"),
        iva_total=PublicDecimal(decimal="21.00"),
        grand_total=PublicDecimal(decimal="121.00"),
        currency="USD",
        payment_status=PaymentStatus.PENDING,
        linked_transaction_ids=(),
        source_filename=None,
        source_sha256=None,
        source_row_index=None,
        notes="typed note",
        retention_rate=PublicDecimal(decimal="15.0"),
        retention_amount=PublicDecimal(decimal="15.00"),
        recargo_amount=PublicDecimal(decimal="0.77"),
        operation_type=IntracomOperationType.A,
        lines=(
            InvoiceLineSnapshot(
                description="Consulting",
                quantity=PublicDecimal(decimal="2.0"),
                unit_price=PublicDecimal(decimal="50.00"),
                subtotal=PublicDecimal(decimal="100.00"),
                iva_rate="RATE_21",
                iva_amount=PublicDecimal(decimal="21.00"),
                spending_category_id="professional-services",
                oss_rate_kind="standard",
            ),
        ),
        invoice_class="rectificativa",
        series="SER-1",
        operation_date=date(2026, 3, 15),
        operation_date_role=None,
        iva_category="general",
        rectifies_invoice_number="TUI-006",
        fx_rate=None,
        fx_rate_date=None,
        fx_rate_source=None,
        base_total_eur=None,
        iva_total_eur=None,
        grand_total_eur=None,
    )


def _operation_contract() -> tuple[OperationPublicDefinitionContractV1, str]:
    factory = cast(CatalogueCreationPortsFactory, cast(object, lambda **_kwargs: None))
    definition = build_invoice_add_definition(factory)
    registration = build_invoice_add_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    return registry.lookup_public_contract(
        INVOICE_ADD_OPERATION_DEFINITION_ID
    ), registry.public_contract_set.contract_set_digest


def _observation(*, refused: bool = False) -> OperationObservationSuccessV1:
    contract, contract_set_digest = _operation_contract()
    condition = OperationTerminalCondition.REFUSED if refused else OperationTerminalCondition.SUCCEEDED
    effect = OperationEffect.NONE if refused else OperationEffect.UPDATED
    state = OperationPublicProjectionV1(
        operation_id=_OPERATION_ID,
        definition_id=INVOICE_ADD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE_ID)),
        revision=1,
        anchor_cursor=0,
        definition_contract=contract,
        contract_set_digest=contract_set_digest,
        lifecycle=OperationLifecycle.TERMINAL,
        terminal_condition=condition,
        effect=effect,
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
        result_ref=None if refused else "f" * 64,
        refusal_ref=INVOICE_ADD_VALIDATION_REFUSAL_CODE if refused else None,
        failure_error_code=None,
        diagnostic_ref=None,
    )
    return OperationObservationSuccessV1(
        projection=state,
        event_page=OperationPublicEventPageV1(
            operation_id=_OPERATION_ID,
            anchor_cursor=0,
            requested_cursor=0,
            status=OperationReplayStatus.CAUGHT_UP,
            events=(),
            next_cursor=0,
            restart_cursor=None,
        ),
    )


def _created_result() -> InvoiceAddResult:
    return InvoiceAddResult.created(
        _PROFILE_ID,
        invoice=_invoice_snapshot(),
        bucket_event_ids=("e" * 64,),
        euro_value_pending=True,
        simplificada_tax_id_advisory_required=False,
    )


def _install_runtime(
    monkeypatch: pytest.MonkeyPatch,
    *,
    client: _Client,
    result: InvoiceAddResult,
    refused: bool = False,
    expire_after_result: bool = False,
) -> tuple[list[dict[str, object]], _Controller, list[tuple[UUID, UUID]]]:
    from cadrumo.entrypoints.tui.operations import runtime_profile_session as bridge

    status_checks: list[tuple[UUID, UUID]] = []

    def read_session(
        _client: RuntimeFrontendClient,
        *,
        profile_id: UUID,
        session_id: UUID,
        profile_label: str,
    ) -> object:
        assert profile_label == "Fixture profile"
        status_checks.append((profile_id, session_id))
        if client.profile_id != profile_id or client.session_id != session_id:
            raise AccountSessionExpiredError()
        return object()

    monkeypatch.setattr(bridge, "read_runtime_account_session", read_session)
    controller = _Controller(
        observation=_observation(refused=refused),
        result=result,
        client=client,
        expire_after_result=expire_after_result,
    )
    submissions: list[dict[str, object]] = []

    async def submit(
        _controller_type: type[RuntimeOperationController],
        received_client: RuntimeFrontendClient,
        **kwargs: object,
    ) -> _Controller:
        assert received_client is client
        submissions.append(kwargs)
        return controller

    monkeypatch.setattr(RuntimeOperationController, "submit", classmethod(submit))
    return submissions, controller, status_checks


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invoice_add_tui_door_preserves_the_complete_entry_and_worker_totals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    entry = _entry()
    submissions, controller, status_checks = _install_runtime(
        monkeypatch,
        client=client,
        result=_created_result(),
    )
    door = RuntimeInvoiceAddTuiDoorV1(cast(RuntimeFrontendClient, client), profile_label="Fixture profile")

    result = await door(entry)

    assert result == LedgerInvoiceAddResultV1(
        invoice_id="c" * 64,
        invoice_number="TUI-007",
        base_total=Decimal("100.00"),
        iva_total=Decimal("21.00"),
        grand_total=Decimal("121.00"),
        currency="USD",
        euro_value_pending=True,
    )
    assert controller.started
    assert controller.result_reads == [(InvoiceAddResult, 1, True)]
    assert all(binding == (_PROFILE_ID, _SESSION_ID) for binding in status_checks)
    submitted = submissions[0]
    assert submitted["definition_id"] == INVOICE_ADD_OPERATION_DEFINITION_ID
    assert submitted["subject_ref"] == profile_operation_subject(str(_PROFILE_ID))
    assert submitted["expected_session_id"] == _SESSION_ID
    assert submitted["payload"] == InvoiceAddRequest(
        profile_id=_PROFILE_ID,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Proveedor Example SL",
        counterparty_tax_id="B12345678",
        counterparty_country="ES",
        invoice_number="TUI-007",
        issued_at=date(2026, 3, 16),
        taxable_base=None,
        iva_rate=None,
        currency="USD",
        notes="typed note",
        iva_category="general",
        operation_type=IntracomOperationType.A,
        operation_date=date(2026, 3, 15),
        retention_rate=PublicDecimal(decimal="15.0"),
        retention_amount=PublicDecimal(decimal="15.00"),
        invoice_class="rectificativa",
        series="SER-1",
        rectifies_invoice_number="TUI-006",
        recargo_amount=PublicDecimal(decimal="0.77"),
        lines=(
            InvoiceAddLine(
                description="Consulting",
                quantity=PublicDecimal(decimal="2.0"),
                unit_price=PublicDecimal(decimal="50.00"),
                subtotal=PublicDecimal(decimal="100.00"),
                iva_rate="RATE_21",
                iva_amount=PublicDecimal(decimal="21.00"),
                spending_category_id="professional-services",
                oss_rate_kind="standard",
            ),
        ),
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invoice_add_tui_door_preserves_receipt_for_a_duplicate_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cadrumo.domain.invoices.errors import InvoiceValidationError

    client = _Client()
    refusal = InvoiceAddResult.validation_refusal(
        _PROFILE_ID,
        code="duplicate_invoice",
        invoice_id="c" * 64,
    )
    submissions, _controller, _status_checks = _install_runtime(
        monkeypatch,
        client=client,
        result=refusal,
        refused=True,
    )
    door = RuntimeInvoiceAddTuiDoorV1(cast(RuntimeFrontendClient, client), profile_label="Fixture profile")

    with pytest.raises(InvoiceValidationError) as raised:
        await door(_entry())

    assert submissions[0]["expected_session_id"] == _SESSION_ID
    assert raised.value.translated_message == "application.invoices.creation.errors.duplicate_invoice"
    assert raised.value.context == {
        "operation_id": _OPERATION_ID,
        "terminal_condition": OperationTerminalCondition.REFUSED.value,
        "effect": OperationEffect.NONE.value,
        "refusal_code": INVOICE_ADD_VALIDATION_REFUSAL_CODE,
        "invoice_id": "c" * 64,
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invoice_add_tui_door_clears_disclosure_if_session_expires_after_settlement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    submissions, _controller, _status_checks = _install_runtime(
        monkeypatch,
        client=client,
        result=_created_result(),
        expire_after_result=True,
    )
    door = RuntimeInvoiceAddTuiDoorV1(cast(RuntimeFrontendClient, client), profile_label="Fixture profile")

    with pytest.raises(AccountSessionExpiredError) as raised:
        await door(_entry())

    assert submissions[0]["expected_session_id"] == _SESSION_ID
    assert raised.value.context == {
        "operation_id": _OPERATION_ID,
        "terminal_condition": OperationTerminalCondition.SUCCEEDED.value,
        "effect": OperationEffect.UPDATED.value,
        "refusal_code": None,
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invoice_add_tui_door_refuses_a_replaced_session_before_submit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    submissions, _controller, _status_checks = _install_runtime(
        monkeypatch,
        client=client,
        result=_created_result(),
    )
    door = RuntimeInvoiceAddTuiDoorV1(cast(RuntimeFrontendClient, client), profile_label="Fixture profile")
    client.session_id = UUID("7cc00000-0000-4000-8000-0000000000cc")

    with pytest.raises(AccountSessionExpiredError):
        await door(_entry())

    assert submissions == []


class _ExpiredDoor:
    async def __call__(self, _entry: LedgerInvoiceEntryV1) -> LedgerInvoiceAddResultV1:
        raise AccountSessionExpiredError(
            context={
                "operation_id": _OPERATION_ID,
                "terminal_condition": OperationTerminalCondition.SUCCEEDED.value,
                "effect": OperationEffect.UPDATED.value,
                "refusal_code": None,
            }
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invoice_entry_clears_private_form_when_the_add_door_reports_expiry() -> None:
    screen = LedgerInvoiceEntryScreen(
        LedgerWorkspaceController(
            ledger_context(),
            ledger_projection(),
            LedgerWorkspaceInjection(
                review_action=ledger_review_action(),
                invoice_add_door=cast(LedgerInvoiceAddDoorV1, _ExpiredDoor()),
            ),
        )
    )

    async with ScreenHostApp[None](screen).run_test(size=(110, 200)) as pilot:
        await pilot.pause()
        for name, value in {
            "counterparty_name": "Private counterparty",
            "counterparty_nif": "B12345678",
            "invoice_number": "PRIVATE-007",
            "invoice_date": "2026-03-16",
            "taxable_base": "100.00",
            "iva_rate": "21",
            "notes": "private note",
        }.items():
            screen.query_one(f"#ledger-invoice-{name.replace('_', '-')}", Input).value = value
        screen.query_one("#ledger-invoice-review", Button).press()
        await pilot.pause()
        assert screen.flow_state is LedgerFlowState.CONFIRMING
        assert screen.entry is not None
        screen.query_one("#ledger-invoice-confirm", Button).press()
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()

        assert screen.flow_state is LedgerFlowState.FAILED
        assert screen.entry is None
        assert screen.lines == []
        assert all(not field.value for field in screen.query(Input))
        assert str(screen.query_one("#ledger-invoice-summary", Static).render()).strip() == ""
        assert "PRIVATE-007" not in str(screen.query_one("#ledger-flow-status", Static).render())


@pytest.mark.unit
def test_the_tui_request_carries_the_business_premises_lease_facts() -> None:
    """The TUI submits the lease facts on the same add request the CLI builds."""
    entry = _entry().model_copy(
        update={
            "kind": InvoiceKind.ISSUED,
            "arrendamiento_local_negocio": True,
            "situacion_inmueble": "1",
            "referencia_catastral": "9872023VH5797S0001WX",
        },
    )

    request = _request_from_entry(_PROFILE_ID, entry)

    assert request.arrendamiento_local_negocio is True
    assert request.situacion_inmueble == "1"
    assert request.referencia_catastral == "9872023VH5797S0001WX"
