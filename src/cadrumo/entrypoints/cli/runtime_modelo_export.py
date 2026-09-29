"""Exact-profile submission of local export through the shared runtime."""

from __future__ import annotations

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.modelo.export_projection import ModeloExportPublicResultV2
from ...application.modelo.operation_definitions import MODELO_EXPORT_OPERATION_DEFINITION_ID, ModeloExportRequest
from ...application.runtime.contracts import RuntimeRefusalCode
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
) -> RegisteredOperationCompletion[ModeloExportPublicResultV2]:
    """Export one selected revision and validate the worker's publication receipt."""
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_EXPORT_OPERATION_DEFINITION_ID,
        subject_ref=work_unit_id,
        result_type=ModeloExportPublicResultV2,
        request_version=2,
        result_version=2,
        timeout=timeout,
    )
    projection = completed.projection
    if (
        not isinstance(projection, ModeloExportPublicResultV2)
        or projection.bucket_id != str(client.profile_id)
        or projection.work_unit_id != work_unit_id
        or projection.calculation_revision_id != request.calculation_revision_id
        or projection.output_path != request.output_path
        or completed.effect is not OperationEffect.UPDATED
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=completed.effect,
        )
    return completed
