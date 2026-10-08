"""Submit ledger LLM diagnostics through the authenticated profile worker."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import typer

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.ledger.llm_diagnostics import LlmDiagnosticsReport
from ...application.ledger.llm_diagnostics_operation import (
    LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID,
    LedgerLlmDiagnosticsProjection,
    LedgerLlmDiagnosticsRequest,
)
from ...application.operations.public_scalar import PublicDecimal
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation


def read_ledger_llm_diagnostics_for_cli(
    ctx: typer.Context,
    *,
    since: date | None,
    until: date | None,
    low_confidence_threshold: Decimal,
) -> LlmDiagnosticsReport:
    """Read both canonical metric stores for the exact bound profile."""
    client: RuntimeFrontendClient = bound_profile_client(ctx)
    public_threshold = PublicDecimal(decimal=str(low_confidence_threshold))
    request = LedgerLlmDiagnosticsRequest(
        profile_id=client.profile_id,
        since=since,
        until=until,
        low_confidence_threshold=public_threshold,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerLlmDiagnosticsProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    projection = completed.projection
    if _llm_diagnostics_receipt_invalid(completed, projection, client.profile_id, since, until, public_threshold):
        raise invalid_completion_error(completed)

    report = projection.to_report()
    if report.since != since or report.until != until or report.low_confidence_threshold != low_confidence_threshold:
        raise invalid_completion_error(completed)
    return report


__all__ = ["read_ledger_llm_diagnostics_for_cli"]


def _llm_diagnostics_receipt_invalid(
    completed: RegisteredOperationCompletion[LedgerLlmDiagnosticsProjection],
    projection: LedgerLlmDiagnosticsProjection,
    profile_id: UUID,
    since: date | None,
    until: date | None,
    public_threshold: PublicDecimal,
) -> bool:
    """Correlate the settled read receipt and exact metric window and threshold."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or (projection.profile_id != profile_id)
        or (projection.operation_id != LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID)
        or (projection.outcome != "completed")
        or (projection.effect is not OperationEffect.NONE)
        or (projection.since != since)
        or (projection.until != until)
        or (projection.low_confidence_threshold != public_threshold)
    )
