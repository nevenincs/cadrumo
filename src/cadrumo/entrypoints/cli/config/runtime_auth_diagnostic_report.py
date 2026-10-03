"""Authenticated CLI bridge for the registered auth diagnostic report write."""

from __future__ import annotations

from typing import Never

import typer
from pydantic import BaseModel, ValidationError

from ....application.auth.diagnostic_report_operation import (
    AUTH_DIAGNOSTIC_NOT_FOUND_REFUSAL_CODE,
    AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID,
    AuthDiagnosticReportProjection,
    AuthDiagnosticReportRequest,
)
from ....application.auth.diagnostics import AuthDiagnosticPhoneState, AuthDiagnosticReportResult
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..errors import CliRefusedBoundaryError
from ..runtime_profile_binding import bound_profile_client
from ..runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


def _invalid[ProjectionT: BaseModel](completed: RegisteredOperationCompletion[ProjectionT]) -> Never:
    """Refuse a worker result that does not correlate with its registered receipt."""
    raise submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


def report_auth_diagnostic_phone_state(
    ctx: typer.Context,
    *,
    diagnostic_id: str,
    phone_state: AuthDiagnosticPhoneState,
) -> AuthDiagnosticReportResult:
    """Record one operator report for the exact authenticated profile."""
    if not 1 <= len(diagnostic_id) <= 128:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.auth.diagnostics.not_found",
            context={"diagnostic_id": diagnostic_id},
        )

    client = bound_profile_client(ctx)
    try:
        request = AuthDiagnosticReportRequest(
            profile_id=client.profile_id,
            diagnostic_id=diagnostic_id,
            phone_state=phone_state,
        )
    except ValidationError:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None

    completed = run_registered_operation(
        client,
        request,
        definition_id=AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=AuthDiagnosticReportProjection,
        request_version=1,
        result_version=1,
        timeout=60,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    if (
        projection.profile_id != client.profile_id
        or str(projection.operation_id) != AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID
        or projection.effect is not completed.effect
    ):
        _invalid(completed)

    if projection.outcome == "prewrite_refusal":
        if (
            completed.terminal_condition is not OperationTerminalCondition.REFUSED
            or completed.effect is not OperationEffect.NONE
            or completed.refusal_code != AUTH_DIAGNOSTIC_NOT_FOUND_REFUSAL_CODE
            or projection.refusal_code != completed.refusal_code
            or projection.report is not None
        ):
            _invalid(completed)
        raise CliRefusedBoundaryError(
            translated_message="cli.config.auth.diagnostics.not_found",
            context={"diagnostic_id": diagnostic_id},
        )

    report = projection.report
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.UPDATED
        or completed.refusal_code is not None
        or projection.outcome != "completed"
        or projection.refusal_code is not None
        or report is None
        or report.diagnostic_id != diagnostic_id
        or report.phone_state is not phone_state
    ):
        _invalid(completed)
    return report


__all__ = ["report_auth_diagnostic_phone_state"]
