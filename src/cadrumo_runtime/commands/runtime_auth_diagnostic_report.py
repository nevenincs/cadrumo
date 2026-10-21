"""Authenticated CLI bridge for the registered auth diagnostic report write."""

from __future__ import annotations

from typing import Never

import typer
from pydantic import ValidationError

from cadrumo.application.auth.diagnostic_report_operation import (
    AUTH_DIAGNOSTIC_NOT_FOUND_REFUSAL_CODE,
    AUTH_DIAGNOSTIC_REPORT_OPERATION_DEFINITION_ID,
    AuthDiagnosticReportProjection,
    AuthDiagnosticReportRequest,
)
from cadrumo.application.auth.diagnostics import AuthDiagnosticPhoneState, AuthDiagnosticReportResult
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.profile_binding import bound_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError


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
        raise RefusalError(RefusalCode.INVALID_FRAME) from None

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
        raise invalid_completion_error(completed)

    if projection.outcome == "prewrite_refusal":
        _raise_diagnostic_not_found(completed, projection, diagnostic_id)

    return _auth_diagnostic_report_result(completed, projection, diagnostic_id, phone_state)


__all__ = ["report_auth_diagnostic_phone_state"]


def _raise_diagnostic_not_found(
    completed: RegisteredOperationCompletion[AuthDiagnosticReportProjection],
    projection: AuthDiagnosticReportProjection,
    diagnostic_id: str,
) -> Never:
    """Present only the correlated unchanged diagnostic-not-found refusal."""
    if (
        completed.terminal_condition is not OperationTerminalCondition.REFUSED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code != AUTH_DIAGNOSTIC_NOT_FOUND_REFUSAL_CODE
        or projection.refusal_code != completed.refusal_code
        or projection.report is not None
    ):
        raise invalid_completion_error(completed)
    raise CliRefusedBoundaryError(
        translated_message="cli.config.auth.diagnostics.not_found",
        context={"diagnostic_id": diagnostic_id},
    )


def _auth_diagnostic_report_result(
    completed: RegisteredOperationCompletion[AuthDiagnosticReportProjection],
    projection: AuthDiagnosticReportProjection,
    diagnostic_id: str,
    phone_state: AuthDiagnosticPhoneState,
) -> AuthDiagnosticReportResult:
    """Require exact diagnostic identity and phone state after successful mutation."""
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
        raise invalid_completion_error(completed)
    return report
