"""TUI evidence operations remain bound to the reviewed source and receipt."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.outbound.components.tests.recorded_rows import recorded_absent_row
from cadrumo.application.cli_exception_preconditions import nested_terminal_precondition_verdict
from cadrumo.application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot
from cadrumo.application.ledger.evidence import MediaKind
from cadrumo.application.ledger.evidence_add_operation import (
    LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
    LedgerEvidenceAddProjection,
    LedgerEvidenceAddRequest,
    build_ledger_evidence_add_definition,
    build_ledger_evidence_add_registration,
)
from cadrumo.application.ledger.evidence_errors import (
    EVIDENCE_LOCAL_AI_NOT_READY_LOCALE_KEY,
    PurchaseInvoiceEvidenceReaderError,
    evidence_reader_refusal_key,
)
from cadrumo.application.ledger.evidence_ports import LedgerEvidencePortsFactory
from cadrumo.application.ledger.evidence_read_operation import (
    LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID,
    LedgerEvidenceListProjection,
    LedgerEvidenceRecordProjection,
    build_ledger_evidence_list_definition,
    build_ledger_evidence_list_registration,
)
from cadrumo.application.ledger.invoice_evidence_confirm_operation import (
    LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
    LedgerEvidenceConfirmProjection,
    LedgerEvidenceConfirmRequest,
    build_ledger_evidence_confirm_definition,
    build_ledger_evidence_confirm_registration,
)
from cadrumo.application.ledger.invoice_evidence_extract_operation import (
    LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
    LedgerEvidenceExtractProjection,
    LedgerEvidenceExtractRequest,
    build_ledger_evidence_extract_definition,
    build_ledger_evidence_extract_registration,
)
from cadrumo.application.ledger.invoice_evidence_operation import InvoiceEvidenceOperationPortsFactory
from cadrumo.application.ledger.invoice_evidence_operation_dtos import (
    DraftDiscrepancyProjectionV1,
    FieldAmbiguityCandidateProjectionV1,
    FieldProvenanceProjectionV1,
    InvoiceConfirmationProjectionV1,
    InvoiceDraftLineProjectionV1,
    InvoiceDraftProjectionV1,
    InvoiceDraftRateBreakdownProjectionV1,
    StructuredInvoiceClassProjectionV1,
)
from cadrumo.application.ledger.structured_invoice_ports import StructuredInvoiceClassificationKind
from cadrumo.application.local_reader import probe_local_ai_program
from cadrumo.application.operations.error_detail import OperationErrorDetailV1, build_operation_error_detail
from cadrumo.application.operations.frontend_requests import OperationObservationSuccessV1
from cadrumo.application.operations.public_scalar import PublicDecimal
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationRegistry,
)
from cadrumo.application.provisioning_contracts import LOCAL_AI_PROVISION_ACTION_ID
from cadrumo.core.config import override_settings
from cadrumo.core.draft_discrepancy import DraftDiscrepancyKind
from cadrumo.core.errors.error_codes import resolve_error_message
from cadrumo.core.errors.hierarchy import RecordedRegisteredError
from cadrumo.core.field_grounding import FieldGroundingOutcome
from cadrumo.core.field_origin import FieldOrigin
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.domain.iva.schema import InvoiceKind
from cadrumo.domain.iva.supply_nature import SupplyNature
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo.entrypoints.tui.ledger.evidence_draft import draft_lines
from cadrumo.entrypoints.tui.ledger.models import LedgerEvidenceConfirmationV1, LedgerEvidenceRecordStatus
from cadrumo.entrypoints.tui.operations.outcome import OperationOutcomeUnknownError
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.operation_controller import OperationController

from ....frontend.tui.runtime_evidence import RuntimeEvidenceTuiDoorV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000aa")
_SESSION_ID = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OPERATION_ID = "d" * 64
_SOURCE_DIGEST = "a" * 64
_DRAFT_DIGEST = "b" * 64
#: Extraction and confirmation results carry the label-reading fallback beside
#: the draft, so they read the second result schema; the other reads stay on the first.
_RESULT_VERSIONS = {
    LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID: 1,
    LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID: 1,
    LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID: 3,
    LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID: 2,
}


def _contracts() -> dict[str, OperationPublicDefinitionContractV1]:
    """The four evidence operations' public contracts, declared through their own builders."""
    evidence = cast(LedgerEvidencePortsFactory, cast(object, lambda **_kwargs: None))
    invoice_evidence = cast(InvoiceEvidenceOperationPortsFactory, cast(object, lambda **_kwargs: None))
    add = build_ledger_evidence_add_definition(evidence)
    listing = build_ledger_evidence_list_definition(evidence)
    extract = build_ledger_evidence_extract_definition(invoice_evidence)
    confirm = build_ledger_evidence_confirm_definition(invoice_evidence)
    definitions = (add, listing, extract, confirm)
    registrations = (
        build_ledger_evidence_add_registration(add),
        build_ledger_evidence_list_registration(listing),
        build_ledger_evidence_extract_registration(extract),
        build_ledger_evidence_confirm_registration(confirm),
    )
    registry = OperationRegistry(
        definitions=tuple(sorted(definitions, key=lambda item: item.definition_id)),
        public_registrations=tuple(sorted(registrations, key=lambda item: item.contract.definition_id)),
    )
    return {item.definition_id: registry.lookup_public_contract(item.definition_id) for item in definitions}


