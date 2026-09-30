"""CLI transport bridge for worker-owned ledger catalogue reset."""

from __future__ import annotations

import typer

from ...application.ledger.reset_operation import (
    LEDGER_RESET_OPERATION_DEFINITION_ID,
    LedgerResetOperationResult,
    LedgerResetRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


def run_ledger_reset(
    ctx: typer.Context,
    *,
    reason: str,
    dry_run: bool,
    actor: str | None,
) -> LedgerResetOperationResult:
    """Run one exact-profile reset and correlate its complete private receipt."""
    client = bound_profile_client(ctx)
    normalized_actor = actor or None
    request = LedgerResetRequest(
        profile_id=client.profile_id,
        reason=reason,
        dry_run=dry_run,
        actor=normalized_actor,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=LEDGER_RESET_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerResetOperationResult,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    report = completed.projection.report
    expected_effect = OperationEffect.NONE if dry_run else OperationEffect.UPDATED
    expected_actor = normalized_actor.strip() if normalized_actor is not None else str(client.profile_id)
    invalid = (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not expected_effect
        or completed.projection.profile_id != client.profile_id
        or str(report.bucket_id) != str(client.profile_id)
        or report.reset is not (not dry_run)
        or report.dry_run is not dry_run
        or report.reason != reason.strip()
        or report.actor != expected_actor
    )
    if invalid:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    return completed.projection


__all__ = ["run_ledger_reset"]
