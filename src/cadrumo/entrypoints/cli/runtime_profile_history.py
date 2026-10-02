"""CLI transport for an authenticated profile's complete event history."""

from __future__ import annotations

import typer

from ...application.runtime.contracts import RuntimeRefusalCode
from ...application.user_profile.history_operation import (
    PROFILE_HISTORY_OPERATION_DEFINITION_ID,
    ProfileHistoryProjection,
    ProfileHistoryRequest,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


def read_profile_history_for_cli(
    ctx: typer.Context,
    *,
    request: ProfileHistoryRequest,
) -> ProfileHistoryProjection:
    """Return only the exact-profile, exact-filter registered history result."""
    client = require_profile_client(ctx, expected_profile_id=request.profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=PROFILE_HISTORY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(request.profile_id)),
        result_type=ProfileHistoryProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    result = completed.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or result.profile_id != request.profile_id
        or result.event_types != request.event_types
        or result.since != request.since
        or result.until != request.until
        or result.object_id != request.object_id
        or result.actor != request.actor
        or result.event_count != len(result.events)
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    return result


__all__ = ["read_profile_history_for_cli"]
