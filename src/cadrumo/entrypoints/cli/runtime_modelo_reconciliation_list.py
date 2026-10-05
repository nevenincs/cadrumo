"""CLI bridge for worker-owned, exact-profile modelo reconciliation history."""

from __future__ import annotations

from uuid import UUID

import typer

from ...application.modelo.reconciliation_list_operation import (
    MODELO_RECONCILIATION_LIST_OPERATION_DEFINITION_ID,
    ModeloReconciliationListProjection,
    ModeloReconciliationListRequest,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation


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
    if _reconciliation_list_receipt_invalid(
        completed, projection, client.profile_id, scoped_work_unit_id
    ) or _reconciliation_list_rows_invalid(projection, profile_id, scoped_work_unit_id):
        raise invalid_completion_error(completed)
    return projection


__all__ = ["read_modelo_reconciliation_list"]


def _reconciliation_list_receipt_invalid(
    completed: RegisteredOperationCompletion[ModeloReconciliationListProjection],
    projection: ModeloReconciliationListProjection,
    profile_uuid: UUID,
    scoped_work_unit_id: str | None,
) -> bool:
    """Correlate the successful list receipt, exact selector, and complete result count."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.NONE
        or (projection.profile_id != profile_uuid)
        or (projection.work_unit_id != scoped_work_unit_id)
        or (projection.reconciliation_count != len(projection.reconciliations))
    )


def _reconciliation_list_rows_invalid(
    projection: ModeloReconciliationListProjection, profile_id: str, scoped_work_unit_id: str | None
) -> bool:
    """Require every reconciliation row to belong to the requested profile and work unit."""
    return any(row.bucket_id != profile_id for row in projection.reconciliations) or (
        scoped_work_unit_id is not None
        and any(row.work_unit_id != scoped_work_unit_id for row in projection.reconciliations)
    )
