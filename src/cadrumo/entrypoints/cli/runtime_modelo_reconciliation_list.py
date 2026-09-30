"""CLI bridge for worker-owned, exact-profile modelo reconciliation history."""

from __future__ import annotations

import typer

from ...application.modelo.reconciliation_list_operation import (
    MODELO_RECONCILIATION_LIST_OPERATION_DEFINITION_ID,
    ModeloReconciliationListProjection,
    ModeloReconciliationListRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


def read_modelo_reconciliation_list(
    ctx: typer.Context,
    *,
    work_unit_id: str | None,
) -> ModeloReconciliationListProjection:
    """Return one settled worker snapshot for the invocation's bound profile."""
    client = bound_profile_client(ctx)
    profile_id = str(client.profile_id)
    scoped_work_unit_id = work_unit_id.strip() if work_unit_id and work_unit_id.strip() else None
    request = ModeloReconciliationListRequest(
        profile_id=client.profile_id,
        work_unit_id=scoped_work_unit_id,
    )
    subject_ref = profile_operation_subject(str(client.profile_id))
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_RECONCILIATION_LIST_OPERATION_DEFINITION_ID,
        subject_ref=subject_ref,
        result_type=ModeloReconciliationListProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    projection = completed.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.NONE
        or projection.profile_id != client.profile_id
        or projection.work_unit_id != scoped_work_unit_id
        or projection.reconciliation_count != len(projection.reconciliations)
        or any(row.bucket_id != profile_id for row in projection.reconciliations)
        or (
            scoped_work_unit_id is not None
            and any(row.work_unit_id != scoped_work_unit_id for row in projection.reconciliations)
        )
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
        )
    return projection


__all__ = ["read_modelo_reconciliation_list"]
