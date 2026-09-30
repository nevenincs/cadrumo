"""Exact-profile submission of local export through the shared runtime."""

from __future__ import annotations

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.modelo.export_projection import ModeloExportPublicResultV3
from ...application.modelo.operation_definitions import MODELO_EXPORT_OPERATION_DEFINITION_ID, ModeloExportRequest
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.modelo_export_artefact import ModeloExportArtefact
from ...core.operations import OperationEffect, OperationTerminalCondition
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


def run_modelo_export(
    client: RuntimeFrontendClient,
    request: ModeloExportRequest,
    *,
    work_unit_id: str,
    timeout: float = 120,
) -> RegisteredOperationCompletion[ModeloExportPublicResultV3]:
    """Export one selected revision and validate the worker's publication receipt."""
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_EXPORT_OPERATION_DEFINITION_ID,
        subject_ref=work_unit_id,
        result_type=ModeloExportPublicResultV3,
        request_version=3,
        result_version=3,
        timeout=timeout,
    )
    projection = completed.projection
    receipt = projection.fichero_boe if projection.fichero_boe is not None else projection.calculation_report
    if (
        projection.artefact is not request.artefact
        or projection.calculation_revision_id != request.calculation_revision_id
        or projection.output_path != request.output_path
        or receipt is None
        or (projection.fichero_boe is not None and projection.fichero_boe.bucket_id != str(client.profile_id))
        or receipt.work_unit_id != work_unit_id
        or (
            request.artefact is not ModeloExportArtefact.FICHERO_BOE
            and (
                projection.calculation_report is None
                or projection.calculation_report.report_language != request.report_language
            )
        )
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.UPDATED
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    return completed
