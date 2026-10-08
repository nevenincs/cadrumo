"""CLI bridge for worker-owned manual ledger splits."""

from __future__ import annotations

from uuid import UUID

import typer
from pydantic import ValidationError

from ...application.ledger.actions_common import display_decimal
from ...application.ledger.models import SplitChildCommand
from ...application.ledger.split_operation import (
    LEDGER_SPLIT_OPERATION_DEFINITION_ID,
    LedgerSplitChildRequest,
    LedgerSplitOperationResult,
    LedgerSplitRequest,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ._ledger_support import ledger_validation_bad
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation


def run_ledger_split(
    ctx: typer.Context,
    *,
    transaction_id: str,
    children: tuple[SplitChildCommand, ...],
    reason: str,
    actor: str | None,
) -> LedgerSplitOperationResult:
    """Submit one split under the authenticated profile and correlate its receipt."""
    client = bound_profile_client(ctx)
    try:
        request = LedgerSplitRequest(
            profile_id=client.profile_id,
            transaction_id=transaction_id,
            children=tuple(
                LedgerSplitChildRequest(
                    amount=display_decimal(child.amount),
                    description=child.description,
                )
                for child in children
            ),
            reason=reason,
            actor=actor if actor else None,
        )
    except ValidationError as exc:
        raise ledger_validation_bad(exc) from exc

    completed = run_registered_operation(
        client,
        request,
        definition_id=LEDGER_SPLIT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerSplitOperationResult,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    invalid = _ledger_split_receipt_invalid(completed, projection, request, client.profile_id)
    if invalid:
        raise invalid_completion_error(completed)
    return projection


__all__ = ["run_ledger_split"]


def _ledger_split_receipt_invalid(
    completed: RegisteredOperationCompletion[LedgerSplitOperationResult],
    projection: LedgerSplitOperationResult,
    request: LedgerSplitRequest,
    profile_id: UUID,
) -> bool:
    """Require the updated parent, unique children, exact count, and settled profile receipt."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.UPDATED
        or (projection.profile_id != profile_id)
        or (not projection.parent_transaction_id.startswith(request.transaction_id))
        or (len(projection.child_transaction_ids) != len(request.children))
        or (len(set(projection.child_transaction_ids)) != len(request.children))
        or (projection.parent_transaction_id in projection.child_transaction_ids)
    )
