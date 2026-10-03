"""CLI bridge for worker-owned, exact-profile Modelo work inventory."""

from __future__ import annotations

from uuid import UUID

import typer

from ...adapters.local_runtime.frontend_client import RuntimeFrontendRefusedError
from ...application.modelo.work_inventory_operation import (
    MODELO_WORK_LIST_OPERATION_DEFINITION_ID,
    ModeloWorkListProjection,
    ModeloWorkListRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...application.user_profile.access_contracts import AccessDenialCode
from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.modelos.work_unit import WorkUnit, WorkUnitState
from .common import no_active_profile_refusal
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


def read_modelo_work_inventory(
    ctx: typer.Context, *, bucket_id: str | None, include_discarded: bool
) -> tuple[WorkUnit, ...]:
    """Return the admitted worker snapshot in canonical lifecycle order."""
    target = resolve_active_bucket_id()
    if target is None:
        raise no_active_profile_refusal()
    client = require_profile_client(ctx, expected_profile_id=UUID(target))
    if bucket_id is not None and bucket_id.strip() and bucket_id.strip() != str(client.profile_id):
        raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
    completed = run_registered_operation(
        client,
        ModeloWorkListRequest(profile_id=client.profile_id, include_discarded=include_discarded),
        definition_id=MODELO_WORK_LIST_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=ModeloWorkListProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    projection = completed.projection
    if (
        projection.profile_id != client.profile_id
        or projection.include_discarded is not include_discarded
        or completed.effect is not OperationEffect.NONE
        or any(row.bucket_id != str(client.profile_id) for row in projection.units)
        or (not include_discarded and any(row.state is not WorkUnitState.BORRADOR for row in projection.units))
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=completed.effect,
        )
    return tuple(row.to_work_unit() for row in projection.units)
