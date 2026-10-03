"""CLI bridge for an exact-profile registered notification snapshot capture."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer

from ...application.live.notifications_capture_operation import (
    NOTIFICATIONS_CAPTURE_DEFINITION_ID,
    NotificationsCapturePublicResultV1,
    NotificationsCaptureRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


@dataclass(frozen=True, slots=True)
class NotificationsCaptureRead:
    """Keep the settled worker receipt beside its safe capture summary."""

    completion: RegisteredOperationCompletion[NotificationsCapturePublicResultV1]
    projection: NotificationsCapturePublicResultV1


def read_notifications_capture_for_cli(ctx: typer.Context, *, profile_id: UUID) -> NotificationsCaptureRead:
    """Submit one live capture to the client bound to the requested profile."""
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = NotificationsCaptureRequest(profile_id=profile_id)
    completed = run_registered_operation(
        client,
        request,
        definition_id=NOTIFICATIONS_CAPTURE_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=NotificationsCapturePublicResultV1,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, NotificationsCapturePublicResultV1):
            raise ValueError("notification capture projection has an invalid type")
        if projection.bucket_id != str(profile_id):
            raise ValueError("notification capture result does not match its submitted profile")
        if (
            completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or completed.refusal_code is not None
            or completed.effect not in {OperationEffect.UPDATED, OperationEffect.NONE}
        ):
            raise ValueError("notification capture result disagrees with its settled receipt")
    except Exception:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None
    return NotificationsCaptureRead(completion=completed, projection=projection)


__all__ = ["NotificationsCaptureRead", "read_notifications_capture_for_cli"]
