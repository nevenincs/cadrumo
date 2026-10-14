"""Receipt-bound CLI access to calculation-summary store verification."""

from __future__ import annotations

from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient

from ...application.modelo.calculation_report_verification_operation import (
    MODELO_CALCULATION_REPORT_VERIFY_OPERATION_DEFINITION_ID,
    ModeloCalculationReportVerificationProjection,
    ModeloCalculationReportVerificationRequest,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject


def run_modelo_calculation_report_verify(
    client: FrontendClient,
    request: ModeloCalculationReportVerificationRequest,
    *,
    timeout: float = 120,
) -> RegisteredOperationCompletion[ModeloCalculationReportVerificationProjection]:
    """Verify the exact document against the admitted profile's canonical store."""
    if request.profile_id != client.profile_id:
        raise RefusalError(RefusalCode.INVALID_FRAME)
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
        or (request.source_sha256 is not None and projection.source_sha256 != request.source_sha256)
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.NONE
    ):
        raise invalid_completion_error(completed)
    return completed
