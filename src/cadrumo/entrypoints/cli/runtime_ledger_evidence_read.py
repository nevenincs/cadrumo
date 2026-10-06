"""CLI transport bridge for worker-owned purchase-invoice evidence reads."""

from __future__ import annotations

from uuid import UUID

import typer

from ...application.ledger.evidence_errors import PurchaseInvoiceEvidenceNotFoundError
from ...application.ledger.evidence_read_operation import (
    LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_VIEW_NOT_FOUND_REFUSAL_CODE,
    LEDGER_EVIDENCE_VIEW_OPERATION_DEFINITION_ID,
    LedgerEvidenceListProjection,
    LedgerEvidenceListRequest,
    LedgerEvidenceViewProjection,
    LedgerEvidenceViewRefusal,
    LedgerEvidenceViewRequest,
)
from ...application.ledger.preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .ledger_business_payloads import EvidenceListResult, EvidenceViewResult
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation


def run_ledger_evidence_list(ctx: typer.Context) -> EvidenceListResult:
    """Read and correlate the complete evidence list for the bound profile."""
    client = bound_profile_client(ctx)
    completed = run_registered_operation(
        client,
        LedgerEvidenceListRequest(profile_id=client.profile_id),
        definition_id=LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerEvidenceListProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    profile_id = str(client.profile_id)
    invalid = _evidence_list_receipt_invalid(completed, projection, client.profile_id, profile_id)
    if invalid:
        raise invalid_completion_error(completed)
    return EvidenceListResult.model_validate(
        {
            "bucket_id": profile_id,
            "count": projection.count,
            "rows": [row.model_dump(mode="json") for row in projection.rows],
        }
    )


def run_ledger_evidence_view(ctx: typer.Context, *, evidence_id: str) -> EvidenceViewResult:
    """Read and correlate one exact evidence identity for the bound profile."""
    client = bound_profile_client(ctx)
    completed = run_registered_operation(
        client,
        LedgerEvidenceViewRequest(profile_id=client.profile_id, evidence_id=evidence_id),
        definition_id=LEDGER_EVIDENCE_VIEW_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerEvidenceViewProjection,
        request_version=1,
        result_version=2,
        timeout=120,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    outcome = projection.outcome
    if isinstance(outcome, LedgerEvidenceViewRefusal):
        if (
            projection.profile_id != client.profile_id
            or completed.terminal_condition is not OperationTerminalCondition.REFUSED
            or completed.refusal_code != LEDGER_EVIDENCE_VIEW_NOT_FOUND_REFUSAL_CODE
            or completed.effect is not OperationEffect.NONE
        ):
            raise invalid_completion_error(completed)
        raise PurchaseInvoiceEvidenceNotFoundError(
            translated_message="errors.refused.refused_ledger_evidence_not_found",
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.EVIDENCE_REFERENCE_RESOLVES,
                facts={"evidence_record_present": outcome.evidence_record_present},
            ),
            context={
                "operation_id": str(completed.operation_id),
                "refusal_code": completed.refusal_code,
                "terminal_condition": completed.terminal_condition.value,
                "effect": completed.effect.value,
            },
        )
    invalid = (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.NONE
        or projection.profile_id != client.profile_id
        or outcome.record.bucket_id != str(client.profile_id)
        or outcome.record.evidence_id != evidence_id
    )
    if invalid:
        raise invalid_completion_error(completed)
    return EvidenceViewResult.model_validate(outcome.record.model_dump(mode="json"))


__all__ = ["run_ledger_evidence_list", "run_ledger_evidence_view"]


def _evidence_list_receipt_invalid(
    completed: RegisteredOperationCompletion[LedgerEvidenceListProjection],
    projection: LedgerEvidenceListProjection,
    profile_uuid: UUID,
    profile_id: str,
) -> bool:
    """Require complete unique evidence rows owned by the exact read profile."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.NONE
        or (projection.profile_id != profile_uuid)
        or (projection.count != len(projection.rows))
        or any(row.bucket_id != profile_id for row in projection.rows)
        or (len({row.evidence_id for row in projection.rows}) != projection.count)
    )
