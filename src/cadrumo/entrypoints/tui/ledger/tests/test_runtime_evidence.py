"""TUI evidence operations remain bound to the reviewed source and receipt."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot
from cadrumo.application.ledger.evidence import MediaKind
from cadrumo.application.ledger.evidence_add_operation import (
    LEDGER_EVIDENCE_ADD_OPERATION_DEFINITION_ID,
    LedgerEvidenceAddProjection,
    LedgerEvidenceAddRequest,
)
from cadrumo.application.ledger.evidence_read_operation import (
    LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID,
    LedgerEvidenceListProjection,
    LedgerEvidenceRecordProjection,
)
from cadrumo.application.ledger.invoice_evidence_confirm_operation import (
    LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
    LedgerEvidenceConfirmProjection,
    LedgerEvidenceConfirmRequest,
)
from cadrumo.application.ledger.invoice_evidence_extract_operation import (
    LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
    LedgerEvidenceExtractProjection,
    LedgerEvidenceExtractRequest,
)
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
from cadrumo.application.operations.frontend_requests import OperationObservationSuccessV1
from cadrumo.application.operations.public_scalar import PublicDecimal
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.core.config import override_settings
from cadrumo.core.draft_discrepancy import DraftDiscrepancyKind
from cadrumo.core.field_grounding import FieldGroundingOutcome
from cadrumo.core.field_origin import FieldOrigin
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.domain.iva.supply_nature import SupplyNature
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo.entrypoints.tui.ledger.evidence_draft import draft_lines
from cadrumo.entrypoints.tui.ledger.models import LedgerEvidenceConfirmationV1, LedgerEvidenceRecordStatus
from cadrumo.entrypoints.tui.ledger.runtime_evidence import RuntimeEvidenceTuiDoorV1
from cadrumo.entrypoints.tui.operations.runtime_controller import RuntimeOperationController

from .....application.operations.schema_identity import OperationSchemaIdentityV1

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
    LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID: 2,
    LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID: 2,
}


class _Client:
    frontend = OperationFrontendProjection.TUI

    def __init__(self) -> None:
        self.profile_id = _PROFILE_ID
        self.session_id = _SESSION_ID


class _Controller:
    operation_id = _OPERATION_ID

    def __init__(self, request: BaseModel, *, definition_id: str, result: BaseModel, effect: OperationEffect) -> None:
        self.request = request
        self.definition_id = definition_id
        self.result = result
        self.started = False
        request_schema = OperationSchemaIdentityV1.from_model(
            schema_id=f"{definition_id}.request",
            schema_version=1,
            model_type=type(request),
        )
        self.projection = SimpleNamespace(
            operation_id=self.operation_id,
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(_PROFILE_ID)),
            definition_contract=SimpleNamespace(request_schema=request_schema),
            lifecycle=OperationLifecycle.TERMINAL,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=effect,
            refusal_ref=None,
            failure_error_code=None,
            diagnostic_ref=None,
            result_ref="e" * 64,
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
    from cadrumo.entrypoints.tui.operations import runtime_profile_session as bridge

    submissions: list[dict[str, object]] = []
    controllers: list[_Controller] = []

    def read_session(
        _client: RuntimeFrontendClient,
        *,
        profile_id: UUID,
        session_id: UUID,
        profile_label: str,
    ) -> object:
        assert profile_label == "Fixture profile"
        if client.profile_id != profile_id or client.session_id != session_id:
            raise AccountSessionExpiredError()
        return object()

    async def submit(
        _controller_type: type[RuntimeOperationController],
        received_client: RuntimeFrontendClient,
        **kwargs: object,
    ) -> _Controller:
        assert received_client is client
        assert results
        definition_id, result, effect = results.pop(0)
        assert kwargs["definition_id"] == definition_id
        request = cast(BaseModel, kwargs["payload"])
        controller = _Controller(request, definition_id=definition_id, result=result, effect=effect)
        submissions.append(kwargs)
        controllers.append(controller)
        return controller

    monkeypatch.setattr(bridge, "read_runtime_account_session", read_session)
    monkeypatch.setattr(RuntimeOperationController, "submit", classmethod(submit))
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
    door = RuntimeEvidenceTuiDoorV1(cast(RuntimeFrontendClient, client), profile_label="Fixture profile")
    if substituted_source:
        with pytest.raises(RuntimeRefusalError) as refused:
            await door.add(source_path)
        assert refused.value.reason is RuntimeRefusalCode.INVALID_FRAME
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
    door = RuntimeEvidenceTuiDoorV1(cast(RuntimeFrontendClient, client), profile_label="Fixture profile")

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

    with pytest.raises(RuntimeRefusalError) as refused:
        await door.confirm(
            LedgerEvidenceConfirmationV1(
                evidence_id="f" * 16,
                kind=InvoiceKind.RECEIVED,
                country_code="ES",
            )
        )
    assert refused.value.reason is RuntimeRefusalCode.INVALID_FRAME
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
    door = RuntimeEvidenceTuiDoorV1(cast(RuntimeFrontendClient, client), profile_label="Fixture profile")
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
    door = RuntimeEvidenceTuiDoorV1(cast(RuntimeFrontendClient, client), profile_label="Fixture profile")

    rows = door.list_records()

    assert len(rows) == 1
    assert rows[0].file_name == "record.pdf"
    assert rows[0].status is LedgerEvidenceRecordStatus.UNMEASURED
    assert rows[0].evidence_id == "f" * 16
    assert "private" not in repr(rows[0])
