"""CLI chain for exact-profile receipt capture and local reconciliation."""

from __future__ import annotations

import typer

from ...application.live.justificante import JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE
from ...application.modelo.reconciliation import ModeloReconciliationReport
from ...application.modelo.reconciliation_import_operation import ModeloReconciliationImportProjection
from ...application.modelo.reconciliation_pull_operation import (
    MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID,
    ModeloReconciliationPullRequest,
)
from ...application.modelo.reconciliation_records import ModeloReconciliationEvidenceKind
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .registered_operation_errors import invalid_completion_error
from .runtime_justificante_capture import capture_justificante_for_cli
from .runtime_modelo_metadata import read_modelo_work_unit
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation


def pull_modelo_reconciliation(
    ctx: typer.Context,
    *,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: str | None,
    revision: str | None,
    bucket_id: str | None,
    actor: str,
) -> ModeloReconciliationReport:
    """Resolve, capture and compare without ambient profile storage access."""
    client = bound_profile_client(ctx)
    profile_id = str(client.profile_id)
    unit = read_modelo_work_unit(
        ctx,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
        expected_profile_id=client.profile_id,
    )
    if unit.bucket_id != profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)

    capture = capture_justificante_for_cli(
        ctx,
        profile_id=client.profile_id,
        modelo=str(unit.modelo),
        year=unit.filing_year,
        period=unit.period,
    ).projection
    request = ModeloReconciliationPullRequest(
        profile_id=client.profile_id,
        work_unit_id=unit.work_unit_id,
        snapshot_id=capture.snapshot_id,
        actor=actor,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(profile_id),
        result_type=ModeloReconciliationImportProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    expected_source = f"secure-object://{JUSTIFICANTE_CAPTURE_SNAPSHOT_NAMESPACE}/{capture.snapshot_id}"
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.UPDATED
        or projection.bucket_id != profile_id
        or projection.work_unit_id != unit.work_unit_id
        or projection.source_kind is not ModeloReconciliationEvidenceKind.JUSTIFICANTE
        or projection.source_path != expected_source
    ):
        raise invalid_completion_error(completed)
    return projection.to_report()


__all__ = ["pull_modelo_reconciliation"]
