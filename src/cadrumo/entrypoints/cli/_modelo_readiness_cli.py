"""Behavior handlers for modelo readiness commands."""

from __future__ import annotations

import typer

from ...application.operator_actions import ActionReference
from ...application.state_projection import (
    MODELO_READINESS_MISSING_PROFILE_ACTION,
    OPERATOR_ACTION_BY_MODELO_READINESS_BINDING_SOURCE,
    OPERATOR_ACTION_BY_MODELO_READINESS_LEDGER_ISSUE,
    ModeloReadinessRequest,
    ProjectionModeloReadiness,
    build_operator_state_projection,
)
from ...core import (
    ActionArgumentSource,
    ActionArgumentStatus,
    Period,
    PeriodError,
)
from ...core.json_contract import (
    Notice,
    NoticeSeverity,
    ResolvedActionArgument,
)
from ...domain.calculations.registry import RevisionId
from ...domain.user_profile import ProfileNotFoundError
from ._common import _emit_envelope, _no_active_profile_refusal, resolve_notice_action
from ._errors import CliRefusedBoundaryError
from ._modelo_cli_support import unsupported_local_work_period_refusal
from ._modelo_payloads import (
    LedgerIssuePayload,
    ModeloReadinessMissingBindingPayload,
    ModeloReadinessMissingRequirementPayload,
    ModeloReadinessResult,
)


def modelo_readiness(
    ctx: typer.Context,
    modelo: str,
    revision_id: str,
    filing_year: int,
    period: str | None = None,
) -> None:
    """Report active-profile readiness for one modelo target."""
    request = ModeloReadinessRequest(
        modelo=modelo,
        revision_id=revision_id,
        filing_year=filing_year,
        period=_resolve_readiness_period(modelo=modelo, filing_year=filing_year, period=period),
    )
    report = _readiness_report(request)
    readiness_result = _readiness_result(
        report,
        modelo=modelo,
        revision_id=revision_id,
        filing_year=filing_year,
    )
    _emit_envelope(
        ctx,
        command="modelo.readiness",
        result=readiness_result,
        lines=_readiness_lines(
            report,
            modelo=modelo,
            revision_id=revision_id,
            filing_year=filing_year,
            period=period,
        ),
        notices=_readiness_notices(report),
    )


def _resolve_readiness_period(*, modelo: str, filing_year: int, period: str | None) -> Period | None:
    if period is None:
        return None
    try:
        return Period.from_year_and_code(filing_year, period)
    except PeriodError as exc:
        if refusal := unsupported_local_work_period_refusal(modelo=modelo, token=period):
            raise refusal from exc
        raise


def _readiness_report(request: ModeloReadinessRequest) -> ProjectionModeloReadiness:
    from ...core import resolve_active_bucket_id
    from ...core.i18n import tr as _tr

    if resolve_active_bucket_id() is None:
        raise _no_active_profile_refusal()
    try:
        projection = build_operator_state_projection(modelo_readiness_requests=(request,))
    except ProfileNotFoundError as exc:
        raise CliRefusedBoundaryError(
            _tr("cli.config.profile.unknown_profile", name=resolve_active_bucket_id() or ""),
        ) from exc
    if not projection.modelo_readiness:
        raise CliRefusedBoundaryError(_tr("cli.config.errors.no_active_profile"))
    return projection.modelo_readiness[0]


def _readiness_result(
    report: ProjectionModeloReadiness,
    *,
    modelo: str,
    revision_id: RevisionId,
    filing_year: int,
) -> ModeloReadinessResult:
    return ModeloReadinessResult(
        profile_id=str(report.profile_id),
        modelo=modelo,
        revision_id=revision_id,
        filing_year=filing_year,
        period=report.period,
        ready=report.ready,
        profile_ready=report.profile_ready,
        profile_refusal=report.profile_refusal,
        registry_ready=report.registry_ready,
        registry_refusal=report.registry_refusal,
        binding_ready=report.binding_ready,
        missing=[
            ModeloReadinessMissingRequirementPayload(
                section_key=req.section_key,
                field_key=req.field_key,
                selector=req.selector,
                label=req.label,
                legal_refs=list(req.legal_refs),
                modelos=list(req.modelos),
                operator_action=MODELO_READINESS_MISSING_PROFILE_ACTION,
            )
            for req in report.missing
        ],
        missing_bindings=[
            ModeloReadinessMissingBindingPayload(
                binding_id=req.binding_id,
                source=req.source,
                input_channel=req.input_channel,
                operator_action=OPERATOR_ACTION_BY_MODELO_READINESS_BINDING_SOURCE[req.source],
            )
            for req in report.missing_bindings
        ],
        ledger_preflight_required=report.ledger_preflight_required,
        ledger_ready=report.ledger_ready,
        ledger_period=report.ledger_period,
        ledger_checked_transaction_count=report.ledger_checked_transaction_count,
        ledger_issues=[
            LedgerIssuePayload(
                transaction_id=issue.transaction_id,
                reason=issue.reason.value,
                detail=issue.detail,
                operator_action=OPERATOR_ACTION_BY_MODELO_READINESS_LEDGER_ISSUE[issue.reason],
            )
            for issue in report.ledger_issues
        ],
    )


