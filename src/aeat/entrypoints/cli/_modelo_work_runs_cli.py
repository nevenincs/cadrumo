"""Typer registration for modelo work workflow-run commands."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Annotated

import typer

from ...application.modelo import (
    WorkUnitNotFoundError,
    get_work_unit,
    workflow_period_for_work_unit,
)
from ...application.workflow import (
    WorkflowError,
    WorkflowResumeRefusedError,
    find_latest_run_for_period,
    list_runs,
    resume_modelo_workflow,
)
from ...core.external_constants import OutputLanguage
from ...core.i18n import tr
from ._common import _emit_envelope
from ._modelo_payloads import WorkflowRunPayload, WorkResumeResult, WorkRunsResult

_WORKFLOW_RUN_ID_RE = r"[0-9a-f]{16}"
_WORK_UNIT_ID_RE = r"^[0-9a-f]{64}$"


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
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
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
                "drive a fresh attempt. Accepts a workflow run id or a work-unit "
                "id. Local-only: never contacts AEAT."
            ),
        ),
    )
    def work_resume(
        ctx: typer.Context,
        target: Annotated[
            str,
            typer.Argument(
                help=tr(
                    "cli.app.modelo.work.resume_target_help",
                    default=(
                        "16-character workflow run id, or the 64-character "
                        "work-unit id (its latest run is resolved automatically). "
                        "Run `aeat app modelo work runs` to list run ids."
                    ),
                ),
            ),
        ],
    ) -> None:
        """Surface the workflow-resume preconditions and resumable context."""
        workflow_run_id = _resolve_workflow_run_id(
            target,
            bad_parameter_from_error=bad_parameter_from_error,
        )

        try:
            result = resume_modelo_workflow(workflow_run_id)
        except (WorkflowResumeRefusedError, WorkflowError) as exc:
            raise bad_parameter_from_error(exc) from exc

        resume_result = WorkResumeResult(
            prior_workflow_run_id=result.resumed_from_run_id,
            modelo=result.modelo,
            period=result.period,
            aborted_reason=result.aborted_reason.value,
            obligation=result.obligation.model_dump(mode="json"),
        )
        lines = [
            "operation\tmodelo.work.resume",
            f"prior_workflow_run_id\t{result.resumed_from_run_id}",
            f"modelo\t{result.modelo}",
            f"period\t{result.period}",
            f"aborted_reason\t{result.aborted_reason.value}",
            f"opens_on\t{result.obligation.opens_on.isoformat()}",
            f"closes_on\t{result.obligation.closes_on.isoformat()}",
            f"obligation_status\t{result.obligation.status.value}",
        ]
        _emit_envelope(ctx, command="modelo.work.resume", result=resume_result, lines=lines)


def _resolve_workflow_run_id(
    target: str,
    *,
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter],
) -> str:
    """Resolve a work-resume argument to a 16-character workflow run id."""
    stripped = target.strip()
    if re.fullmatch(_WORKFLOW_RUN_ID_RE, stripped):
        return stripped
    if re.fullmatch(_WORK_UNIT_ID_RE, stripped):
        try:
            unit = get_work_unit(stripped)
        except WorkUnitNotFoundError as exc:
            raise bad_parameter_from_error(exc) from exc
        try:
            run = find_latest_run_for_period(
                modelo=unit.modelo,
                period=workflow_period_for_work_unit(unit),
            )
        except WorkflowError as exc:
            raise bad_parameter_from_error(exc) from exc
        return run.run_id
    raise typer.BadParameter(
        tr(
            "cli.app.modelo.work.resume_invalid_target",
            default=(
                "resume target must be a 16-character workflow run id or a "
                "64-character work-unit id; got {target!r}. "
                "Run `aeat app modelo work runs` to list run ids."
            ),
            target=target,
        )
    )


__all__ = ["register_work_run_commands"]