_CONTRACTS = _contracts()


class _Client:
    frontend = OperationFrontendProjection.TUI

    def __init__(self) -> None:
        self.profile_id = _PROFILE_ID
        self.session_id = _SESSION_ID
        self.session_read_threads: list[int] = []
        """The thread of each blocking session read: at composition, then around each operation."""


class _Controller:
    """One submitted operation that succeeds with ``result``, or refuses when ``result`` is its recorded detail."""

    operation_id = _OPERATION_ID
    # The client it was submitted through, as the real controller keeps it.
    client: _Client

    def __init__(self, request: BaseModel, *, definition_id: str, result: BaseModel, effect: OperationEffect) -> None:
        self.request = request
        self.definition_id = definition_id
        self.result = result
        self.started = False
        self.definition_contract = _CONTRACTS[definition_id]
        refused = result.error_code if isinstance(result, OperationErrorDetailV1) else None
        self.projection = SimpleNamespace(
            operation_id=self.operation_id,
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(_PROFILE_ID)),
            definition_contract=self.definition_contract,
            lifecycle=OperationLifecycle.TERMINAL,
            terminal_condition=OperationTerminalCondition.SUCCEEDED
            if refused is None
            else OperationTerminalCondition.REFUSED,
            effect=effect,
            refusal_ref=refused,
            failure_error_code=None,
            diagnostic_ref=None,
            result_ref="e" * 64 if refused is None else None,
        )

    async def start(self) -> str:
        self.started = True
        return self.operation_id

    async def observe(self, _after_cursor: int, *, page_limit: int) -> OperationObservationSuccessV1:
        assert page_limit == 1
        return OperationObservationSuccessV1.model_construct(projection=self.projection, event_page=None)

    async def read_settled_result(
        self,
        _projection: object,
        result_type: type[BaseModel],
        *,
        result_version: int,
        allow_refusal_detail: bool = False,
    ) -> BaseModel:
        assert result_version == _RESULT_VERSIONS[self.definition_id]
        assert not allow_refusal_detail
        assert type(self.result) is result_type
        return self.result

    async def settled_error_detail(self, _projection: object) -> OperationErrorDetailV1 | None:
        return self.result if isinstance(self.result, OperationErrorDetailV1) else None


