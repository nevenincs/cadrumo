"""CLI bridges for exact-profile local expedientes snapshot reads."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer
from pydantic import BaseModel

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
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
        raise ValueError("expedientes read result disagrees with its settled receipt")


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


def read_expedientes_list_for_cli(ctx: typer.Context) -> ExpedientesListRead:
    """Read exact-profile local expedientes snapshot summaries."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = ExpedientesListRequest(profile_id=profile_id)
    completed = _submit(
        client,
        profile_id,
        request,
        definition_id=EXPEDIENTES_LIST_DEFINITION_ID,
        result_type=ExpedientesListPublicResultV1,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, ExpedientesListPublicResultV1):
            raise ValueError("expedientes list projection has an invalid type")
        if projection.bucket_id != str(profile_id) or projection.count != len(projection.rows):
            raise ValueError("expedientes list result does not match its submitted profile and rows")
        _require_settled_none(completed)
    except Exception:
        raise _correlated_invalid_frame(completed) from None
    return ExpedientesListRead(completion=completed, projection=projection)


def read_expedientes_show_for_cli(ctx: typer.Context, *, snapshot_id: str) -> ExpedientesShowRead:
    """Read one exact-profile expedientes snapshot by full id or prefix."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = ExpedientesShowRequest(profile_id=profile_id, snapshot_id=snapshot_id)
    completed = _submit(
        client,
        profile_id,
        request,
        definition_id=EXPEDIENTES_SHOW_DEFINITION_ID,
        result_type=ExpedientesShowPublicResultV1,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, ExpedientesShowPublicResultV1):
            raise ValueError("expedientes show projection has an invalid type")
        if (
            projection.bucket_id != str(profile_id)
            or not projection.snapshot_id.startswith(request.snapshot_id)
            or projection.declaration_count != len(projection.declarations)
        ):
            raise ValueError("expedientes show result does not match its submitted profile, id and declarations")
        _require_settled_none(completed)
    except Exception:
        raise _correlated_invalid_frame(completed) from None
    return ExpedientesShowRead(completion=completed, projection=projection)


def read_expedientes_latest_for_cli(ctx: typer.Context) -> ExpedientesLatestRead:
    """Read the newest exact-profile expedientes snapshot, if one exists."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = ExpedientesLatestRequest(profile_id=profile_id)
    completed = _submit(
        client,
        profile_id,
        request,
        definition_id=EXPEDIENTES_LATEST_DEFINITION_ID,
        result_type=ExpedientesLatestPublicResultV1,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, ExpedientesLatestPublicResultV1):
            raise ValueError("expedientes latest projection has an invalid type")
        if projection.bucket_id != str(profile_id):
            raise ValueError("expedientes latest result does not match its submitted profile")
        snapshot_details = (projection.captured_at, projection.source_url, projection.declaration_count)
        if (projection.snapshot_id is None and any(value is not None for value in snapshot_details)) or (
            projection.snapshot_id is not None and any(value is None for value in snapshot_details)
        ):
            raise ValueError("expedientes latest result has incomplete snapshot details")
        _require_settled_none(completed)
    except Exception:
        raise _correlated_invalid_frame(completed) from None
    return ExpedientesLatestRead(completion=completed, projection=projection)


__all__ = [
    "ExpedientesLatestRead",
    "ExpedientesListRead",
    "ExpedientesShowRead",
    "read_expedientes_latest_for_cli",
    "read_expedientes_list_for_cli",
    "read_expedientes_show_for_cli",
]
