"""Typer registration for modelo workflow-run discovery and resume.

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

from collections.abc import Callable
from typing import Annotated, NamedTuple

import typer

from ...application.workflow import (
    SiteHealthAlert,
    WorkflowError,
    WorkflowResult,
    WorkflowResumeContext,
    WorkflowResumeRefusedError,
    WorkflowResumeTargetResolution,
    WorkflowStage,
    WorkflowStepDetails,
    list_runs,
    resolve_modelo_workflow_resume_target,
    resume_modelo_workflow,
)
from ...core import Period
from ...core.external_constants import OutputLanguage
from ...core.i18n import tr
from ...core.json_contract import ResolvedPreconditionAction
from ._action_rendering import resolved_precondition_action_json_cell
from ._command_policy import command_execution_policy
from ._common import _emit_envelope, resolve_cli_precondition_action
from ._modelo_cli_support import (
    OutputLanguageOpt,
    parse_revision_selector,
    validate_calculation_revision_id,
    validate_work_unit_id,
)
from ._modelo_execution_policies import MODEL_READ, MODEL_WRITE
from ._modelo_payloads import WorkflowRunPayload, WorkResumeResult, WorkRunsResult
from ._modelo_work_options import (
    _BucketIdOpt,
    _ModeloOpt,
    _PeriodOpt,
    _RevisionOpt,
    _WorkUnitIdOpt,
    _YearOpt,
)


def _render_workflow_step_summary(
    summary_locale_key: str,
    details: WorkflowStepDetails | None,
) -> str:
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
        summary=_render_workflow_step_summary(
            projection.summary_locale_key,
            projection.summary_details,
        ),
        action=projection.action,
    )


def _workflow_run_tab_line(run: WorkflowRunPayload) -> str:
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
        ),
    )


def register_work_run_commands(
    work_app: typer.Typer,
    *,
    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None],
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter],
    resolve_optional_cli_period: Callable[..., Period | None],
) -> None:
    """Register workflow-run discovery and resume commands.

    The command callbacks delegate business rules to the public workflow
    application facade and keep CLI responsibilities limited to option parsing,
    localization, and envelope emission.
    """

    @work_app.command(
        "runs",
        help=tr("cli.app.modelo.work.runs_help"),
    )
    @command_execution_policy(MODEL_READ)
    def work_runs(
        ctx: typer.Context,
        output_language: OutputLanguageOpt = None,
    ) -> None:
        """List persisted :class:`WorkflowResult` rows."""
        activate_output_language(ctx, output_language)
        runs = list_runs()

        run_payloads = [_workflow_run_payload(run) for run in runs]
        result = WorkRunsResult(run_count=len(runs), runs=run_payloads)
        lines = [
            "operation\tmodelo.work.runs",
            f"run_count\t{len(runs)}",
            "run_id\tmodelo\tperiod\tfinal_stage\taborted_reason\tstarted_at\tsummary\taction",
        ]
        lines.extend(_workflow_run_tab_line(run) for run in run_payloads)
        _emit_envelope(ctx, command="modelo.work.runs", result=result, lines=lines)

    @work_app.command(
        "resume",
        help=tr("cli.app.modelo.work.resume_help"),
    )
    @command_execution_policy(MODEL_WRITE)
    def work_resume(
        ctx: typer.Context,
        target: Annotated[
            str | None,
            typer.Argument(
                help=tr("cli.app.modelo.work.resume_target_help"),
            ),
        ] = None,
        modelo: _ModeloOpt = None,
        year: _YearOpt = None,
        period: _PeriodOpt = None,
        revision: _RevisionOpt = None,
        select: Annotated[
            str | None,
            typer.Option("--select", help=tr("cli.app.modelo.work.revision_selector_help")),
        ] = None,
        work_unit_id: _WorkUnitIdOpt = None,
        calculation_revision_id: Annotated[
            str | None,
            typer.Option(
                "--calculation-revision-id",
                help=tr("cli.app.modelo.work.calculation_revision_id_help"),
            ),
        ] = None,
        bucket_id: _BucketIdOpt = None,
        output_language: OutputLanguageOpt = None,
    ) -> None:
        """Surface workflow-resume preconditions and resumable context.

        The natural-key path, exact work-unit path, calculation-revision path,
        and direct workflow-run path are normalized by
        :func:`resolve_modelo_workflow_resume_target`
        before :func:`resume_modelo_workflow` validates
        that the selected run is actually resumable.
        """
        activate_output_language(ctx, output_language)

        try:
            typed_period = resolve_optional_cli_period(year=year, period=period, modelo=modelo)
            resolution = resolve_modelo_workflow_resume_target(
                target=target,
                work_unit_id=validate_work_unit_id(work_unit_id) if work_unit_id is not None else None,
                calculation_revision_id=(
                    validate_calculation_revision_id(calculation_revision_id)
                    if calculation_revision_id is not None
                    else None
                ),
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


def _emit_work_resume(
    ctx: typer.Context,
    *,
    result: WorkflowResumeContext,
    resolution: WorkflowResumeTargetResolution,
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
    _emit_envelope(ctx, command="modelo.work.resume", result=resume_result, lines=lines)


__all__ = ["register_work_run_commands"]