def _draft_projection() -> InvoiceDraftProjectionV1:
    return InvoiceDraftProjectionV1(
        supplier_tax_id="B12345678",
        supplier_name="Proveedor Example SL",
        customer_tax_id="12345678Z",
        customer_name="Cliente Example SL",
        customer_country_code="ES",
        invoice_number="INV-01",
        invoice_series="SERIE-X",
        rectifies_invoice_number="INV-00",
        invoice_date="2026-03-16",
        proposed_supply_nature=SupplyNature.GOODS,
        taxable_base=PublicDecimal(decimal="100.00"),
        iva_rate=PublicDecimal(decimal="21"),
        iva_amount=PublicDecimal(decimal="21.00"),
        grand_total=PublicDecimal(decimal="121.00"),
        currency="EUR",
        regime_legend="REDEME special regime",
        recargo_amount=PublicDecimal(decimal="5.00"),
        retencion_rate=PublicDecimal(decimal="0.15"),
        retencion_amount=PublicDecimal(decimal="15.00"),
        suplidos_amount=PublicDecimal(decimal="3.00"),
        lines=(
            InvoiceDraftLineProjectionV1(
                description="Monitor display",
                quantity=PublicDecimal(decimal="2"),
                unit_price=PublicDecimal(decimal="50"),
                taxable_base=PublicDecimal(decimal="100.00"),
                iva_rate=PublicDecimal(decimal="21"),
                iva_amount=PublicDecimal(decimal="21.00"),
                recargo_rate=PublicDecimal(decimal="5.2"),
                recargo_amount=PublicDecimal(decimal="5.20"),
            ),
        ),
        iva_breakdown=(
            InvoiceDraftRateBreakdownProjectionV1(
                iva_rate=PublicDecimal(decimal="21"),
                taxable_base=PublicDecimal(decimal="100.00"),
                iva_amount=PublicDecimal(decimal="21.00"),
                recargo_rate=PublicDecimal(decimal="5.2"),
                recargo_amount=PublicDecimal(decimal="5.20"),
            ),
        ),
        iva_category="domestic_general",
        suggested_kind=InvoiceKind.RECEIVED,
        transcription_sha256="c" * 64,
        provenance=(
            FieldProvenanceProjectionV1(
                field="supplier_name",
                origin=FieldOrigin.VISION,
                grounding=FieldGroundingOutcome.AMBIGUOUS,
                anchor="SELLER",
                refused_anchor="CUSTOMER",
                candidates=(
                    FieldAmbiguityCandidateProjectionV1(
                        value="Proveedor Example SL",
                        anchor="SELLER: Proveedor Example SL",
                        note="labelled seller",
                    ),
                ),
                anchor_self_reported=True,
                derived_from=("invoice_number",),
                role_evidence="supplier tax identifier",
                attribution_unverified=True,
                note="check party attribution",
            ),
        ),
        discrepancies=(
            DraftDiscrepancyProjectionV1(
                kind=DraftDiscrepancyKind.ARITHMETIC_CLOSURE,
                field="grand_total",
                detail="printed total needs review",
                expected=PublicDecimal(decimal="121.00"),
                observed=PublicDecimal(decimal="120.00"),
            ),
        ),
        raw_text_length=842,
        facturae_invoice_class=StructuredInvoiceClassProjectionV1(
            source_code="F1",
            kind=StructuredInvoiceClassificationKind.CORRECTIVE,
        ),
    )


def _extract_projection() -> LedgerEvidenceExtractProjection:
    return LedgerEvidenceExtractProjection(
        profile_id=_PROFILE_ID,
        evidence_id="f" * 16,
        source_sha256=_SOURCE_DIGEST,
        draft_review_sha256=_DRAFT_DIGEST,
        consent_audit_effect=OperationEffect.NONE,
        draft=_draft_projection(),
    )


def _confirm_projection() -> LedgerEvidenceConfirmProjection:
    invoice = CatalogueInvoiceSnapshot.model_construct(
        invoice_id="c" * 64,
        bucket_id=_PROFILE_ID,
        kind=InvoiceKind.RECEIVED,
        invoice_number="INV-01",
        counterparty_country="ES",
        grand_total=PublicDecimal(decimal="121.00"),
        currency="EUR",
        source_sha256=_SOURCE_DIGEST,
    )
    confirmation = InvoiceConfirmationProjectionV1.model_construct(
        invoice=invoice,
        draft=_draft_projection(),
        created=True,
        total_discrepancy=None,
    )
    return LedgerEvidenceConfirmProjection.model_construct(
        profile_id=_PROFILE_ID,
        evidence_id="f" * 16,
        attachment_id=None,
        source_sha256=_SOURCE_DIGEST,
        reviewed_draft_sha256=_DRAFT_DIGEST,
        confirmation=confirmation,
    )


def _install_runtime(
    monkeypatch: pytest.MonkeyPatch,
    *,
    client: _Client,
    results: list[tuple[str, BaseModel, OperationEffect]],
) -> tuple[list[dict[str, object]], list[_Controller]]:
    from ....frontend.tui.operations import runtime_profile_session as bridge

    submissions: list[dict[str, object]] = []
    controllers: list[_Controller] = []

    def read_session(
        _client: FrontendClient,
        *,
        profile_id: UUID,
        session_id: UUID,
        profile_label: str,
    ) -> object:
        assert profile_label == "Fixture profile"
        client.session_read_threads.append(threading.get_ident())
        if client.profile_id != profile_id or client.session_id != session_id:
            raise AccountSessionExpiredError()
        return object()

    async def submit(
        _controller_type: type[OperationController],
        received_client: FrontendClient,
        **kwargs: object,
    ) -> _Controller:
        assert received_client is client
        assert results
        definition_id, result, effect = results.pop(0)
        assert kwargs["definition_id"] == definition_id
        request = cast(BaseModel, kwargs["payload"])
        controller = _Controller(request, definition_id=definition_id, result=result, effect=effect)
        controller.client = client
        submissions.append(kwargs)
        controllers.append(controller)
        return controller

    monkeypatch.setattr(bridge, "read_runtime_account_session", read_session)
    monkeypatch.setattr(OperationController, "submit", classmethod(submit))
    return submissions, controllers


