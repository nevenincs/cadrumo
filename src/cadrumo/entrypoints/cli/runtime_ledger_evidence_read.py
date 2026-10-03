"""CLI transport bridge for worker-owned purchase-invoice evidence reads."""

from __future__ import annotations

import typer

from ...application.ledger.evidence_read_operation import (
    LEDGER_EVIDENCE_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_VIEW_OPERATION_DEFINITION_ID,
    LedgerEvidenceListProjection,
    LedgerEvidenceListRequest,
    LedgerEvidenceViewProjection,
    LedgerEvidenceViewRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .ledger_business_payloads import EvidenceListResult, EvidenceViewResult
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


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
    invalid = (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.NONE
        or projection.profile_id != client.profile_id
        or projection.count != len(projection.rows)
        or any(row.bucket_id != profile_id for row in projection.rows)
        or len({row.evidence_id for row in projection.rows}) != projection.count
    )
    if invalid:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
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
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    invalid = (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.NONE
        or projection.profile_id != client.profile_id
        or projection.record.bucket_id != str(client.profile_id)
        or projection.record.evidence_id != evidence_id
    )
    if invalid:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    return EvidenceViewResult.model_validate(projection.record.model_dump(mode="json"))


__all__ = ["run_ledger_evidence_list", "run_ledger_evidence_view"]
