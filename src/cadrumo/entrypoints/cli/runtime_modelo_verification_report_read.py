"""CLI bridges for exact-profile registered verification-report reads."""

from __future__ import annotations

from typing import NoReturn
from uuid import UUID

import typer

from ...application.modelo.verification_report_read_operation import (
    MODELO_VERIFICATION_REPORT_LIST_OPERATION_DEFINITION_ID,
    MODELO_VERIFICATION_REPORT_VIEW_OPERATION_DEFINITION_ID,
    ModeloVerificationReportListProjection,
    ModeloVerificationReportListRequest,
    ModeloVerificationReportViewProjection,
    ModeloVerificationReportViewRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ._modelo_payloads import VerificationReportListResult, VerificationReportShowResult
from ._modelo_rendering import verification_report_lines, verification_report_payload
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import submitted_operation_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation


def _invalid_projection(completed: object) -> NoReturn:
    """Raise one stable CLI refusal when a worker receipt fails correlation."""
    operation_id = getattr(completed, "operation_id", "unknown")
    terminal_condition = getattr(completed, "terminal_condition", None)
    effect = getattr(completed, "effect", None)
    refusal_code = getattr(completed, "refusal_code", None)
    raise submitted_operation_error(
        operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=terminal_condition,
        effect=effect,
        refusal_code=refusal_code,
    )


def read_modelo_verification_report_list(
    ctx: typer.Context,
    *,
    calculation_revision_id: str | None,
) -> tuple[VerificationReportListResult, list[str]]:
    """Return the existing JSON and text renderings from one settled operation."""
    client = bound_profile_client(ctx)
    request = ModeloVerificationReportListRequest(
        profile_id=client.profile_id,
        calculation_revision_id=calculation_revision_id,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_VERIFICATION_REPORT_LIST_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=ModeloVerificationReportListProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    projection = completed.projection
    if not isinstance(projection, ModeloVerificationReportListProjection):
        _invalid_projection(completed)
    try:
        if _verification_list_receipt_invalid(
            completed, projection, client.profile_id, calculation_revision_id
        ) or _verification_list_rows_invalid(projection, calculation_revision_id):
            _invalid_projection(completed)
        reports = tuple(row.to_report() for row in projection.reports)
        result = VerificationReportListResult(
            calculation_revision_id_filter=calculation_revision_id,
            report_count=len(reports),
            reports=[verification_report_payload(report) for report in reports],
        )
        lines = [
            "operation\tmodelo.verification_report.list",
            f"calculation_revision_id_filter\t{calculation_revision_id or ''}",
            f"report_count\t{len(reports)}",
            "verification_report_id\tcalculation_revision_id\tcompleteness_status\tgranted\trun_at\tverified_by",
        ]
        lines.extend(
            "\t".join(
                (
                    report.verification_report_id,
                    report.calculation_revision_id,
                    report.completeness_status.value,
                    str(report.granted_verificado_completo).lower(),
                    report.run_at.isoformat(),
                    report.verified_by,
                )
            )
            for report in reports
        )
    except Exception:
        _invalid_projection(completed)
    return result, lines


def read_modelo_verification_report_view(
    ctx: typer.Context,
    *,
    verification_report_id: str,
) -> tuple[VerificationReportShowResult, list[str]]:
    """Return one renderer-ready report only when the settled receipt matches."""
    client = bound_profile_client(ctx)
    request = ModeloVerificationReportViewRequest(
        profile_id=client.profile_id,
        verification_report_id=verification_report_id,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_VERIFICATION_REPORT_VIEW_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=ModeloVerificationReportViewProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    projection = completed.projection
    if not isinstance(projection, ModeloVerificationReportViewProjection):
        _invalid_projection(completed)
    try:
        if (
            completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or completed.refusal_code is not None
            or completed.effect is not OperationEffect.NONE
            or projection.result_version != 1
            or projection.profile_id != client.profile_id
            or projection.verification_report_id != verification_report_id
            or projection.report.verification_report_id != verification_report_id
        ):
            _invalid_projection(completed)
        report = projection.report.to_report()
        payload = verification_report_payload(report)
        result = VerificationReportShowResult.model_validate(payload.model_dump(mode="python"))
        lines = ["operation\tmodelo.verification_report.show", *verification_report_lines(report)]
    except Exception:
        _invalid_projection(completed)
    return result, lines


__all__ = ["read_modelo_verification_report_list", "read_modelo_verification_report_view"]


def _verification_list_receipt_invalid(
    completed: RegisteredOperationCompletion[ModeloVerificationReportListProjection],
    projection: ModeloVerificationReportListProjection,
    profile_id: UUID,
    calculation_revision_id: str | None,
) -> bool:
    """Require the settled receipt and exact requested profile and revision."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not OperationEffect.NONE
        or (projection.result_version != 1)
        or (projection.profile_id != profile_id)
        or (projection.calculation_revision_id_filter != calculation_revision_id)
    )


def _verification_list_rows_invalid(
    projection: ModeloVerificationReportListProjection, calculation_revision_id: str | None
) -> bool:
    """Require complete unique reports in canonical order within the revision filter."""
    return (
        projection.report_count != len(projection.reports)
        or len({row.verification_report_id for row in projection.reports}) != len(projection.reports)
        or any(
            calculation_revision_id is not None and row.calculation_revision_id != calculation_revision_id
            for row in projection.reports
        )
        or (
            projection.reports
            != tuple(sorted(projection.reports, key=lambda row: (row.calculation_revision_id, row.run_at)))
        )
    )
