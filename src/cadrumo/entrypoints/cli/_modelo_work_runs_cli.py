"""Behavior for modelo workflow-run discovery and resume.

This CLI module is a transport boundary for persisted
:class:`WorkflowResult` rows. The ``runs`` command
renders local run history from :func:`list_runs`; the
``resume`` command validates operator selectors, delegates target resolution to
:func:`resolve_modelo_workflow_resume_target`, and
passes the selected run id to
:func:`resume_modelo_workflow`.

Resume output combines the resumable
:class:`WorkflowResumeContext` with the selector
metadata carried by
:class:`WorkflowResumeTargetResolution`. No command in
this module contacts AEAT or mutates workflow, bucket, or modelo state.

See Also:
    :mod:`workflow`:
        Public workflow facade that owns run persistence and resume validation.
    :mod:`modelo`:
        Public modelo facade used indirectly by workflow resume resolution for
        visible filing targets, exact work-unit targets, and revision selectors.
"""

from __future__ import annotations

from typing import NamedTuple

import typer

from cadrumo.application.workflow.run_models import SiteHealthAlert, WorkflowResult, WorkflowStage, WorkflowStepDetails
from cadrumo.application.workflow.errors import WorkflowError
from cadrumo.application.workflow.resume import WorkflowResumeContext, WorkflowResumeRefusedError, WorkflowResumeTargetResolution, resolve_modelo_workflow_resume_target, resume_modelo_workflow
from cadrumo.application.workflow.persistence import list_runs, load_run
from ...core.external_constants import OutputLanguage
from ...core.i18n import tr
from ...core.json_contract import ResolvedPreconditionAction
from ._action_rendering import resolved_precondition_action_json_cell
from ._common import activate_subcommand_output_language, emit_envelope, resolve_cli_precondition_action
from ._modelo_behavior_support import resolve_optional_cli_period
from ._modelo_cli_support import (
    bad_parameter_from_error,
    parse_revision_selector,
    validate_calculation_revision_id,
    validate_work_unit_id,
)
from ._modelo_payloads import (
    WorkflowRunPayload,
    WorkflowRunSummaryPayload,
    WorkResumeResult,
    WorkRunDetailsResult,
    WorkRunResult,
    WorkRunsResult,
)


def _render_workflow_step_summary(summary_locale_key: str, details: WorkflowStepDetails | None) -> str:
    """Render an abstract workflow summary from its closed locale-neutral facts."""
    interpolation = {} if details is None else details.model_dump(mode="json", exclude_none=True)
    return tr(summary_locale_key, **interpolation)


class _WorkflowRunProjection(NamedTuple):
    """Localized step facts projected once for a workflow-run payload."""

    modelo: str | None
    period: str | None
    summary_stage: WorkflowStage | None
    summary_locale_key: str
    summary_details: WorkflowStepDetails | None
    site_health_alert: SiteHealthAlert | None
    action: ResolvedPreconditionAction | None


def _workflow_run_projection(run: WorkflowResult) -> _WorkflowRunProjection:
    """Resolve optional terminal-step and obligation facts for one run."""
    final_step = run.steps[-1] if run.steps else None
    obligation = run.obligation
    terminal_verdict = final_step.precondition_verdict if final_step is not None else None
    return _WorkflowRunProjection(
        modelo=obligation.modelo if obligation is not None else None,
        period=str(obligation.period) if obligation is not None else None,
        summary_stage=final_step.stage if final_step is not None else None,
        summary_locale_key=final_step.summary_locale_key if final_step is not None else run.summary_locale_key,
        summary_details=final_step.details if final_step is not None else run.summary_details,
        site_health_alert=final_step.site_health_alert if final_step is not None else None,
        action=resolve_cli_precondition_action(terminal_verdict) if terminal_verdict is not None else None,
    )


def _workflow_run_payload(run: WorkflowResult) -> WorkflowRunPayload:
    """Project one persisted workflow run into localized CLI-only presentation fields."""
    projection = _workflow_run_projection(run)
    return WorkflowRunPayload(
        run_id=run.run_id,
        modelo=projection.modelo,
        period=projection.period,
        final_stage=run.final_stage.value,
        aborted_reason=run.aborted_reason.value if run.aborted_reason is not None else None,
        started_at=run.started_at.isoformat(),
        obligation=run.obligation,
        summary_stage=projection.summary_stage,
        summary_locale_key=projection.summary_locale_key,
        summary_details=projection.summary_details,
        site_health_alert=projection.site_health_alert,
        summary=_render_workflow_step_summary(projection.summary_locale_key, projection.summary_details),
        action=projection.action,
    )


