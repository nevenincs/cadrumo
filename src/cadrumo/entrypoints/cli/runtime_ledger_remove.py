"""CLI transport bridge for worker-owned ledger transaction removal."""

from __future__ import annotations

import typer

from ...application.ledger.remove_operation import (
    LEDGER_REMOVE_OPERATION_DEFINITION_ID,
    LedgerRemoveOperationResult,
    LedgerRemoveRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


def run_ledger_remove(
    ctx: typer.Context,
    *,
    transaction_id: str,
    reason: str,
    dry_run: bool,
    actor: str,
) -> LedgerRemoveOperationResult:
    """Run one exact-profile removal and correlate the full private receipt."""
    client = bound_profile_client(ctx)
    request = LedgerRemoveRequest(
        profile_id=client.profile_id,
        transaction_id=transaction_id,
        reason=reason,
        dry_run=dry_run,
        actor=actor,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=LEDGER_REMOVE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerRemoveOperationResult,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    report = completed.projection.report
    expected_effect = OperationEffect.UPDATED if report.removed else OperationEffect.NONE
    expected_actor = actor.strip()
    prefix = transaction_id.strip().lower()
    invalid = (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not expected_effect
        or completed.projection.profile_id != client.profile_id
        or str(report.bucket_id) != str(client.profile_id)
        or not report.transaction_id.startswith(prefix)
        or report.dry_run is not dry_run
        or report.reason != reason.strip()
        or report.actor != expected_actor
        or (not dry_run and not report.removed)
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


__all__ = ["run_ledger_remove"]
