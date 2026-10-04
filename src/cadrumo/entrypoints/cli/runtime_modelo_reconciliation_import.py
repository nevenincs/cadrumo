"""CLI transport for worker-owned local reconciliation imports."""

from __future__ import annotations

from pathlib import Path

import typer

from ...application.modelo.reconciliation import ModeloReconciliationReport
from ...application.modelo.reconciliation_import_operation import (
    MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID,
    ModeloReconciliationImportProjection,
    ModeloReconciliationImportRequest,
)
from ...application.modelo.reconciliation_records import ModeloReconciliationEvidenceKind
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ._modelo_behavior_support import resolve_optional_cli_period
from ._modelo_cli_support import validate_work_unit_selector
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation


def import_modelo_reconciliation(
    ctx: typer.Context,
    *,
    file: Path,
    source_kind: ModeloReconciliationEvidenceKind,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: str | None,
    revision: str | None,
    bucket_id: str | None,
    actor: str,
    calculation_revision: str | None = None,
) -> ModeloReconciliationReport:
    """Select and reconcile inside the invocation's exact profile worker."""
    client = bound_profile_client(ctx)
    profile_id = str(client.profile_id)
    if bucket_id is not None and bucket_id != profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    source_path = str(file.resolve())
    selected_id = validate_work_unit_selector(work_unit_id) if work_unit_id is not None else None
    resolved_period = resolve_optional_cli_period(year=year, period=period, modelo=modelo)
    request = ModeloReconciliationImportRequest(
        profile_id=client.profile_id,
        work_unit_id=selected_id,
        modelo=modelo,
        filing_year=year,
        period=resolved_period.registry_token if resolved_period is not None else None,
        revision_id=revision,
        bucket_id=bucket_id,
        source_kind=source_kind,
        source_path=source_path,
        actor=actor,
        calculation_revision_id=calculation_revision,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(profile_id),
        result_type=ModeloReconciliationImportProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    if calculation_revision is not None and projection.calculation_revision_id != calculation_revision:
        raise invalid_completion_error(completed)
    if _reconciliation_import_receipt_invalid(completed, projection, profile_id, source_kind, source_path, selected_id):
        raise invalid_completion_error(completed)
    return projection.to_report()


__all__ = ["import_modelo_reconciliation"]


def _reconciliation_import_receipt_invalid(
    completed: RegisteredOperationCompletion[ModeloReconciliationImportProjection],
    projection: ModeloReconciliationImportProjection,
    profile_id: str,
    source_kind: ModeloReconciliationEvidenceKind,
    source_path: str,
    selected_id: str | None,
) -> bool:
    """Require the submitted source, requested work selection, and profile-owned mutation receipt."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.UPDATED
        or (projection.bucket_id != profile_id)
        or (projection.source_kind is not source_kind)
        or (projection.source_path != source_path)
        or (selected_id is not None and len(selected_id) != 12 and (projection.work_unit_id != selected_id))
    )