def _workflow_run_summary_payload(run: WorkflowResult) -> WorkflowRunSummaryPayload:
    """Project one persisted run into the compact listing contract."""
    payload = _workflow_run_payload(run)
    return WorkflowRunSummaryPayload(
        run_id=payload.run_id,
        modelo=payload.modelo,
        period=payload.period,
        final_stage=payload.final_stage,
        aborted_reason=payload.aborted_reason,
        started_at=payload.started_at,
        summary=payload.summary,
        action=payload.action,
    )


def _workflow_run_tab_line(run: WorkflowRunSummaryPayload) -> str:
    """Render one workflow-run payload as its tab-delimited CLI row."""
    return "\t".join(
        (
            run.run_id,
            run.modelo or "-",
            run.period or "-",
            run.final_stage,
            run.aborted_reason or "-",
            run.started_at,
            run.summary,
            resolved_precondition_action_json_cell(run.action),
        )
    )


def _emit_work_resume(
    ctx: typer.Context, *, result: WorkflowResumeContext, resolution: WorkflowResumeTargetResolution
) -> None:
    """Emit the resume context and resolved selector metadata.

    Args:
        ctx: Typer context carrying output-mode configuration.
        result: :class:`WorkflowResumeContext`
            produced by the workflow application service.
        resolution: :class:`WorkflowResumeTargetResolution`
            produced by the resume-target resolver.
    """
    resume_result = WorkResumeResult(
        prior_workflow_run_id=result.resumed_from_run_id,
        resolved_source=resolution.source,
        work_unit_id=resolution.work_unit_id,
        short_work_unit_id=resolution.short_work_unit_id,
        calculation_revision_id=resolution.calculation_revision_id,
        short_calculation_revision_id=resolution.short_calculation_revision_id,
        modelo=result.modelo,
        period=result.period,
        aborted_reason=result.aborted_reason.value,
        obligation=result.obligation.model_dump(mode="json"),
    )
    lines = [
        "operation\tmodelo.work.resume",
        f"prior_workflow_run_id\t{result.resumed_from_run_id}",
        f"resolved_source\t{resolution.source}",
        f"modelo\t{result.modelo}",
        f"period\t{result.period!s}",
        f"filing_year\t{resolution.filing_year or ''}",
        f"registry_period\t{result.period.registry_token}",
        f"short_work_unit_id\t{resolution.short_work_unit_id or ''}",
        f"work_unit_id\t{resolution.work_unit_id or ''}",
        f"short_calculation_revision_id\t{resolution.short_calculation_revision_id or ''}",
        f"calculation_revision_id\t{resolution.calculation_revision_id or ''}",
        f"aborted_reason\t{result.aborted_reason.value}",
        f"opens_on\t{result.obligation.opens_on.isoformat()}",
        f"closes_on\t{result.obligation.closes_on.isoformat()}",
        f"obligation_status\t{result.obligation.status.value}",
    ]
    emit_envelope(ctx, command="modelo.work.resume", result=resume_result, lines=lines)


__all__ = ["work_resume", "work_run", "work_run_details", "work_runs"]


def work_run_details(
    ctx: typer.Context,
    run_id: str,
    output_language: OutputLanguage | None = None,
) -> None:
    """Show the typed terminal-step facts for one persisted workflow run."""
    activate_subcommand_output_language(ctx, output_language)
    try:
        run = load_run(run_id)
    except WorkflowError as exc:
        raise bad_parameter_from_error(exc) from exc
    projection = _workflow_run_projection(run)
    detail_facts = (
        projection.summary_details.model_dump(mode="json", exclude={"kind"}, exclude_none=True)
        if projection.summary_details is not None
        else None
    )
    result = WorkRunDetailsResult(
        run_id=run.run_id,
        summary_stage=projection.summary_stage,
        summary_locale_key=projection.summary_locale_key,
        summary_detail_kind=projection.summary_details.kind if projection.summary_details is not None else None,
        summary_detail_facts=detail_facts,
    )
    lines = [
        "operation\tmodelo.work.run_details",
        f"run_id\t{run.run_id}",
        f"summary_stage\t{projection.summary_stage.value if projection.summary_stage is not None else ''}",
        f"summary_locale_key\t{projection.summary_locale_key}",
    ]
    emit_envelope(ctx, command="modelo.work.run_details", result=result, lines=lines)


