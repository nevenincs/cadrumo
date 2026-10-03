"""CLI bridges for exact-profile registered verification-report reads."""

from __future__ import annotations

from decimal import Decimal
from typing import NoReturn

import typer

from ...application.modelo.verification_report_read_operation import (
    MODELO_VERIFICATION_REPORT_LIST_OPERATION_DEFINITION_ID,
    MODELO_VERIFICATION_REPORT_VIEW_OPERATION_DEFINITION_ID,
    ModeloVerificationFactProjection,
    ModeloVerificationReportListProjection,
    ModeloVerificationReportListRequest,
    ModeloVerificationReportProjection,
    ModeloVerificationReportViewProjection,
    ModeloVerificationReportViewRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.modelos.verification_report import ModeloVerificationFinding, VerificationReport
from ._modelo_payloads import VerificationReportListResult, VerificationReportShowResult
from ._modelo_rendering import verification_report_lines, verification_report_payload
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


def _to_domain_report(projection: ModeloVerificationReportProjection) -> VerificationReport:
    """Restore the canonical report so the existing renderer owns localization."""
    findings = tuple(
        ModeloVerificationFinding(
            kind=finding.kind,
            severity=finding.severity,
            casilla_id=finding.casilla_id,
            expectation_id=finding.expectation_id,
            message_locale_key=finding.message_locale_key,
            message_facts=_facts_by_key(finding.message_facts),
            legal_refs=finding.legal_refs,
            source_refs=finding.source_refs,
        )
        for finding in projection.findings
    )
    snapshot = projection.registry_snapshot_ref
    return VerificationReport(
        verification_report_id=projection.verification_report_id,
        calculation_revision_id=projection.calculation_revision_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=snapshot.modelo,
            revision_id=snapshot.revision_id,
            modelo_year=snapshot.modelo_year,
            period=snapshot.period,
        ),
        completeness_status=projection.completeness_status,
        findings=findings,
        resolved_casilla_ids=projection.resolved_casilla_ids,
        missing_required_casilla_ids=projection.missing_required_casilla_ids,
        run_at=projection.run_at,
        verified_by=projection.verified_by,
        granted_verificado_completo=projection.granted_verificado_completo,
    )


def _facts_by_key(facts: tuple[ModeloVerificationFactProjection, ...]) -> dict[str, str | int | bool | Decimal]:
    """Rebuild typed message arguments for the domain finding validator."""
    return {fact.key: Decimal(str(fact.value)) if fact.value_kind == "decimal" else fact.value for fact in facts}


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
        if (
            completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or completed.refusal_code is not None
            or completed.effect is not OperationEffect.NONE
            or projection.result_version != 1
            or projection.profile_id != client.profile_id
            or projection.calculation_revision_id_filter != calculation_revision_id
            or projection.report_count != len(projection.reports)
            or len({row.verification_report_id for row in projection.reports}) != len(projection.reports)
            or any(
                calculation_revision_id is not None and row.calculation_revision_id != calculation_revision_id
                for row in projection.reports
            )
            or projection.reports
            != tuple(sorted(projection.reports, key=lambda row: (row.calculation_revision_id, row.run_at)))
        ):
            _invalid_projection(completed)
        reports = tuple(_to_domain_report(row) for row in projection.reports)
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
        report = _to_domain_report(projection.report)
        payload = verification_report_payload(report)
        result = VerificationReportShowResult.model_validate(payload.model_dump(mode="python"))
        lines = ["operation\tmodelo.verification_report.show", *verification_report_lines(report)]
    except Exception:
        _invalid_projection(completed)
    return result, lines


__all__ = ["read_modelo_verification_report_list", "read_modelo_verification_report_view"]
