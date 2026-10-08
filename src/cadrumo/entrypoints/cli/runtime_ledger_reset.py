"""CLI transport bridge for worker-owned ledger catalogue reset."""

from __future__ import annotations

from uuid import UUID

import typer

from ...application.ledger.reset_operation import (
    LEDGER_RESET_OPERATION_DEFINITION_ID,
    LedgerResetOperationResult,
    LedgerResetReportProjection,
    LedgerResetRequest,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation


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
        invalid_ledger_reset_receipt(completed, report, client.profile_id, expected_effect)
        or report.reset is not (not dry_run)
        or report.dry_run is not dry_run
        or (report.reason != reason.strip())
        or (report.actor != expected_actor)
    )
    if invalid:
        raise invalid_completion_error(completed)
    return completed.projection


__all__ = ["run_ledger_reset"]


def invalid_ledger_reset_receipt(
    completed: RegisteredOperationCompletion[LedgerResetOperationResult],
    report: LedgerResetReportProjection,
    profile_id: UUID,
    expected_effect: OperationEffect,
) -> bool:
    """Invalid ledger reset receipt."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not expected_effect
        or (completed.projection.profile_id != profile_id)
        or (str(report.bucket_id) != str(profile_id))
    )
