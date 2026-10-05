"""Registered worker bridge for the ledger evidence batch."""

from __future__ import annotations

from pathlib import Path

import typer
from pydantic import ValidationError

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.ledger.evidence_ingestion_contracts import (
    LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,
    LedgerEvidenceBatchProjection,
    LedgerEvidenceBatchRequest,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.iva.classification import InvoiceKind
from ._ledger_support import ledger_validation_bad
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation


def run_ledger_evidence_batch(
    ctx: typer.Context,
    *,
    sources: tuple[str, ...],
    direction: InvoiceKind,
) -> LedgerEvidenceBatchProjection:
    """Run the exact-profile batch with caller-relative sources in secure custody."""
    client = bound_profile_client(ctx)
    try:
        request = LedgerEvidenceBatchRequest(
            profile_id=client.profile_id,
            sources=sources,
            source_directory=str(Path.cwd()),
            direction=direction,
        )
    except ValidationError as error:
        raise ledger_validation_bad(error) from error
    completed = _submit(
        client,
        request,
        definition_id=LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,
        result_type=LedgerEvidenceBatchProjection,
    )
    projection = completed.projection
    if (
        projection.profile_id != client.profile_id
        or projection.direction is not direction
        or projection.effect not in {OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.PARTIAL}
    ):
        raise invalid_completion_error(completed)
    return projection


def _submit(
    client: RuntimeFrontendClient,
    request: LedgerEvidenceBatchRequest,
    *,
    definition_id: str,
    result_type: type[LedgerEvidenceBatchProjection],
) -> RegisteredOperationCompletion[LedgerEvidenceBatchProjection]:
    """Submit one typed secure-reference request and require a truthful success."""
    completed = run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=result_type,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not completed.projection.effect
        or completed.projection.profile_id != client.profile_id
    ):
        raise invalid_completion_error(completed)
    return completed


__all__ = [
    "run_ledger_evidence_batch",
]
