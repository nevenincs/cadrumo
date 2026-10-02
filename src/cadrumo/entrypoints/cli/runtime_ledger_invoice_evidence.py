"""Authenticated CLI transport for registered invoice evidence operations."""

from __future__ import annotations

from typing import Never
from uuid import UUID

import typer
from pydantic import BaseModel

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.ledger.invoice_evidence_operation import (
    LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
    LedgerEvidenceConfirmProjection,
    LedgerEvidenceConfirmRequest,
    LedgerEvidenceExtractProjection,
    LedgerEvidenceExtractRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .common import active_bucket_id_or_refuse
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


def _client(ctx: typer.Context, profile_id: UUID) -> RuntimeFrontendClient:
    """Return only the runtime client bound to the immutable active profile."""
    expected_profile_id = UUID(active_bucket_id_or_refuse())
    if profile_id != expected_profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return require_profile_client(ctx, expected_profile_id=expected_profile_id)


def _invalid[ProjectionT: BaseModel](completed: RegisteredOperationCompletion[ProjectionT]) -> Never:
    raise submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


def _submit[ProjectionT: BaseModel](
    ctx: typer.Context,
    request: BaseModel,
    *,
    definition_id: str,
    result_type: type[ProjectionT],
) -> RegisteredOperationCompletion[ProjectionT]:
    """Submit one request through the exact profile-bound runtime frontend."""
    profile_id = getattr(request, "profile_id", None)
    if not isinstance(profile_id, UUID):
        raise RuntimeError("invoice evidence request has no typed profile identity")
    client = _client(ctx, profile_id)
    return run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=result_type,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )


def submit_invoice_evidence_extract(
    ctx: typer.Context,
    request: LedgerEvidenceExtractRequest,
) -> RegisteredOperationCompletion[LedgerEvidenceExtractProjection]:
    """Submit an extraction and correlate its consent/source projection to the receipt."""
    completed = _submit(
        ctx,
        request,
        definition_id=LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
        result_type=LedgerEvidenceExtractProjection,
    )
    projection = completed.projection
    if (
        projection.profile_id != request.profile_id
        or projection.evidence_id != request.evidence_id
        or projection.attachment_id != request.attachment_id
        or projection.off_host_provider is not request.off_host_provider
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not projection.consent_audit_effect
        or completed.refusal_code is not None
        or projection.consent_audit_effect not in {OperationEffect.NONE, OperationEffect.UPDATED}
    ):
        _invalid(completed)
    return completed


def submit_invoice_evidence_confirm(
    ctx: typer.Context,
    request: LedgerEvidenceConfirmRequest,
) -> RegisteredOperationCompletion[LedgerEvidenceConfirmProjection]:
    """Submit one reviewed confirmation and bind readback to both supplied digests."""
    completed = _submit(
        ctx,
        request,
        definition_id=LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
        result_type=LedgerEvidenceConfirmProjection,
    )
    projection = completed.projection
    if (
        projection.profile_id != request.profile_id
        or projection.evidence_id != request.evidence_id
        or projection.attachment_id != request.attachment_id
        or projection.source_sha256 != request.expected_source_sha256
        or projection.reviewed_draft_sha256 != request.expected_draft_review_sha256
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.UPDATED
        or completed.refusal_code is not None
    ):
        _invalid(completed)
    return completed


__all__ = ["submit_invoice_evidence_confirm", "submit_invoice_evidence_extract"]