@pytest.mark.asyncio
@pytest.mark.parametrize("substituted_source", [False, True])
async def test_runtime_evidence_add_preserves_caller_directory_and_source_provenance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    substituted_source: bool,
) -> None:
    source_path = "invoices/record.pdf"
    monkeypatch.chdir(tmp_path)
    client = _Client()
    record = LedgerEvidenceRecordProjection.model_construct(
        evidence_id="f" * 16,
        bucket_id=str(_PROFILE_ID),
        source_path="other/record.pdf" if substituted_source else source_path,
        source_sha256=_SOURCE_DIGEST,
        attachment_id=_SOURCE_DIGEST,
        media_kind=MediaKind.PDF,
        supplier=None,
        invoice_number=None,
        created_at=datetime(2026, 3, 16, tzinfo=UTC),
    )
    result = LedgerEvidenceAddProjection.model_construct(
        profile_id=_PROFILE_ID, record=record, bucket_event_ids=("c" * 64,)
    )
    submissions, controllers = _install_runtime(
        monkeypatch,
        client=client,
        results=[(LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID, result, OperationEffect.UPDATED)],
    )
    door = RuntimeEvidenceTuiDoorV1(cast(FrontendClient, client), profile_label="Fixture profile")
    if substituted_source:
        # The receipt reported the file added, so a result naming another source leaves the outcome unknown.
        with pytest.raises(OperationOutcomeUnknownError) as unknown:
            await door.add(source_path)
        assert unknown.value.operation_id == _OPERATION_ID
        assert unknown.value.effect is OperationEffect.UPDATED
        assert isinstance(unknown.value.reason, RefusalError)
        assert unknown.value.reason.reason is RefusalCode.INVALID_FRAME
    else:
        row = await door.add(source_path)
        assert row.file_name == "record.pdf"
        assert row.evidence_id == "f" * 16
        assert str(tmp_path) not in repr(row)
    request = cast(LedgerEvidenceAddRequest, submissions[0]["payload"])
    assert request.source_path == source_path
    assert Path(request.source_directory) == tmp_path
    assert request.profile_id == _PROFILE_ID
    assert submissions[0]["expected_session_id"] == _SESSION_ID
    assert controllers[0].started


@pytest.mark.asyncio
async def test_runtime_evidence_extract_and_confirm_bind_the_exact_reviewed_digests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    submissions, controllers = _install_runtime(
        monkeypatch,
        client=client,
        results=[
            (LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID, _extract_projection(), OperationEffect.NONE),
            (LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID, _confirm_projection(), OperationEffect.UPDATED),
        ],
    )
    door = RuntimeEvidenceTuiDoorV1(cast(FrontendClient, client), profile_label="Fixture profile")

    draft = await door.extract("f" * 16)

    assert draft.evidence_id == "f" * 16
    assert draft.supplier_name == "Proveedor Example SL"
    assert draft.grand_total == "121.00"
    assert draft.full_projection == _draft_projection()
    with override_settings(cadrumo_output_language="en"):
        review_text = "\n".join(draft_lines(draft))
    for fact in (
        "SERIE-X",
        "INV-00",
        "REDEME special regime",
        "0.15",
        "Monitor display",
        "5.20",
        "printed total needs review",
        "SELLER: Proveedor Example SL",
        "supplier tax identifier",
        "F1",
        "842",
    ):
        assert fact in review_text
    extract_request = cast(LedgerEvidenceExtractRequest, submissions[0]["payload"])
    assert extract_request == LedgerEvidenceExtractRequest(profile_id=_PROFILE_ID, evidence_id="f" * 16)
    assert submissions[0]["definition_id"] == LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID
    assert submissions[0]["subject_ref"] == profile_operation_subject(str(_PROFILE_ID))
    assert submissions[0]["expected_session_id"] == _SESSION_ID
    assert controllers[0].started

    confirmed = await door.confirm(
        LedgerEvidenceConfirmationV1(
            evidence_id="f" * 16,
            kind=InvoiceKind.RECEIVED,
            country_code="ES",
            counterparty_name="Proveedor Example SL",
        )
    )

    assert confirmed.invoice_id == "c" * 64
    assert confirmed.invoice_number == "INV-01"
    assert confirmed.grand_total == Decimal("121.00")
    confirm_request = cast(LedgerEvidenceConfirmRequest, submissions[1]["payload"])
    assert confirm_request.expected_source_sha256 == _SOURCE_DIGEST
    assert confirm_request.expected_draft_review_sha256 == _DRAFT_DIGEST
    assert confirm_request.evidence_id == "f" * 16
    assert confirm_request.counterparty_name == "Proveedor Example SL"
    assert submissions[1]["definition_id"] == LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID
    assert controllers[1].started

    with pytest.raises(RefusalError) as refused:
        await door.confirm(
            LedgerEvidenceConfirmationV1(
                evidence_id="f" * 16,
                kind=InvoiceKind.RECEIVED,
                country_code="ES",
            )
        )
    assert refused.value.reason is RefusalCode.INVALID_FRAME
    assert len(submissions) == 2


