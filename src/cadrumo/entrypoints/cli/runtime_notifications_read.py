"""CLI bridges for exact-profile local notification snapshot reads."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer

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
from ...core.bucket_pointer import require_active_bucket_id
from .registered_operation_contracts import RegisteredOperationCompletion
from .runtime_profile_binding import require_profile_client
from .runtime_profile_operation import settled_profile_projection, submit_profile_operation


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


def read_notifications_list_for_cli(ctx: typer.Context) -> NotificationsListRead:
    """Read exact-profile local notification snapshot summaries."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = NotificationsListRequest(profile_id=profile_id)
    completed = submit_profile_operation(
        client,
        profile_id,
        request,
        definition_id=NOTIFICATIONS_LIST_DEFINITION_ID,
        result_type=NotificationsListPublicResultV1,
    )

    def correlate(projection: NotificationsListPublicResultV1) -> None:
        if projection.count != len(projection.rows):
            raise ValueError("notification list result does not match its rows")

    projection = settled_profile_projection(completed, NotificationsListPublicResultV1, profile_id, correlate)
    return NotificationsListRead(completion=completed, projection=projection)


def read_notifications_show_for_cli(ctx: typer.Context, *, snapshot_id: str) -> NotificationsShowRead:
    """Read one exact-profile notification snapshot by full id or prefix."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = NotificationsShowRequest(profile_id=profile_id, snapshot_id=snapshot_id)
    completed = submit_profile_operation(
        client,
        profile_id,
        request,
        definition_id=NOTIFICATIONS_SHOW_DEFINITION_ID,
        result_type=NotificationsShowPublicResultV1,
    )

    def correlate(projection: NotificationsShowPublicResultV1) -> None:
        if not projection.snapshot_id.startswith(request.snapshot_id) or projection.row_count != len(projection.rows):
            raise ValueError("notification show result does not match its submitted prefix and rows")

    projection = settled_profile_projection(completed, NotificationsShowPublicResultV1, profile_id, correlate)
    return NotificationsShowRead(completion=completed, projection=projection)


def read_notifications_latest_for_cli(ctx: typer.Context) -> NotificationsLatestRead:
    """Read the newest exact-profile notification snapshot, if one exists."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = NotificationsLatestRequest(profile_id=profile_id)
    completed = submit_profile_operation(
        client,
        profile_id,
        request,
        definition_id=NOTIFICATIONS_LATEST_DEFINITION_ID,
        result_type=NotificationsLatestPublicResultV1,
    )
    projection = settled_profile_projection(
        completed, NotificationsLatestPublicResultV1, profile_id, lambda _projection: None
    )
    return NotificationsLatestRead(completion=completed, projection=projection)


__all__ = [
    "NotificationsLatestRead",
    "NotificationsListRead",
    "NotificationsShowRead",
    "read_notifications_latest_for_cli",
    "read_notifications_list_for_cli",
    "read_notifications_show_for_cli",
]
