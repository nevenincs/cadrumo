"""CLI transport for an authenticated work-unit history snapshot."""

from __future__ import annotations

from uuid import UUID

import typer

from ...application.modelo.history import WorkUnitHistory
from ...application.modelo.history_operation import (
    MODELO_WORK_HISTORY_OPERATION_DEFINITION_ID,
    ModeloWorkHistoryProjection,
    ModeloWorkHistoryRequest,
)
from ...core.operations import OperationEffect
from ...domain.modelos.work_unit import WorkUnit
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


def read_modelo_work_history(ctx: typer.Context, *, unit: WorkUnit) -> WorkUnitHistory:
    """Read only the profile and work identity already selected through the runtime."""
    client = require_profile_client(ctx, expected_profile_id=UUID(unit.bucket_id))
    completed = run_registered_operation(
        client,
        ModeloWorkHistoryRequest(profile_id=client.profile_id, work_unit_id=unit.work_unit_id),
        definition_id=MODELO_WORK_HISTORY_OPERATION_DEFINITION_ID,
        subject_ref=unit.work_unit_id,
        result_type=ModeloWorkHistoryProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    projection = completed.projection
    if (
        projection.profile_id != client.profile_id
        or projection.history.bucket_id != unit.bucket_id
        or projection.history.work_unit_id != unit.work_unit_id
        or completed.effect is not OperationEffect.NONE
    ):
        raise invalid_completion_error(completed)
    return projection.history.to_history()
