"""CLI bridges for exact-profile local notification snapshot reads."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer
from pydantic import BaseModel

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.live.notifications_read_operation import (
    NOTIFICATIONS_LATEST_DEFINITION_ID,
    NOTIFICATIONS_LIST_DEFINITION_ID,
    NOTIFICATIONS_SHOW_DEFINITION_ID,
    NotificationsLatestPublicResultV1,
    NotificationsLatestRequest,
    NotificationsListPublicResultV1,
    NotificationsListRequest,
    NotificationsShowPublicResultV1,
    NotificationsShowRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


@dataclass(frozen=True, slots=True)
class NotificationsListRead:
    """Keep the settled receipt with the exact-profile snapshot inventory."""

    completion: RegisteredOperationCompletion[NotificationsListPublicResultV1]
    projection: NotificationsListPublicResultV1


@dataclass(frozen=True, slots=True)
class NotificationsShowRead:
    """Keep the settled receipt with one prefix-correlated snapshot view."""

    completion: RegisteredOperationCompletion[NotificationsShowPublicResultV1]
    projection: NotificationsShowPublicResultV1


@dataclass(frozen=True, slots=True)
class NotificationsLatestRead:
    """Keep the settled receipt with the latest snapshot summary or empty state."""

    completion: RegisteredOperationCompletion[NotificationsLatestPublicResultV1]
    projection: NotificationsLatestPublicResultV1


def _submit[ResultT: BaseModel](
    client: RuntimeFrontendClient,
    profile_id: UUID,
    request: BaseModel,
    *,
    result_type: type[ResultT],
    definition_id: str,
) -> RegisteredOperationCompletion[ResultT]:
    """Submit one registered read over the client bound to the active profile."""
    return run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=result_type,
        request_version=1,
        result_version=1,
        timeout=120,
    )


def _require_settled_none[ResultT: BaseModel](completed: RegisteredOperationCompletion[ResultT]) -> None:
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.NONE
    ):
        raise ValueError("notification read result disagrees with its settled receipt")


def _correlated_invalid_frame[ResultT: BaseModel](
    completed: RegisteredOperationCompletion[ResultT],
) -> Exception:
    return submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


def read_notifications_list_for_cli(ctx: typer.Context) -> NotificationsListRead:
    """Read exact-profile local notification snapshot summaries."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = NotificationsListRequest(profile_id=profile_id)
    completed = _submit(
        client,
        profile_id,
        request,
        definition_id=NOTIFICATIONS_LIST_DEFINITION_ID,
        result_type=NotificationsListPublicResultV1,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, NotificationsListPublicResultV1):
            raise ValueError("notification list projection has an invalid type")
        if projection.bucket_id != str(profile_id) or projection.count != len(projection.rows):
            raise ValueError("notification list result does not match its submitted profile and rows")
        _require_settled_none(completed)
    except Exception:
        raise _correlated_invalid_frame(completed) from None
    return NotificationsListRead(completion=completed, projection=projection)


def read_notifications_show_for_cli(ctx: typer.Context, *, snapshot_id: str) -> NotificationsShowRead:
    """Read one exact-profile notification snapshot by full id or prefix."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = NotificationsShowRequest(profile_id=profile_id, snapshot_id=snapshot_id)
    completed = _submit(
        client,
        profile_id,
        request,
        definition_id=NOTIFICATIONS_SHOW_DEFINITION_ID,
        result_type=NotificationsShowPublicResultV1,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, NotificationsShowPublicResultV1):
            raise ValueError("notification show projection has an invalid type")
        if (
            projection.bucket_id != str(profile_id)
            or not projection.snapshot_id.startswith(request.snapshot_id)
            or projection.row_count != len(projection.rows)
        ):
            raise ValueError("notification show result does not match its submitted profile, prefix and rows")
        _require_settled_none(completed)
    except Exception:
        raise _correlated_invalid_frame(completed) from None
    return NotificationsShowRead(completion=completed, projection=projection)


def read_notifications_latest_for_cli(ctx: typer.Context) -> NotificationsLatestRead:
    """Read the newest exact-profile notification snapshot, if one exists."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = NotificationsLatestRequest(profile_id=profile_id)
    completed = _submit(
        client,
        profile_id,
        request,
        definition_id=NOTIFICATIONS_LATEST_DEFINITION_ID,
        result_type=NotificationsLatestPublicResultV1,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, NotificationsLatestPublicResultV1):
            raise ValueError("notification latest projection has an invalid type")
        if projection.bucket_id != str(profile_id):
            raise ValueError("notification latest result does not match its submitted profile")
        _require_settled_none(completed)
    except Exception:
        raise _correlated_invalid_frame(completed) from None
    return NotificationsLatestRead(completion=completed, projection=projection)


__all__ = [
    "NotificationsLatestRead",
    "NotificationsListRead",
    "NotificationsShowRead",
    "read_notifications_latest_for_cli",
    "read_notifications_list_for_cli",
    "read_notifications_show_for_cli",
]
