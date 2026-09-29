"""Exact-profile CLI bridge for the six recorded overview read leaves."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import typer

from ...application.overview.read_operation import (
    OVERVIEW_READ_DEFINITION_IDS,
    OverviewReadPayload,
    OverviewReadProjection,
    OverviewReadRequest,
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
class OverviewReadCompletion:
    """Preserve the known operation receipt through CLI rendering."""

    completion: RegisteredOperationCompletion[OverviewReadProjection]
    payload: OverviewReadPayload


def read_overview(ctx: typer.Context, *, request: OverviewReadRequest) -> OverviewReadCompletion:
    """Read one closed overview snapshot through the selected profile worker."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    if request.profile_id != client.profile_id:
        raise ValueError("overview query profile differs from the selected session")
    completed = run_registered_operation(
        client,
        request,
        definition_id=OVERVIEW_READ_DEFINITION_IDS[request.kind],
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=OverviewReadProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    if (
        projection.profile_id != client.profile_id
        or projection.request != request
        or projection.payload.kind != request.kind.value
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    return OverviewReadCompletion(completion=completed, payload=projection.payload)


__all__ = ["OverviewReadCompletion", "read_overview"]
