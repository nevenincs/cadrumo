"""Registered runtime bridges retain complete evidence follow-up read DTOs."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer
from pydantic import BaseModel

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.ledger.attachment_review import AttachmentReviewItem
from ....application.ledger.evidence_followup_contracts import (
    LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
    CloudDerivedArtefactProjection,
    ConsentedDispatchProjection,
    ConsentWithdrawalSurveyProjection,
    EvidenceReviewQueueRowProjection,
    LedgerEvidenceAttachmentQueueProjection,
    LedgerEvidenceAttachmentQueueRequest,
    LedgerEvidenceAttachmentViewProjection,
    LedgerEvidenceAttachmentViewRequest,
    LedgerEvidenceConsentListProjection,
    LedgerEvidenceConsentListRequest,
    LedgerEvidenceReviewListProjection,
    LedgerEvidenceReviewListRequest,
    LedgerEvidenceReviewViewProjection,
    LedgerEvidenceReviewViewRequest,
)
from ....application.ledger.invoice_draft_records import InvoiceDraft
from ....application.ledger.invoice_evidence_operation_dtos import InvoiceDraftProjectionV1
from ....application.operations.models import OperationId
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.attachments.enums import AttachmentSource
from .. import runtime_ledger_evidence_followup as bridge
from ..errors import CliRefusedBoundaryError
from ..ledger_business_payloads import (
    AttachmentReviewQueueResult,
    AttachmentReviewViewResult,
    EvidenceConsentListResult,
    EvidenceReviewListResult,
)
from ..registered_operation_contracts import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")
_ATTACHMENT_ID = "a" * 64
_EVIDENCE_REFERENCE = "evidence-followup-reference"
_OPERATION_ID = "f" * 64
_DRIVE_FILE_ID = "1AbcDEfgHIjkLMnoPQRstuVWxyz12345"
_CAPTURED_AT = datetime(2026, 9, 30, 11, 30, tzinfo=UTC)
#: The review view carries the stored label-reading fallback beside its draft,
#: so it alone reads the second result schema.
_RESULT_VERSIONS = {
    LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID: 1,
    LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID: 1,
    LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID: 1,
    LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID: 1,
    LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID: 2,
}


def _attachment() -> AttachmentReviewItem:
    return AttachmentReviewItem(
        attachment_id=_ATTACHMENT_ID,
        sha256=_ATTACHMENT_ID,
        mime_type="application/xml",
        bytes_size=64,
        source=AttachmentSource.GOOGLE_DRIVE,
        provider_locator=_DRIVE_FILE_ID,
        captured_at=_CAPTURED_AT.isoformat(),
        linked_invoice_ids=(),
        pending_review=True,
    )


def _projection(definition_id: str, *, profile_id: UUID) -> BaseModel:
    if definition_id == LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID:
        return LedgerEvidenceAttachmentQueueProjection(profile_id=profile_id, count=1, rows=(_attachment(),))
    if definition_id == LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID:
        return LedgerEvidenceAttachmentViewProjection(profile_id=profile_id, item=_attachment())
    if definition_id == LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID:
        return LedgerEvidenceConsentListProjection(
            profile_id=profile_id,
            survey=ConsentWithdrawalSurveyProjection(
                consented_dispatches=(
                    ConsentedDispatchProjection(
                        profile_bucket_id=str(profile_id),
                        evidence_content_address="b" * 64,
                        provider="openai",
                        model="fixture-model",
                        surface="app.ledger.evidence.extract",
                        recorded_at=_CAPTURED_AT,
                    ),
                ),
                cloud_derived_artefacts=(
                    CloudDerivedArtefactProjection(
                        evidence_reference=_EVIDENCE_REFERENCE,
                        provenance_stamp="fixture-reader",
                        transport="openai",
                        drafted_at=_CAPTURED_AT,
                    ),
                ),
            ),
        )
    if definition_id == LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID:
        return LedgerEvidenceReviewListProjection(
            profile_id=profile_id,
            rows=(
                EvidenceReviewQueueRowProjection(
                    evidence_reference=_EVIDENCE_REFERENCE,
                    extractor="fixture-reader",
                    drafted_at=_CAPTURED_AT,
                    blocking_count=0,
                    advisory_count=0,
                ),
            ),
        )
    if definition_id == LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID:
        return LedgerEvidenceReviewViewProjection(
            profile_id=profile_id,
            evidence_reference=_EVIDENCE_REFERENCE,
            extractor="fixture-reader",
            drafted_at=_CAPTURED_AT,
            draft=InvoiceDraftProjectionV1.from_draft(InvoiceDraft()),
        )
    raise AssertionError(definition_id)


def _request(definition_id: str) -> BaseModel:
    if definition_id == LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID:
        return LedgerEvidenceAttachmentQueueRequest(profile_id=_PROFILE)
    if definition_id == LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID:
        return LedgerEvidenceAttachmentViewRequest(profile_id=_PROFILE, attachment_id=_ATTACHMENT_ID)
    if definition_id == LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID:
        return LedgerEvidenceConsentListRequest(profile_id=_PROFILE)
    if definition_id == LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID:
        return LedgerEvidenceReviewListRequest(profile_id=_PROFILE)
    if definition_id == LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID:
        return LedgerEvidenceReviewViewRequest(profile_id=_PROFILE, evidence_reference=_EVIDENCE_REFERENCE)
    raise AssertionError(definition_id)


def _invoke(ctx: typer.Context, definition_id: str) -> BaseModel:
    if definition_id == LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID:
        return bridge.run_ledger_evidence_attachment_queue(ctx)
    if definition_id == LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID:
        return bridge.run_ledger_evidence_attachment_view(ctx, attachment_id=_ATTACHMENT_ID)
    if definition_id == LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID:
        return bridge.run_ledger_evidence_consent_list(ctx)
    if definition_id == LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID:
        return bridge.run_ledger_evidence_review_list(ctx)
    if definition_id == LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID:
        return bridge.run_ledger_evidence_review_view(ctx, evidence_reference=_EVIDENCE_REFERENCE)
    raise AssertionError(definition_id)


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    *,
    definition_id: str,
    profile_id: UUID,
    projection: BaseModel,
    submitted: list[BaseModel],
) -> None:
    client = cast(RuntimeFrontendClient, SimpleNamespace(profile_id=profile_id))
    monkeypatch.setattr(bridge, "active_bucket_id_or_refuse", lambda: str(profile_id))

    def bound_client(_ctx: typer.Context, *, expected_profile_id: UUID) -> RuntimeFrontendClient:
        assert expected_profile_id == profile_id
        return client

    monkeypatch.setattr(bridge, "require_profile_client", bound_client)

    def submit(
        actual_client: RuntimeFrontendClient,
        request: BaseModel,
        **kwargs: object,
    ) -> RegisteredOperationCompletion[BaseModel]:
        submitted.append(request)
        assert actual_client is client
        assert kwargs["definition_id"] == definition_id
        assert kwargs["subject_ref"] == profile_operation_subject(str(profile_id))
        assert kwargs["result_type"] is type(projection)
        assert kwargs["request_version"] == 1
        assert kwargs["result_version"] == _RESULT_VERSIONS[definition_id]
        assert kwargs["timeout"] == 120
        return RegisteredOperationCompletion(
            operation_id=cast("OperationId", _OPERATION_ID),
            projection=projection,
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)


@pytest.mark.parametrize(
    ("definition_id", "result_type"),
    [
        (LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID, AttachmentReviewQueueResult),
        (LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID, AttachmentReviewViewResult),
        (LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID, EvidenceConsentListResult),
        (LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID, EvidenceReviewListResult),
        (LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID, LedgerEvidenceReviewViewProjection),
    ],
)
def test_each_bridge_submits_its_exact_profile_request_and_preserves_complete_result(
    monkeypatch: pytest.MonkeyPatch,
    definition_id: str,
    result_type: type[BaseModel],
) -> None:
    projection = _projection(definition_id, profile_id=_PROFILE)
    submitted: list[BaseModel] = []
    _bind(
        monkeypatch,
        definition_id=definition_id,
        profile_id=_PROFILE,
        projection=projection,
        submitted=submitted,
    )

    result = _invoke(cast(typer.Context, cast(object, None)), definition_id)

    assert submitted == [_request(definition_id)]
    assert isinstance(result, result_type)
    if isinstance(result, AttachmentReviewQueueResult):
        assert result.count == 1
        assert result.rows[0].sha256 == _ATTACHMENT_ID
    elif isinstance(result, AttachmentReviewViewResult):
        assert result.attachment_id == _ATTACHMENT_ID
        assert result.provider_locator == _DRIVE_FILE_ID
    elif isinstance(result, EvidenceConsentListResult):
        assert result.transmitted_bytes_are_unrecallable is True
        assert result.consented_dispatches[0].evidence_content_address == "b" * 64
        assert result.cloud_derived_artefacts[0].transport == "openai"
    elif isinstance(result, EvidenceReviewListResult):
        assert result.rows[0].evidence_reference == _EVIDENCE_REFERENCE
    else:
        assert isinstance(result, LedgerEvidenceReviewViewProjection)
        assert isinstance(projection, LedgerEvidenceReviewViewProjection)
        assert result.evidence_reference == _EVIDENCE_REFERENCE
        assert result.draft == projection.draft


@pytest.mark.parametrize(
    "definition_id",
    [
        LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
        LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
        LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
        LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
        LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
    ],
)
def test_each_bridge_refuses_a_foreign_profile_projection_with_the_submitted_receipt(
    monkeypatch: pytest.MonkeyPatch,
    definition_id: str,
) -> None:
    projection = _projection(definition_id, profile_id=_OTHER_PROFILE)
    submitted: list[BaseModel] = []
    _bind(
        monkeypatch,
        definition_id=definition_id,
        profile_id=_PROFILE,
        projection=projection,
        submitted=submitted,
    )

    with pytest.raises(CliRefusedBoundaryError) as refused:
        _invoke(cast(typer.Context, cast(object, None)), definition_id)

    assert submitted == [_request(definition_id)]
    assert refused.value.context == {
        "operation_id": _OPERATION_ID,
        "reason": RuntimeRefusalCode.INVALID_FRAME.value,
        "effect": OperationEffect.NONE.value,
        "terminal_condition": "succeeded",
    }