@pytest.mark.asyncio
async def test_runtime_evidence_clears_a_review_when_its_session_is_replaced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    submissions, _controllers = _install_runtime(
        monkeypatch,
        client=client,
        results=[(LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID, _extract_projection(), OperationEffect.NONE)],
    )
    door = RuntimeEvidenceTuiDoorV1(cast(FrontendClient, client), profile_label="Fixture profile")
    await door.extract("f" * 16)
    client.session_id = UUID("7cc00000-0000-4000-8000-0000000000cc")

    with pytest.raises(AccountSessionExpiredError):
        await door.confirm(
            LedgerEvidenceConfirmationV1(
                evidence_id="f" * 16,
                kind=InvoiceKind.RECEIVED,
                country_code="ES",
            )
        )

    assert len(submissions) == 1


def test_runtime_evidence_maps_complete_list_to_unmeasured_safe_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _Client()
    record = LedgerEvidenceRecordProjection.model_construct(
        evidence_id="f" * 16,
        bucket_id=str(_PROFILE_ID),
        source_path="C:/private/invoices/record.pdf",
        source_sha256=_SOURCE_DIGEST,
        attachment_id=_SOURCE_DIGEST,
        media_kind=MediaKind.PDF,
        supplier="Proveedor Example SL",
        invoice_number="INV-01",
        invoice_date="2026-03-16",
        taxable_base="100",
        iva_rate="21",
        iva_amount="21",
        notes="private detail",
        created_at=datetime(2026, 3, 16, tzinfo=UTC),
        updated_at=datetime(2026, 3, 16, tzinfo=UTC),
    )
    result = LedgerEvidenceListProjection.model_construct(profile_id=_PROFILE_ID, count=1, rows=(record,))
    _install_runtime(
        monkeypatch,
        client=client,
        results=[(LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID, result, OperationEffect.NONE)],
    )
    door = RuntimeEvidenceTuiDoorV1(cast(FrontendClient, client), profile_label="Fixture profile")

    rows = door.list_records()

    assert len(rows) == 1
    assert rows[0].file_name == "record.pdf"
    assert rows[0].status is LedgerEvidenceRecordStatus.UNMEASURED
    assert rows[0].evidence_id == "f" * 16
    assert "private" not in repr(rows[0])


def _confirmation() -> LedgerEvidenceConfirmationV1:
    return LedgerEvidenceConfirmationV1(
        evidence_id="f" * 16,
        kind=InvoiceKind.RECEIVED,
        country_code="ES",
        counterparty_name="Proveedor Example SL",
    )


def _added_record() -> LedgerEvidenceAddProjection:
    record = LedgerEvidenceRecordProjection.model_construct(
        evidence_id="f" * 16,
        bucket_id=str(_PROFILE_ID),
        source_path="record.pdf",
        source_sha256=_SOURCE_DIGEST,
        attachment_id=_SOURCE_DIGEST,
        media_kind=MediaKind.PDF,
        supplier=None,
        invoice_number=None,
        created_at=datetime(2026, 3, 16, tzinfo=UTC),
    )
    return LedgerEvidenceAddProjection.model_construct(
        profile_id=_PROFILE_ID, record=record, bucket_event_ids=("c" * 64,)
    )


