"""CLI bridge for worker-owned manual ledger splits."""

from __future__ import annotations

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
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ._ledger_support import ledger_validation_bad
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


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
    prefix = request.transaction_id
    invalid = (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.UPDATED
        or projection.profile_id != client.profile_id
        or not projection.parent_transaction_id.startswith(prefix)
        or len(projection.child_transaction_ids) != len(request.children)
        or len(set(projection.child_transaction_ids)) != len(request.children)
        or projection.parent_transaction_id in projection.child_transaction_ids
    )
    if invalid:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    return projection


__all__ = ["run_ledger_split"]