def _readiness_lines(
    report: ProjectionModeloReadiness,
    *,
    modelo: str,
    revision_id: RevisionId,
    filing_year: int,
    period: str | None,
) -> list[str]:
    export_context = _export_readiness_context(report)
    lines = [
        f"profile_id\t{report.profile_id}",
        f"modelo\t{modelo}",
        f"revision_id\t{revision_id}",
        f"filing_year\t{filing_year}",
        f"period\t{period or ''}",
        "readiness_scope\tprofile_and_source_preflight_not_manual_casilla_completeness",
        f"ready\t{report.ready}",
        f"profile_ready\t{report.profile_ready}",
        f"profile_refusal\t{report.profile_refusal}",
        f"registry_ready\t{report.registry_ready}",
        f"registry_refusal\t{report.registry_refusal}",
        f"binding_ready\t{report.binding_ready}",
        f"source_binding_ready\t{report.binding_ready}",
        f"missing\t{len(report.missing)}",
        f"missing_bindings\t{len(report.missing_bindings)}",
    ]
    if report.missing_bindings:
        command_period = period or report.period.registry_token
        lines.append(
            "missing_bindings_command\t"
            f"aeat app modelo bindings list --modelo {modelo} --year {filing_year} "
            f"--period {command_period} --missing",
        )
    lines.extend(_readiness_ledger_export_lines(report, export_context))
    lines.extend(_readiness_detail_lines(report))
    if _ledger_ready_but_bindings_missing(report):
        lines.append(
            "readiness_note\tledger_ready only means the period ledger rows passed transaction preflight; "
            "missing_bindings/source_binding_ready still decide source completeness.",
        )
    return lines


def _readiness_ledger_export_lines(
    report: ProjectionModeloReadiness,
    export_context: dict[str, str] | None,
) -> list[str]:
    return [
        f"ledger_preflight_required\t{report.ledger_preflight_required}",
        f"ledger_ready\t{report.ledger_ready if report.ledger_ready is not None else ''}",
        "ledger_ready_scope\ttransaction_preflight_only",
        f"ledger_period\t{report.ledger_period or ''}",
        f"ledger_checked\t{report.ledger_checked_transaction_count}",
        f"ledger_issues\t{len(report.ledger_issues)}",
        f"export_ready\t{export_context is None}",
        f"export_refusal\t{export_context['reason'] if export_context is not None else ''}",
        _readiness_finish_line(export_context),
    ]


def _readiness_detail_lines(report: ProjectionModeloReadiness) -> list[str]:
    lines: list[str] = []
    for requirement in report.missing:
        legal_refs = ", ".join(requirement.legal_refs) or "-"
        modelos = ", ".join(requirement.modelos) or "-"
        lines.append(
            f"{requirement.section_key}.{requirement.field_key}\t{requirement.selector}\t"
            f"{requirement.label}\t{legal_refs}\t{modelos}",
        )
    lines.extend(
        f"missing_binding\t{binding.binding_id}\t{binding.source}\t{binding.input_channel}"
        for binding in report.missing_bindings
    )
    lines.extend(
        f"ledger_issue\t{issue.transaction_id}\t{issue.reason.value}\t{issue.detail}" for issue in report.ledger_issues
    )
    return lines


def _readiness_notices(report: ProjectionModeloReadiness) -> tuple[Notice, ...]:
    notices: list[Notice] = []
    if not report.per_operation_requirements_assessed:
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="modelo.readiness.per_operation_axis_not_assessed",
                message=(
                    f"No schema-required profile field is currently declared for Modelo {report.modelo}, so "
                    "profile_ready reflects only the export-identity and conditional checks, not a per-modelo "
                    "assessment. Do not read profile_ready as a complete check for this modelo."
                ),
                context={"modelo": report.modelo, "profile_ready": str(report.profile_ready)},
            ),
        )
    if _ledger_ready_but_bindings_missing(report):
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="modelo.readiness.ledger_preflight_scope",
                message=(
                    "ledger_ready only means the period ledger rows passed transaction preflight; "
                    "missing_bindings/source_binding_ready still decide source completeness."
                ),
                context={
                    "ledger_ready": "true",
                    "binding_ready": "false",
                    "missing_bindings": str(len(report.missing_bindings)),
                },
            ),
        )
    if export_context := _export_readiness_context(report):
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="modelo.readiness.export_unsupported",
                message=(
                    f"Modelo {report.modelo} cannot produce a local fichero-BOE export: {export_context['reason']}."
                ),
                action=resolve_notice_action(
                    action=ActionReference(action_id="operator.modelo.describe"),
                    argument_bindings=(
                        ResolvedActionArgument(
                            argument_name="modelo",
                            status=ActionArgumentStatus.RESOLVED,
                            value=report.modelo,
                            source=ActionArgumentSource.VERDICT_CONTEXT,
                            source_key="modelo",
                        ),
                    ),
                ),
                context=export_context,
            ),
        )
    return tuple(notices)


def _ledger_ready_but_bindings_missing(report: ProjectionModeloReadiness) -> bool:
    return report.ledger_ready is True and not report.binding_ready and bool(report.missing_bindings)


def _export_readiness_context(report: ProjectionModeloReadiness) -> dict[str, str] | None:
    if not report.registry_ready:
        return None
    from ...application.filing import build_runtime_schema_provider, export_layout_renderability_reason

    provider = build_runtime_schema_provider(
        filing_year=report.period.filing_year,
        period=report.period,
        modelos=(report.modelo,),
    )
    subview = provider.get_subview(report.modelo)
    layout = subview.export_layouts[0] if subview.export_layouts else None
    reason = export_layout_renderability_reason(report.modelo, layout)
    if reason is None:
        return None
    context = {
        "modelo": str(report.modelo),
        "reason": reason,
    }
    if layout is not None:
        context["layout_id"] = str(layout.id)
        context["layout_format"] = str(layout.format)
    return context


def _readiness_finish_line(export_context: dict[str, str] | None) -> str:
    if export_context is not None:
        return "finish_line\tlocal calculation, verification, and internal filing only; fichero-BOE export unsupported"
    return "finish_line\texport verified-complete revision via 'aeat app modelo export' (local finish line)"


__all__ = ["modelo_readiness"]
