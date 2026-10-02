"""Registered CLI transport for live Modelo 100 borrador operations."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Never

import typer
from pydantic import BaseModel, ValidationError

from ...application.live.borrador_100_operation import (
    BORRADOR_100_IMPORT_OPERATION_DEFINITION_ID,
    BORRADOR_100_READ_OPERATION_DEFINITION_ID,
    Borrador100ImportProjection,
    Borrador100ImportRequest,
    Borrador100ReadProjection,
    Borrador100ReadRequest,
)
from ...application.live.snapshot_base import SnapshotLifecycleState, SnapshotStateFilter
from ...application.operations.public_period import PublicPeriod
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)

type _ReadKind = Literal["list", "view", "latest"]


def _invalid[ProjectionT: BaseModel](completed: RegisteredOperationCompletion[ProjectionT]) -> Never:
    """Reject a projection that does not correlate with its worker receipt."""
    raise submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


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
        _invalid(completed)

    if kind == "list":
        selected_state = state.as_lifecycle_state()
        if (
            projection.snapshot is not None
            or projection.filing_year is not None
            or (selected_state is not None and any(row.state is not selected_state for row in projection.rows))
        ):
            _invalid(completed)
    elif kind == "view":
        record = projection.snapshot
        if (
            record is None
            or projection.rows
            or projection.filing_year is not None
            or snapshot_id is None
            or not str(record.snapshot_id).startswith(snapshot_id.strip())
        ):
            _invalid(completed)
    else:
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
            _invalid(completed)
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
        _invalid(completed)
    return projection


__all__ = ["import_borrador_100_for_cli", "read_borrador_100_for_cli"]
