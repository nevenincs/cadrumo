"""CLI bridges for exact-profile local expedientes snapshot reads."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer

from ...application.live.expedientes_read_operation import (
    EXPEDIENTES_LATEST_DEFINITION_ID,
    EXPEDIENTES_LIST_DEFINITION_ID,
    EXPEDIENTES_SHOW_DEFINITION_ID,
    ExpedientesLatestPublicResultV1,
    ExpedientesLatestRequest,
    ExpedientesListPublicResultV1,
    ExpedientesListRequest,
    ExpedientesShowPublicResultV1,
    ExpedientesShowRequest,
)
from ...core.bucket_pointer import require_active_bucket_id
from .registered_operation_contracts import RegisteredOperationCompletion
from .runtime_profile_binding import require_profile_client
from .runtime_profile_operation import settled_profile_projection, submit_profile_operation


@dataclass(frozen=True, slots=True)
class ExpedientesListRead:
    """Keep the settled receipt with the exact-profile snapshot inventory."""

    completion: RegisteredOperationCompletion[ExpedientesListPublicResultV1]
    projection: ExpedientesListPublicResultV1


@dataclass(frozen=True, slots=True)
class ExpedientesShowRead:
    """Keep the settled receipt with one prefix-correlated snapshot view."""

    completion: RegisteredOperationCompletion[ExpedientesShowPublicResultV1]
    projection: ExpedientesShowPublicResultV1


@dataclass(frozen=True, slots=True)
class ExpedientesLatestRead:
    """Keep the settled receipt with the latest snapshot summary or empty state."""

    completion: RegisteredOperationCompletion[ExpedientesLatestPublicResultV1]
    projection: ExpedientesLatestPublicResultV1


def read_expedientes_list_for_cli(ctx: typer.Context) -> ExpedientesListRead:
    """Read exact-profile local expedientes snapshot summaries."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = ExpedientesListRequest(profile_id=profile_id)
    completed = submit_profile_operation(
        client,
        profile_id,
        request,
        definition_id=EXPEDIENTES_LIST_DEFINITION_ID,
        result_type=ExpedientesListPublicResultV1,
    )

    def correlate(projection: ExpedientesListPublicResultV1) -> None:
        if projection.count != len(projection.rows):
            raise ValueError("expedientes list result does not match its rows")

    projection = settled_profile_projection(completed, ExpedientesListPublicResultV1, profile_id, correlate)
    return ExpedientesListRead(completion=completed, projection=projection)


def read_expedientes_show_for_cli(ctx: typer.Context, *, snapshot_id: str) -> ExpedientesShowRead:
    """Read one exact-profile expedientes snapshot by full id or prefix."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = ExpedientesShowRequest(profile_id=profile_id, snapshot_id=snapshot_id)
    completed = submit_profile_operation(
        client,
        profile_id,
        request,
        definition_id=EXPEDIENTES_SHOW_DEFINITION_ID,
        result_type=ExpedientesShowPublicResultV1,
    )

    def correlate(projection: ExpedientesShowPublicResultV1) -> None:
        if not projection.snapshot_id.startswith(request.snapshot_id) or projection.declaration_count != len(
            projection.declarations
        ):
            raise ValueError("expedientes show result does not match its submitted id and declarations")

    projection = settled_profile_projection(completed, ExpedientesShowPublicResultV1, profile_id, correlate)
    return ExpedientesShowRead(completion=completed, projection=projection)


def read_expedientes_latest_for_cli(ctx: typer.Context) -> ExpedientesLatestRead:
    """Read the newest exact-profile expedientes snapshot, if one exists."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = ExpedientesLatestRequest(profile_id=profile_id)
    completed = submit_profile_operation(
        client,
        profile_id,
        request,
        definition_id=EXPEDIENTES_LATEST_DEFINITION_ID,
        result_type=ExpedientesLatestPublicResultV1,
    )

    def correlate(projection: ExpedientesLatestPublicResultV1) -> None:
        snapshot_details = (projection.captured_at, projection.source_url, projection.declaration_count)
        if (projection.snapshot_id is None and any(value is not None for value in snapshot_details)) or (
            projection.snapshot_id is not None and any(value is None for value in snapshot_details)
        ):
            raise ValueError("expedientes latest result has incomplete snapshot details")

    projection = settled_profile_projection(completed, ExpedientesLatestPublicResultV1, profile_id, correlate)
    return ExpedientesLatestRead(completion=completed, projection=projection)


__all__ = [
    "ExpedientesLatestRead",
    "ExpedientesListRead",
    "ExpedientesShowRead",
    "read_expedientes_latest_for_cli",
    "read_expedientes_list_for_cli",
    "read_expedientes_show_for_cli",
]