def work_run(
    ctx: typer.Context,
    run_id: str,
    output_language: OutputLanguage | None = None,
) -> None:
    """Show one full persisted :class:`WorkflowResult`."""
    activate_subcommand_output_language(ctx, output_language)
    try:
        run = load_run(run_id)
    except WorkflowError as exc:
        raise bad_parameter_from_error(exc) from exc
    payload = _workflow_run_payload(run)
    obligation = run.obligation
    health = payload.site_health_alert
    health_status = health.status if health is not None else None
    result = WorkRunResult(
        run_id=payload.run_id,
        modelo=payload.modelo,
        period=payload.period,
        final_stage=payload.final_stage,
        aborted_reason=payload.aborted_reason,
        started_at=payload.started_at,
        obligation_opens_on=obligation.opens_on.isoformat() if obligation is not None else None,
        obligation_closes_on=obligation.closes_on.isoformat() if obligation is not None else None,
        obligation_status=obligation.status.value if obligation is not None else None,
        summary_stage=payload.summary_stage,
        summary_locale_key=payload.summary_locale_key,
        site_health_stage=health.stage.value if health is not None else None,
        site_health_state=health_status.state.value if health_status is not None else None,
        site_health_observed_at=health_status.observed_at.isoformat() if health_status is not None else None,
        site_health_http_status=health_status.http_status if health_status is not None else None,
        site_health_retry_after_seconds=health_status.retry_after_seconds if health_status is not None else None,
        site_health_detected_marker_count=health_status.detected_marker_count if health_status is not None else None,
        summary=payload.summary,
        action=payload.action,
    )
    lines = [
        "operation\tmodelo.work.run",
        "run_id\tmodelo\tperiod\tfinal_stage\taborted_reason\tstarted_at\tsummary\taction",
        _workflow_run_tab_line(payload),
    ]
    emit_envelope(ctx, command="modelo.work.run", result=result, lines=lines)


def work_runs(ctx: typer.Context, output_language: OutputLanguage | None = None) -> None:
    """List persisted :class:`WorkflowResult` rows."""
    activate_subcommand_output_language(ctx, output_language)
    runs = list_runs()
    run_payloads = [_workflow_run_summary_payload(run) for run in runs]
    result = WorkRunsResult(run_count=len(runs), runs=run_payloads)
    lines = [
        "operation\tmodelo.work.runs",
        f"run_count\t{len(runs)}",
        "run_id\tmodelo\tperiod\tfinal_stage\taborted_reason\tstarted_at\tsummary\taction",
    ]
    lines.extend(_workflow_run_tab_line(run) for run in run_payloads)
    emit_envelope(ctx, command="modelo.work.runs", result=result, lines=lines)


def work_resume(
    ctx: typer.Context,
    target: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    select: str | None = None,
    work_unit_id: str | None = None,
    calculation_revision_id: str | None = None,
    bucket_id: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Surface workflow-resume preconditions and resumable context.

    The natural-key path, exact work-unit path, calculation-revision path,
    and direct workflow-run path are normalized by
    :func:`resolve_modelo_workflow_resume_target`
    before :func:`resume_modelo_workflow` validates
    that the selected run is actually resumable.
    """
    activate_subcommand_output_language(ctx, output_language)
    try:
        typed_period = resolve_optional_cli_period(year=year, period=period, modelo=modelo)
        resolution = resolve_modelo_workflow_resume_target(
            target=target,
            work_unit_id=validate_work_unit_id(work_unit_id) if work_unit_id is not None else None,
            calculation_revision_id=validate_calculation_revision_id(calculation_revision_id)
            if calculation_revision_id is not None
            else None,
            modelo=modelo,
            year=year,
            period=typed_period,
            registry_revision_id=revision,
            bucket_id=bucket_id,
            selector=parse_revision_selector(select) if select is not None else None,
        )
        result = resume_modelo_workflow(resolution.run_id)
    except (WorkflowResumeRefusedError, WorkflowError) as exc:
        raise bad_parameter_from_error(exc) from exc
    _emit_work_resume(ctx, result=result, resolution=resolution)
