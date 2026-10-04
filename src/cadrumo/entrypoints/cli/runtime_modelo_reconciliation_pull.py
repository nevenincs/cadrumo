"""CLI chain for exact-profile receipt capture and local reconciliation."""

from __future__ import annotations

from pathlib import Path

import typer

from ...application.modelo.reconciliation import ModeloReconciliationReport
from ...application.modelo.reconciliation_import_operation import ModeloReconciliationImportProjection
from ...application.modelo.reconciliation_pull_operation import (
    MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID,
    ModeloReconciliationPullRequest,
    reconciliation_pull_source_ref,
)
from ...application.modelo.reconciliation_records import ModeloReconciliationEvidenceKind
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.config import load_settings
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .registered_operation_errors import invalid_completion_error
from .runtime_filed_single import read_filed_single_capture_for_cli
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
    source: ModeloReconciliationEvidenceKind = ModeloReconciliationEvidenceKind.JUSTIFICANTE,
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

    snapshot_id = None
    observation_id = None
    if source is ModeloReconciliationEvidenceKind.DECLARATION:
        captured = read_filed_single_capture_for_cli(
            ctx,
            modelo=str(unit.modelo),
            year=unit.filing_year,
            output_root=load_settings().cadrumo_filed_declarations_dir,
            period=unit.period,
            expediente_id=None,
            limit=1,
            expected_profile_id=client.profile_id,
        ).report
        if captured.captured_count != 1 or len(captured.observation_paths) != 1 or captured.casilla_count == 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        observation_id = Path(captured.observation_paths[0]).name
    else:
        capture = capture_justificante_for_cli(
            ctx,
            profile_id=client.profile_id,
            modelo=str(unit.modelo),
            year=unit.filing_year,
            period=unit.period,
        ).projection
        snapshot_id = capture.snapshot_id
    request = ModeloReconciliationPullRequest(
        profile_id=client.profile_id,
        work_unit_id=unit.work_unit_id,
        snapshot_id=snapshot_id,
        observation_id=observation_id,
        source_kind=source,
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
    expected_source = reconciliation_pull_source_ref(source, snapshot_id, observation_id)
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.UPDATED
        or projection.bucket_id != profile_id
        or projection.work_unit_id != unit.work_unit_id
        or projection.source_kind is not source
        or projection.source_path != expected_source
    ):
        raise invalid_completion_error(completed)
    return projection.to_report()


__all__ = ["pull_modelo_reconciliation"]
