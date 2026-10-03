"""Registered worker bridge for the ledger archive, stash, restore, and exclude verbs."""

from __future__ import annotations

import typer
from pydantic import ValidationError

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.ledger.lifecycle_mutation_operation import (
    LEDGER_ARCHIVE_OPERATION_DEFINITION_ID,
    LEDGER_EXCLUDE_OPERATION_DEFINITION_ID,
    LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE,
    LEDGER_RESTORE_OPERATION_DEFINITION_ID,
    LEDGER_STASH_OPERATION_DEFINITION_ID,
    LedgerLifecycleMutationProjection,
    LedgerLifecycleMutationRequest,
    LedgerLifecycleOperationId,
    LedgerLifecycleOperationResult,
    LedgerLifecycleValidationRefusedError,
)
from ...application.review.filter import LedgerReviewStatus
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.i18n.render import tr
from ...core.json_contract import OutputSchema
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ._ledger_payloads import TransactionPayload
from ._ledger_support import ledger_validation_bad
from .common import emit_envelope
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error

_SUCCESS_STATES: dict[LedgerLifecycleOperationId, str] = {
    LEDGER_ARCHIVE_OPERATION_DEFINITION_ID: "ARCHIVED",
    LEDGER_STASH_OPERATION_DEFINITION_ID: "STASHED",
    LEDGER_RESTORE_OPERATION_DEFINITION_ID: "ACTIVE",
    LEDGER_EXCLUDE_OPERATION_DEFINITION_ID: "ACTIVE",
}


def run_ledger_archive(
    ctx: typer.Context,
    *,
    transaction_id: str,
    reason: str,
    actor: str | None,
) -> LedgerLifecycleMutationProjection:
    """Submit archive under the caller's retained exact-profile session."""
    return _run(
        ctx,
        operation_id=LEDGER_ARCHIVE_OPERATION_DEFINITION_ID,
        transaction_id=transaction_id,
        reason=reason,
        actor=actor,
    )


def run_ledger_stash(
    ctx: typer.Context,
    *,
    transaction_id: str,
    reason: str,
    actor: str | None,
) -> LedgerLifecycleMutationProjection:
    """Submit stash under the caller's retained exact-profile session."""
    return _run(
        ctx,
        operation_id=LEDGER_STASH_OPERATION_DEFINITION_ID,
        transaction_id=transaction_id,
        reason=reason,
        actor=actor,
    )


def run_ledger_restore(
    ctx: typer.Context,
    *,
    transaction_id: str,
    reason: str,
    actor: str | None,
) -> LedgerLifecycleMutationProjection:
    """Submit restore under the caller's retained exact-profile session."""
    return _run(
        ctx,
        operation_id=LEDGER_RESTORE_OPERATION_DEFINITION_ID,
        transaction_id=transaction_id,
        reason=reason,
        actor=actor,
    )


def run_ledger_exclude(
    ctx: typer.Context,
    *,
    transaction_id: str,
    reason: str,
    actor: str | None,
) -> LedgerLifecycleMutationProjection:
    """Submit review exclusion under the caller's retained exact-profile session."""
    return _run(
        ctx,
        operation_id=LEDGER_EXCLUDE_OPERATION_DEFINITION_ID,
        transaction_id=transaction_id,
        reason=reason,
        actor=actor,
    )


def _run(
    ctx: typer.Context,
    *,
    operation_id: LedgerLifecycleOperationId,
    transaction_id: str,
    reason: str,
    actor: str | None,
) -> LedgerLifecycleMutationProjection:
    client = bound_profile_client(ctx)
    try:
        request = LedgerLifecycleMutationRequest(
            profile_id=client.profile_id,
            transaction_id=transaction_id,
            reason=reason,
            actor=actor if actor else None,
        )
    except ValidationError as error:
        raise ledger_validation_bad(error) from error
    return _submit(client, request, operation_id=operation_id)


def _submit(
    client: RuntimeFrontendClient,
    request: LedgerLifecycleMutationRequest,
    *,
    operation_id: LedgerLifecycleOperationId,
) -> LedgerLifecycleMutationProjection:
    completed = run_registered_operation(
        client,
        request,
        definition_id=operation_id,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerLifecycleOperationResult,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )
    result = completed.projection
    if result.outcome == "validation_error":
        if (
            completed.terminal_condition is not OperationTerminalCondition.REFUSED
            or completed.refusal_code != LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE
            or completed.effect is not OperationEffect.NONE
            or result.profile_id != client.profile_id
            or result.operation_id != operation_id
            or result.validation is None
        ):
            raise submitted_operation_error(
                completed.operation_id,
                RuntimeRefusalCode.INVALID_FRAME.value,
                terminal_condition=completed.terminal_condition,
                effect=completed.effect,
                refusal_code=completed.refusal_code,
            )
        raise LedgerLifecycleValidationRefusedError(result.validation) from None

    projection = result.result
    if projection is None:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    transaction = projection.transaction
    invalid = (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.UPDATED
        or result.profile_id != client.profile_id
        or result.operation_id != operation_id
        or projection.profile_id != client.profile_id
        or projection.operation_id != operation_id
        or not transaction.transaction_id.startswith(request.transaction_id.strip().lower())
        or transaction.lifecycle_state != _SUCCESS_STATES[operation_id]
        or len(projection.bucket_event_ids) != 1
        or (
            operation_id == LEDGER_EXCLUDE_OPERATION_DEFINITION_ID
            and (
                transaction.business_classification != "REVIEWED_EXCLUDED"
                or projection.review_status is not LedgerReviewStatus.EXCLUDED
            )
        )
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


def emit_ledger_lifecycle_result[ResultSchema: OutputSchema](
    ctx: typer.Context,
    projection: LedgerLifecycleMutationProjection,
    *,
    command: str,
    result_schema: type[ResultSchema],
) -> None:
    """Preserve the existing full ledger-mutation quintet on the CLI."""
    transaction = TransactionPayload.model_validate_json(projection.transaction.model_dump_json())
    result = result_schema.model_validate(
        {
            "bucket_id": str(projection.profile_id),
            "transaction_id": transaction.transaction_id,
            "bucket_event_ids": list(projection.bucket_event_ids),
            "review_status": projection.review_status,
            "transaction": transaction.model_dump(mode="json"),
        },
    )
    emit_envelope(
        ctx,
        command=command,
        result=result,
        lines=[
            f"{tr('cli.ledger.labels.id')}\t{transaction.transaction_id}",
            f"{tr('cli.ledger.labels.date')}\t{transaction.date}",
            f"{tr('cli.ledger.labels.amount')}\t{transaction.amount}",
            f"{tr('cli.ledger.labels.description')}\t{transaction.description}",
            f"{tr('cli.ledger.labels.review_status')}\t{projection.review_status}",
        ],
    )


__all__ = [
    "emit_ledger_lifecycle_result",
    "run_ledger_archive",
    "run_ledger_exclude",
    "run_ledger_restore",
    "run_ledger_stash",
]
