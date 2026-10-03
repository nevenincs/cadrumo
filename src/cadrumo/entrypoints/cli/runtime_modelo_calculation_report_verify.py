"""Receipt-bound CLI access to calculation-summary store verification."""

from __future__ import annotations

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.modelo.calculation_report_verification_operation import (
    MODELO_CALCULATION_REPORT_VERIFY_OPERATION_DEFINITION_ID,
    ModeloCalculationReportVerificationProjection,
    ModeloCalculationReportVerificationRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_registered_operation import run_registered_operation


def run_modelo_calculation_report_verify(
    client: RuntimeFrontendClient,
    request: ModeloCalculationReportVerificationRequest,
    *,
    timeout: float = 120,
) -> RegisteredOperationCompletion[ModeloCalculationReportVerificationProjection]:
    """Verify the exact document against the admitted profile's canonical store."""
    if request.profile_id != client.profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_CALCULATION_REPORT_VERIFY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=ModeloCalculationReportVerificationProjection,
        request_version=1,
        result_version=1,
        timeout=timeout,
    )
    projection = completed.projection
    if (
        projection.profile_id != client.profile_id
        or projection.source_sha256 != request.source_sha256
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.NONE
    ):
        raise invalid_completion_error(completed)
    return completed