@pytest.mark.asyncio
async def test_runtime_evidence_doors_read_their_session_off_the_event_loop_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The session read is a blocking IPC exchange; extract, confirm and add never run it on the loop."""
    client = _Client()
    _install_runtime(
        monkeypatch,
        client=client,
        results=[
            (LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID, _extract_projection(), OperationEffect.NONE),
            (LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID, _confirm_projection(), OperationEffect.UPDATED),
            (LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID, _added_record(), OperationEffect.UPDATED),
        ],
    )
    door = RuntimeEvidenceTuiDoorV1(cast(FrontendClient, client), profile_label="Fixture profile")
    assert client.session_read_threads, "composing the door reads the session once, before any loop runs"
    loop_thread = threading.get_ident()

    for call in (
        lambda: door.extract("f" * 16),
        lambda: door.confirm(_confirmation()),
        lambda: door.add("record.pdf"),
    ):
        client.session_read_threads.clear()
        await call()
        assert client.session_read_threads, "a door reads its session around its operation"
        assert loop_thread not in client.session_read_threads


@pytest.mark.asyncio
async def test_the_evidence_gate_catches_a_session_read_on_the_loop_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detector teeth: a binding check called directly on the loop thread is recorded there."""
    client = _Client()
    _install_runtime(monkeypatch, client=client, results=[])
    door = RuntimeEvidenceTuiDoorV1(cast(FrontendClient, client), profile_label="Fixture profile")
    client.session_read_threads.clear()

    door._session.require_binding()

    assert client.session_read_threads == [threading.get_ident()]


@pytest.mark.asyncio
async def test_a_confirmation_whose_result_disagrees_with_its_updated_receipt_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The receipt reported the invoice confirmed; a result for another source cannot unsay it."""
    client = _Client()
    mismatched = _confirm_projection().model_copy(update={"source_sha256": "9" * 64})
    _install_runtime(
        monkeypatch,
        client=client,
        results=[
            (LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID, _extract_projection(), OperationEffect.NONE),
            (LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID, mismatched, OperationEffect.UPDATED),
        ],
    )
    door = RuntimeEvidenceTuiDoorV1(cast(FrontendClient, client), profile_label="Fixture profile")
    await door.extract("f" * 16)

    with pytest.raises(OperationOutcomeUnknownError) as raised:
        await door.confirm(_confirmation())

    assert raised.value.operation_id == _OPERATION_ID
    assert raised.value.effect is OperationEffect.UPDATED
    assert isinstance(raised.value.reason, RefusalError)
    assert raised.value.reason.reason is RefusalCode.INVALID_FRAME


@pytest.mark.asyncio
async def test_an_extraction_whose_result_disagrees_with_a_receipt_that_saved_nothing_stays_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client()
    other = _extract_projection().model_copy(update={"evidence_id": "e" * 16})
    _install_runtime(
        monkeypatch,
        client=client,
        results=[(LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID, other, OperationEffect.NONE)],
    )
    door = RuntimeEvidenceTuiDoorV1(cast(FrontendClient, client), profile_label="Fixture profile")

    with pytest.raises(RefusalError) as raised:
        await door.extract("f" * 16)

    assert not isinstance(raised.value, OperationOutcomeUnknownError)
    assert raised.value.reason is RefusalCode.INVALID_FRAME


@pytest.mark.asyncio
async def test_a_refused_extraction_raises_its_recorded_reason_with_the_verdict_naming_the_local_ai_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The recorded detail is the one the real program probe's refusal publishes, read back as another process reads it."""
    status = probe_local_ai_program(recorded_absent_row("local_ai"))
    verdict = status.precondition_verdict
    assert verdict is not None
    detail = build_operation_error_detail(
        PurchaseInvoiceEvidenceReaderError(
            translated_message=evidence_reader_refusal_key(verdict), precondition_verdict=verdict
        )
    )
    assert detail is not None
    client = _Client()
    _install_runtime(
        monkeypatch,
        client=client,
        results=[(LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID, detail, OperationEffect.NONE)],
    )
    door = RuntimeEvidenceTuiDoorV1(cast(FrontendClient, client), profile_label="Fixture profile")

    with pytest.raises(RecordedRegisteredError) as raised:
        await door.extract("f" * 16)

    assert raised.value.recorded_code == detail.error_code
    assert raised.value.translated_message == EVIDENCE_LOCAL_AI_NOT_READY_LOCALE_KEY
    assert resolve_error_message(raised.value, locale="en") == (
        "Local AI is not ready, so nothing was read. Set it up in the Cadrumo desktop app, then try again."
    )
    restored = nested_terminal_precondition_verdict(raised.value)
    assert restored == verdict
    assert restored is not None
    assert restored.action is not None
    assert restored.action.action_id == LOCAL_AI_PROVISION_ACTION_ID
