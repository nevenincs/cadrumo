"""CLI transport for worker-owned censal request preparation."""

from __future__ import annotations

import typer

from ....application.runtime.contracts import RuntimeRefusalCode
from ....application.user_profile.censal_prepare_operation import (
    CENSAL_PREPARE_OPERATION_DEFINITION_ID,
    CensalPrepareOperationProjection,
    CensalPrepareOperationRequest,
)
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..runtime_profile_binding import bound_profile_client
from ..runtime_registered_operation import run_registered_operation, submitted_operation_error


def prepare_censal_review(ctx: typer.Context) -> CensalPrepareOperationProjection:
    """Prepare a safe canonical request from the invocation's bound profile."""
    client = bound_profile_client(ctx)
    completed = run_registered_operation(
        client,
        CensalPrepareOperationRequest(profile_id=client.profile_id),
        definition_id=CENSAL_PREPARE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=CensalPrepareOperationProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    projection = completed.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.NONE
        or projection.profile_id != client.profile_id
        or projection.operation_request.baseline.profile_id != str(client.profile_id)
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
        )
    return projection


__all__ = ["prepare_censal_review"]
