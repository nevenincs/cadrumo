"""CLI bridge for worker-owned manual ledger merges."""

from __future__ import annotations

import typer
from pydantic import ValidationError

from ...application.ledger.merge_operation import (
    LEDGER_MERGE_OPERATION_DEFINITION_ID,
    LedgerMergeOperationResult,
    LedgerMergeRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ._ledger_support import ledger_validation_bad
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


def run_ledger_merge(
    ctx: typer.Context,
    *,
    child_ids: tuple[str, ...],
    reason: str,
    actor: str | None,
) -> LedgerMergeOperationResult:
    """Submit one merge under the authenticated profile and correlate its receipt."""
    client = bound_profile_client(ctx)
    try:
        request = LedgerMergeRequest(
            profile_id=client.profile_id,
            child_ids=child_ids,
            reason=reason,
            actor=actor if actor else None,
        )
    except ValidationError as exc:
        raise ledger_validation_bad(exc) from exc

    completed = run_registered_operation(
        client,
        request,
        definition_id=LEDGER_MERGE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerMergeOperationResult,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    resolved_children = _correlate_child_prefixes(request.child_ids, projection.source_child_ids)
    invalid = (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.UPDATED
        or projection.profile_id != client.profile_id
        or resolved_children is None
        or projection.parent_transaction_id in projection.source_child_ids
        or projection.merged_transaction_id in (projection.parent_transaction_id, *projection.source_child_ids)
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


def _correlate_child_prefixes(prefixes: tuple[str, ...], child_ids: tuple[str, ...]) -> tuple[str, ...] | None:
    """Require a one-to-one match between submitted prefixes and returned children."""
    if len(prefixes) != len(child_ids) or len(set(child_ids)) != len(child_ids):
        return None
    resolved: list[str] = []
    for prefix in prefixes:
        matches = tuple(child_id for child_id in child_ids if child_id.startswith(prefix))
        if len(matches) != 1:
            return None
        resolved.append(matches[0])
    if len(set(resolved)) != len(child_ids):
        return None
    return tuple(resolved)


__all__ = ["run_ledger_merge"]
