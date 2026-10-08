"""Exact-profile submission of local export through the shared runtime."""

from __future__ import annotations

from uuid import UUID

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.modelo.export_projection import (
    ModeloCalculationReportPublicReceipt,
    ModeloExportPublicResultV3,
    ModeloFicheroBoePublicReceipt,
)
from ...application.modelo.operation_definitions import MODELO_EXPORT_OPERATION_DEFINITION_ID
from ...application.modelo.work_export_contracts import ModeloExportRequest
from ...core.modelo_export_artefact import ModeloExportArtefact
from ...core.operations import OperationEffect, OperationTerminalCondition
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_registered_operation import run_registered_operation


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
        _export_request_differs(projection, request)
        or receipt is None
        or _export_content_invalid(projection, request, receipt, client.profile_id, work_unit_id)
        or _export_receipt_invalid(completed)
    ):
        raise invalid_completion_error(completed)
    return completed


def _export_request_differs(projection: ModeloExportPublicResultV3, request: ModeloExportRequest) -> bool:
    """Require the requested artefact, exact calculation revision, and output path."""
    return (
        projection.artefact is not request.artefact
        or projection.calculation_revision_id != request.calculation_revision_id
        or projection.output_path != request.output_path
    )


def _export_content_invalid(
    projection: ModeloExportPublicResultV3,
    request: ModeloExportRequest,
    receipt: ModeloFicheroBoePublicReceipt | ModeloCalculationReportPublicReceipt,
    profile_id: UUID,
    work_unit_id: str,
) -> bool:
    """Correlate the profile-owned export receipt and requested report language."""
    return (
        (projection.fichero_boe is not None and projection.fichero_boe.bucket_id != str(profile_id))
        or receipt.work_unit_id != work_unit_id
        or (
            request.artefact is not ModeloExportArtefact.FICHERO_BOE
            and (
                projection.calculation_report is None
                or projection.calculation_report.report_language != request.report_language
            )
        )
    )


def _export_receipt_invalid(completed: RegisteredOperationCompletion[ModeloExportPublicResultV3]) -> bool:
    """Require a successful mutation receipt without a refusal code."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.UPDATED
    )
