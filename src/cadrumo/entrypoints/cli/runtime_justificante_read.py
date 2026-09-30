"""CLI bridges for exact-profile local justificante snapshot reads."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer
from pydantic import BaseModel

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.calculations.observations_repository import ObservationSourceKind
from ...application.live.justificante_read_operation import (
    JUSTIFICANTE_LIST_DEFINITION_ID,
    JUSTIFICANTE_SHOW_DEFINITION_ID,
    JustificanteListPublicResultV1,
    JustificanteListRequest,
    JustificanteShowPublicResultV1,
    JustificanteShowRequest,
)
from ...application.live.snapshot_base import SnapshotLifecycleState
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.modelo import Modelo
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


@dataclass(frozen=True, slots=True)
class JustificanteListRead:
    """Keep the settled receipt with the exact-profile active snapshot inventory."""

    completion: RegisteredOperationCompletion[JustificanteListPublicResultV1]
    projection: JustificanteListPublicResultV1


@dataclass(frozen=True, slots=True)
class JustificanteShowRead:
    """Keep the settled receipt with one prefix-correlated snapshot view."""

    completion: RegisteredOperationCompletion[JustificanteShowPublicResultV1]
    projection: JustificanteShowPublicResultV1


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


def _require_read_receipt[ResultT: BaseModel](completed: RegisteredOperationCompletion[ResultT]) -> None:
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.NONE
    ):
        raise ValueError("justificante read result disagrees with its settled receipt")


def _invalid_frame[ResultT: BaseModel](completed: RegisteredOperationCompletion[ResultT]) -> Exception:
    return submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


def read_justificante_list_for_cli(ctx: typer.Context) -> JustificanteListRead:
    """Read exact-profile local active justificante snapshot summaries."""
    client = bound_profile_client(ctx)
    profile_id = client.profile_id
    request = JustificanteListRequest(profile_id=profile_id)
    completed = _submit(
        client,
        profile_id,
        request,
        definition_id=JUSTIFICANTE_LIST_DEFINITION_ID,
        result_type=JustificanteListPublicResultV1,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, JustificanteListPublicResultV1):
            raise ValueError("justificante list projection has an invalid type")
        if projection.bucket_id != str(profile_id) or projection.count != len(projection.rows):
            raise ValueError("justificante list result does not match its submitted profile and rows")
        for row in projection.rows:
            Modelo(row.modelo)
            if row.state != SnapshotLifecycleState.ACTIVE.value:
                raise ValueError("justificante list result contains a non-active capture")
            Period.from_year_and_code(row.filing_year, row.period)
        _require_read_receipt(completed)
    except Exception:
        raise _invalid_frame(completed) from None
    return JustificanteListRead(completion=completed, projection=projection)


def read_justificante_show_for_cli(ctx: typer.Context, *, snapshot_id: str) -> JustificanteShowRead:
    """Read one exact-profile local snapshot by full id or unambiguous prefix."""
    client = bound_profile_client(ctx)
    profile_id = client.profile_id
    request = JustificanteShowRequest(profile_id=profile_id, snapshot_id=snapshot_id)
    completed = _submit(
        client,
        profile_id,
        request,
        definition_id=JUSTIFICANTE_SHOW_DEFINITION_ID,
        result_type=JustificanteShowPublicResultV1,
    )
    try:
        projection = completed.projection
        if not isinstance(projection, JustificanteShowPublicResultV1):
            raise ValueError("justificante show projection has an invalid type")
        if projection.bucket_id != str(profile_id) or not projection.snapshot_id.startswith(request.snapshot_id):
            raise ValueError("justificante show result does not match its submitted profile and id")
        Modelo(projection.modelo)
        ObservationSourceKind(projection.source_kind)
        SnapshotLifecycleState(projection.state)
        Period.from_year_and_code(projection.filing_year, projection.period)
        _require_read_receipt(completed)
    except Exception:
        raise _invalid_frame(completed) from None
    return JustificanteShowRead(completion=completed, projection=projection)


__all__ = [
    "JustificanteListRead",
    "JustificanteShowRead",
    "read_justificante_list_for_cli",
    "read_justificante_show_for_cli",
]
