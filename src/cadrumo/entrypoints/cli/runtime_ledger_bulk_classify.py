"""CLI transport bridge for worker-owned CSV ledger classification."""

from __future__ import annotations

from typing import Never

import typer
from pydantic import BaseModel, ValidationError

from ...application.ledger.bulk_classify_operation import (
    LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID,
    LEDGER_BULK_CLASSIFY_VALIDATION_REFUSAL_CODE,
    LedgerBulkClassifyProjection,
    LedgerBulkClassifyRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


def _invalid[ProjectionT: BaseModel](completed: RegisteredOperationCompletion[ProjectionT]) -> Never:
    """Refuse a bulk projection that does not match its operation receipt."""
    raise submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


def run_ledger_bulk_classify(
    ctx: typer.Context,
    *,
    csv_text: str,
    actor: str | None,
) -> LedgerBulkClassifyProjection:
    """Submit CSV classification to the exact profile's registered worker."""
    client = bound_profile_client(ctx)
    try:
        request = LedgerBulkClassifyRequest(
            profile_id=client.profile_id,
            csv_text=csv_text,
            actor=actor or str(client.profile_id),
        )
    except ValidationError:
        # Keep oversized or invalid private request data out of parser errors.
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
    completed = run_registered_operation(
        client,
        request,
        definition_id=LEDGER_BULK_CLASSIFY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerBulkClassifyProjection,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    if projection.profile_id != client.profile_id:
        _invalid(completed)
    if projection.outcome == "validation_error":
        if (
            completed.terminal_condition is not OperationTerminalCondition.REFUSED
            or completed.refusal_code != LEDGER_BULK_CLASSIFY_VALIDATION_REFUSAL_CODE
            or completed.effect is not OperationEffect.NONE
            or projection.result is not None
            or not projection.validation_messages
        ):
            _invalid(completed)
        return projection

    result = projection.result
    if result is None or projection.outcome != "classified" or projection.validation_messages:
        _invalid(completed)
    # The terminal operation receipt owns the effect. The public result's
    # applied count only checks that the receipt agrees with the action outcome;
    # returned bucket-event ids are not used as proof of a durable write.
    expected_effect = OperationEffect.UPDATED if result.applied else OperationEffect.NONE
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not expected_effect
        or completed.refusal_code is not None
    ):
        _invalid(completed)
    return projection


__all__ = ["run_ledger_bulk_classify"]
