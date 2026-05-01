"""``aeat workflow show`` — pretty-print a persisted workflow run.

Loads a :class:`aeat.application.workflow.WorkflowResult` from
``settings.aeat_workflow_runs_dir`` via
:func:`aeat.application.workflow.load_run` and renders it as
Rich-formatted JSON or as a JSON envelope on stdout.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.json import JSON

from ....application.workflow import WorkflowError, WorkflowResult, load_run
from ....core.config import load_settings
from .._errors import json_output_requested
from .._observability import cli_run_context
from .._schemas import OutputRootSchema, emit_json_success, register_schema

_CONSOLE = Console()


@register_schema("workflow show")
class WorkflowShowJson(OutputRootSchema[WorkflowResult]):
    """JSON output schema for ``aeat workflow show --json``.

    Wraps a single :class:`aeat.application.workflow.WorkflowResult`.
    """


def show_cmd(
    run_id: str = typer.Argument(..., help="The workflow run id to load."),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit the raw JSON record on stdout instead of the rich view.",
    ),
) -> None:
    """Load and pretty-print a persisted :class:`aeat.application.workflow.WorkflowResult`.

    Args:
        run_id: Identifier of the run to load. Matches the file stem under
            ``AEAT_WORKFLOW_RUNS_DIR``.
        as_json: When ``True``, emit compact JSON to stdout via
            :func:`aeat.entrypoints.cli._schemas.emit_json_success`.

    Raises:
        :exc:`aeat.application.workflow.WorkflowError`: When ``--json`` is
            set and the run cannot be loaded; surfaced through the JSON
            error envelope.
        typer.Exit: With code ``1`` when the run cannot be loaded and JSON
            output was not requested.
    """
    arguments = {"run_id": run_id, "json": as_json}
    with cli_run_context(
        entrypoint="aeat workflow show",
        arguments=arguments,
        positional=("run_id",),
    ):
        settings = load_settings()
        try:
            result = load_run(run_id, runs_dir=settings.aeat_workflow_runs_dir)
        except WorkflowError as exc:
            if as_json or json_output_requested():
                raise
            _CONSOLE.print(f"[red]not found:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        payload = result.model_dump_json(indent=2)
        if as_json or json_output_requested():
            emit_json_success("workflow show", result)
        else:
            _CONSOLE.print(JSON(payload))
