"""Authenticated CLI transport for registered invoice-evidence follow-up reads."""

from __future__ import annotations

from uuid import UUID

import typer
from pydantic import BaseModel

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.ledger.evidence_followup_contracts import (
    LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
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
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.confirmation_gate import ConfirmationBlockReason, ReviewAdvisoryKind
from ...core.draft_discrepancy import DraftDiscrepancyKind
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .common import active_bucket_id_or_refuse
from .ledger_business_payloads import (
    AttachmentReviewQueueResult,
    AttachmentReviewViewResult,
    EvidenceConsentListResult,
    EvidenceReviewListResult,
)
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


def _client(ctx: typer.Context) -> RuntimeFrontendClient:
    """Return only the runtime client bound to the immutable active profile."""
    expected_profile_id = UUID(active_bucket_id_or_refuse())
    return require_profile_client(ctx, expected_profile_id=expected_profile_id)


def _submit[ProjectionT: BaseModel](
    ctx: typer.Context,
    request: BaseModel,
    *,
    definition_id: str,
    result_type: type[ProjectionT],
    result_version: int,
) -> RegisteredOperationCompletion[ProjectionT]:
    """Submit one request through the exact active-profile runtime frontend."""
    profile_id = getattr(request, "profile_id", None)
    if not isinstance(profile_id, UUID):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    client = _client(ctx)
    if client.profile_id != profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=result_type,
        request_version=1,
        result_version=result_version,
        timeout=120,
    )


def _require_success[ProjectionT: BaseModel](
    completed: RegisteredOperationCompletion[ProjectionT],
    *,
    profile_id: UUID,
) -> ProjectionT:
    """Correlate the complete projection with its operation receipt."""
    projection = completed.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or getattr(projection, "profile_id", None) != profile_id
    ):
        raise invalid_completion_error(completed)
    # `_submit` binds the definition and exact subject; run_registered_operation
    # checks them against the runtime contract and terminal observation before
    # creating this completion.
    return projection


def run_ledger_evidence_attachment_queue(ctx: typer.Context) -> AttachmentReviewQueueResult:
    """List the active profile's review-safe pending attachment metadata."""
    client = _client(ctx)
    completed = _submit(
        ctx,
        LedgerEvidenceAttachmentQueueRequest(profile_id=client.profile_id),
        definition_id=LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
        result_type=LedgerEvidenceAttachmentQueueProjection,
        result_version=1,
    )
    projection = _require_success(
        completed,
        profile_id=client.profile_id,
    )
    if projection.count != len(projection.rows) or any(not row.pending_review for row in projection.rows):
        raise invalid_completion_error(completed)
    return AttachmentReviewQueueResult.model_validate(
        {
            "bucket_id": str(client.profile_id),
            "count": projection.count,
            "rows": [row.model_dump(mode="json") for row in projection.rows],
        }
    )


def run_ledger_evidence_attachment_view(
    ctx: typer.Context,
    *,
    attachment_id: str,
) -> AttachmentReviewViewResult:
    """View one exact attachment's non-secret manifest facts."""
    client = _client(ctx)
    request = LedgerEvidenceAttachmentViewRequest(profile_id=client.profile_id, attachment_id=attachment_id)
    completed = _submit(
        ctx,
        request,
        definition_id=LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
        result_type=LedgerEvidenceAttachmentViewProjection,
        result_version=1,
    )
    projection = _require_success(
        completed,
        profile_id=client.profile_id,
    )
    if projection.item.attachment_id != attachment_id:
        raise invalid_completion_error(completed)
    return AttachmentReviewViewResult.model_validate(
        {"bucket_id": str(client.profile_id), **projection.item.model_dump(mode="json")}
    )


def run_ledger_evidence_consent_list(ctx: typer.Context) -> EvidenceConsentListResult:
    """Read the consent survey for the exact active profile."""
    client = _client(ctx)
    completed = _submit(
        ctx,
        LedgerEvidenceConsentListRequest(profile_id=client.profile_id),
        definition_id=LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
        result_type=LedgerEvidenceConsentListProjection,
        result_version=1,
    )
    projection = _require_success(
        completed,
        profile_id=client.profile_id,
    )
    survey = projection.survey
    if any(row.profile_bucket_id != str(client.profile_id) for row in survey.consented_dispatches):
        raise invalid_completion_error(completed)
    return EvidenceConsentListResult.model_validate(
        {
            "bucket_id": str(client.profile_id),
            "transmitted_bytes_are_unrecallable": survey.transmitted_bytes_are_unrecallable,
            "consented_dispatches": [
                row.model_dump(mode="json", exclude={"profile_bucket_id"}) for row in survey.consented_dispatches
            ],
            "cloud_derived_artefacts": [row.model_dump(mode="json") for row in survey.cloud_derived_artefacts],
        }
    )


def run_ledger_evidence_review_list(
    ctx: typer.Context,
    *,
    reason: ConfirmationBlockReason | None = None,
    finding: DraftDiscrepancyKind | None = None,
    advisory: ReviewAdvisoryKind | None = None,
    blocking_only: bool = False,
) -> EvidenceReviewListResult:
    """Read the active profile's complete queue after applying typed filters."""
    client = _client(ctx)
    request = LedgerEvidenceReviewListRequest(
        profile_id=client.profile_id,
        reason=reason,
        finding=finding,
        advisory=advisory,
        blocking_only=blocking_only,
    )
    completed = _submit(
        ctx,
        request,
        definition_id=LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
        result_type=LedgerEvidenceReviewListProjection,
        result_version=1,
    )
    projection = _require_success(
        completed,
        profile_id=client.profile_id,
    )
    if tuple(row.evidence_reference for row in projection.rows) != tuple(
        sorted({row.evidence_reference for row in projection.rows})
    ):
        raise invalid_completion_error(completed)
    return EvidenceReviewListResult.model_validate(
        {
            "bucket_id": str(client.profile_id),
            "filters": list(projection.filters),
            "rows": [row.model_dump(mode="json") for row in projection.rows],
        }
    )


def run_ledger_evidence_review_view(
    ctx: typer.Context,
    *,
    evidence_reference: str,
) -> LedgerEvidenceReviewViewProjection:
    """Read one exact pending draft, preserving its full closed DTO projection."""
    client = _client(ctx)
    completed = _submit(
        ctx,
        LedgerEvidenceReviewViewRequest(profile_id=client.profile_id, evidence_reference=evidence_reference),
        definition_id=LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
        result_type=LedgerEvidenceReviewViewProjection,
        result_version=2,
    )
    projection = _require_success(
        completed,
        profile_id=client.profile_id,
    )
    if projection.evidence_reference != evidence_reference:
        raise invalid_completion_error(completed)
    return projection


__all__ = [
    "run_ledger_evidence_attachment_queue",
    "run_ledger_evidence_attachment_view",
    "run_ledger_evidence_consent_list",
    "run_ledger_evidence_review_list",
    "run_ledger_evidence_review_view",
]
