"""Registered CLI transport for live Modelo 100 borrador operations."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Never

import typer
from pydantic import ValidationError

from ...application.live.borrador_100_contracts import (
    Borrador100ImportProjection,
    Borrador100ImportRequest,
    Borrador100ReadProjection,
    Borrador100ReadRequest,
)
from ...application.live.borrador_100_operation import (
    BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID,
    BORRADOR_100_READ_OPERATION_DEFINITION_ID,
)
from ...application.live.snapshot_base import SnapshotLifecycleState, SnapshotStateFilter
from ...application.operations.public_period import PublicPeriod
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation

type _ReadKind = Literal["list", "view", "latest"]


def _invalid_request() -> Never:
    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)


def read_borrador_100_for_cli(
    ctx: typer.Context,
    *,
    kind: _ReadKind,
    state: SnapshotStateFilter = SnapshotStateFilter.ACTIVE,
    snapshot_id: str | None = None,
    filing_year: int | None = None,
) -> Borrador100ReadProjection:
    """Return an exact-profile list, unique-prefix view, or year-latest result."""
    client = bound_profile_client(ctx)
    try:
        request = Borrador100ReadRequest(
            profile_id=client.profile_id,
            kind=kind,
            state=state,
            snapshot_id=snapshot_id,
            filing_year=filing_year,
        )
    except ValidationError:
        _invalid_request()
    completed = run_registered_operation(
        client,
        request,
        definition_id=BORRADOR_100_READ_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=Borrador100ReadProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    projection = completed.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or projection.profile_id != client.profile_id
        or projection.kind != kind
    ):
        raise invalid_completion_error(completed)

    if kind == "list":
        _require_borrador_list(completed, projection, state)
    elif kind == "view":
        _require_borrador_view(completed, projection, snapshot_id)
    else:
        _require_borrador_latest(completed, projection, filing_year)
    return projection


def import_borrador_100_for_cli(
    ctx: typer.Context,
    *,
    source_path: Path,
    filing_year: int,
    period: PublicPeriod,
) -> Borrador100ImportProjection:
    """Submit a protected local path and correlate the persisted import result."""
    client = bound_profile_client(ctx)
    try:
        request = Borrador100ImportRequest(
            profile_id=client.profile_id,
            source_path=source_path,
            filing_year=filing_year,
            period=period,
        )
    except ValidationError:
        _invalid_request()
    completed = run_registered_operation(
        client,
        request,
        definition_id=BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=Borrador100ImportProjection,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    snapshot = projection.snapshot
    expected_source = f"file-import:sha256:{projection.source_pdf_sha256}"
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect not in {OperationEffect.NONE, OperationEffect.UPDATED}
        or completed.refusal_code is not None
        or projection.profile_id != client.profile_id
        or snapshot.filing_year != filing_year
        or snapshot.period != period
        or snapshot.source_url != expected_source
    ):
        raise invalid_completion_error(completed)
    return projection


__all__ = ["import_borrador_100_for_cli", "read_borrador_100_for_cli"]


def _require_borrador_list(
    completed: RegisteredOperationCompletion[Borrador100ReadProjection],
    projection: Borrador100ReadProjection,
    state: SnapshotStateFilter,
) -> None:
    """Correlate the selected borrador read shape with the request."""
    selected_state = state.as_lifecycle_state()
    if (
        projection.snapshot is not None
        or projection.filing_year is not None
        or (selected_state is not None and any(row.state is not selected_state for row in projection.rows))
    ):
        raise invalid_completion_error(completed)


def _require_borrador_view(
    completed: RegisteredOperationCompletion[Borrador100ReadProjection],
    projection: Borrador100ReadProjection,
    snapshot_id: str | None,
) -> None:
    """Correlate the selected borrador read shape with the request."""
    record = projection.snapshot
    if (
        record is None
        or projection.rows
        or projection.filing_year is not None
        or snapshot_id is None
        or not str(record.snapshot_id).startswith(snapshot_id.strip())
    ):
        raise invalid_completion_error(completed)


def _require_borrador_latest(
    completed: RegisteredOperationCompletion[Borrador100ReadProjection],
    projection: Borrador100ReadProjection,
    filing_year: int | None,
) -> None:
    """Correlate the selected borrador read shape with the request."""
    record = projection.snapshot
    if (
        projection.rows
        or projection.filing_year != filing_year
        or filing_year is None
        or (
            record is not None
            and (record.filing_year != filing_year or record.state is not SnapshotLifecycleState.ACTIVE)
        )
    ):
        raise invalid_completion_error(completed)
