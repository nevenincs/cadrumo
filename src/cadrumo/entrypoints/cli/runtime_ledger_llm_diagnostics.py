"""Submit ledger LLM diagnostics through the authenticated profile worker."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Never

import typer

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.ledger.llm_diagnostics import LlmDiagnosticsReport
from ...application.ledger.llm_diagnostics_operation import (
    LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID,
    LedgerLlmDiagnosticsProjection,
    LedgerLlmDiagnosticsRequest,
)
from ...application.operations.public_scalar import PublicDecimal
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


def _invalid(completed: RegisteredOperationCompletion[LedgerLlmDiagnosticsProjection]) -> Never:
    raise submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


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
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or projection.profile_id != client.profile_id
        or projection.operation_id != LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID
        or projection.outcome != "completed"
        or projection.effect is not OperationEffect.NONE
        or projection.since != since
        or projection.until != until
        or projection.low_confidence_threshold != public_threshold
    ):
        _invalid(completed)

    report = projection.to_report()
    if report.since != since or report.until != until or report.low_confidence_threshold != low_confidence_threshold:
        _invalid(completed)
    return report


__all__ = ["read_ledger_llm_diagnostics_for_cli"]
