"""Typer registration for modelo work workflow-run commands."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

import typer

from ...application.workflow import (
    WorkflowError,
    WorkflowResumeContext,
    WorkflowResumeRefusedError,
    WorkflowResumeTargetResolution,
    list_runs,
    resolve_modelo_workflow_resume_target,
    resume_modelo_workflow,
)
from ...core.external_constants import OutputLanguage
from ...core.i18n import tr
from ._common import _emit_envelope
from ._modelo_cli_support import (
    OutputLanguageOpt,
    parse_revision_selector,
    validate_calculation_revision_id,
    validate_work_unit_id,
)
from ._modelo_payloads import WorkflowRunPayload, WorkResumeResult, WorkRunsResult


def register_work_run_commands(
    work_app: typer.Typer,
    *,
    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None],
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter],
) -> None:
    """Register workflow-run discovery and resume commands."""

    @work_app.command(
        "runs",
        help=tr(
            "cli.app.modelo.work.runs_help",
            default=(
                "List persisted workflow runs with their run ids, newest first. "
                "Use a run id with `aeat app modelo work resume`. Local-only: "
                "never contacts AEAT."
            ),
        ),
    )
    def work_runs(
        ctx: typer.Context,
        output_language: OutputLanguageOpt = None,
    ) -> None:
        """List persisted workflow runs so an operator can discover run ids."""
        activate_output_language(ctx, output_language)
        runs = list_runs()

        result = WorkRunsResult(
            run_count=len(runs),
            runs=[
                WorkflowRunPayload(
                    run_id=run.run_id,
                    modelo=run.obligation.modelo if run.obligation is not None else None,
                    period=run.obligation.period if run.obligation is not None else None,
                    final_stage=run.final_stage.value,
                    aborted_reason=(run.aborted_reason.value if run.aborted_reason is not None else None),
                    started_at=run.started_at.isoformat(),
                )
                for run in runs
            ],
        )
        lines = [
            "operation\tmodelo.work.runs",
            f"run_count\t{len(runs)}",
            "run_id\tmodelo\tperiod\tfinal_stage\taborted_reason\tstarted_at",
        ]
        lines.extend(
            "\t".join(
                (
                    run.run_id,
                    run.obligation.modelo if run.obligation is not None else "-",
                    run.obligation.period if run.obligation is not None else "-",
                    run.final_stage.value,
                    run.aborted_reason.value if run.aborted_reason is not None else "-",
                    run.started_at.isoformat(),
                )
            )
            for run in runs
        )
        _emit_envelope(ctx, command="modelo.work.runs", result=result, lines=lines)

    @work_app.command(
        "resume",
        help=tr(
            "cli.app.modelo.work.resume_help",
            default=(
                "Validate that an aborted workflow run may be retried. Emits the "
                "(modelo, period, obligation) context the engine would consume to "
                "drive a fresh attempt. Use --modelo --year --period for the "
                "normal path; exact ids remain advanced escape hatches. Local-only: "
                "never contacts AEAT."
            ),
        ),
    )
    def work_resume(
        ctx: typer.Context,
        target: Annotated[
            str | None,
            typer.Argument(
                help=tr(
                    "cli.app.modelo.work.resume_target_help",
                    default=(
                        "Optional legacy 16-character workflow run id or 64-character "
                        "work-unit id. Prefer --modelo --year --period."
                    ),
                ),
            ),
        ] = None,
        modelo: Annotated[
            str | None,
            typer.Option("--modelo", help=tr("cli.app.modelo.work.modelo_help")),
        ] = None,
        year: Annotated[
            int | None,
            typer.Option("--year", help=tr("cli.app.modelo.work.year_help")),
        ] = None,
        period: Annotated[
            str | None,
            typer.Option("--period", help=tr("cli.app.modelo.work.period_help")),
        ] = None,
        revision: Annotated[
            str | None,
            typer.Option("--revision", help=tr("cli.app.modelo.work.revision_help")),
        ] = None,
        select: Annotated[
            str | None,
            typer.Option("--select", help=tr("cli.app.modelo.work.revision_selector_help")),
        ] = None,
        work_unit_id: Annotated[
            str | None,
            typer.Option("--work-unit-id", help=tr("cli.app.modelo.work.work_unit_id_help")),
        ] = None,
        calculation_revision_id: Annotated[
            str | None,
            typer.Option(
                "--calculation-revision-id",
                help=tr("cli.app.modelo.work.calculation_revision_id_help"),
            ),
        ] = None,
        bucket_id: Annotated[
            str | None,
            typer.Option("--bucket-id", help=tr("cli.app.modelo.work.bucket_id_help")),
        ] = None,
        output_language: OutputLanguageOpt = None,
    ) -> None:
        """Surface the workflow-resume preconditions and resumable context."""
        activate_output_language(ctx, output_language)

        try:
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
                period=period,
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
        f"period\t{result.period}",
        f"filing_year\t{resolution.filing_year or ''}",
        f"registry_period\t{resolution.registry_period or ''}",
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
