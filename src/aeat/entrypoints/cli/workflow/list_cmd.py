"""``aeat workflow list`` — enumerate persisted workflow runs.

Wraps :func:`aeat.application.workflow.list_runs` to render every persisted
:class:`aeat.application.workflow.WorkflowResult` either as a Rich table
or as a JSON envelope on stdout.
"""

from __future__ import annotations

from datetime import date

import typer
from rich.console import Console
from rich.table import Table

from ....application.workflow import WorkflowResult, list_runs
from ....core.config import load_settings
from .._errors import CliRefusedBoundaryError, json_output_requested
from .._observability import cli_run_context
from .._schemas import OutputRootSchema, emit_json_success, register_schema

_CONSOLE = Console()


@register_schema("workflow list")
class WorkflowListJson(OutputRootSchema[list[WorkflowResult]]):
    """JSON output schema for ``aeat workflow list --json``.

    Generic over ``list[``:class:`aeat.application.workflow.WorkflowResult`
    ``]``: the wrapped payload is the listing returned by
    :func:`aeat.application.workflow.list_runs`.
    """


def list_cmd(
    since: str | None = typer.Option(
        None,
        "--since",
        help="ISO date (YYYY-MM-DD); only runs started on or after are listed.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit the listing as a JSON array on stdout instead of a table.",
    ),
) -> None:
    """List persisted :class:`aeat.application.workflow.WorkflowResult` records.

    Reads runs from ``settings.aeat_workflow_runs_dir`` and renders them as
    a Rich table by default, or as a JSON envelope when ``as_json`` (or the
    detected JSON-output flag) is set.

    Args:
        since: Optional ISO-8601 date filter (``YYYY-MM-DD``); only runs
            started on or after this date are listed.
        as_json: When ``True``, emit machine-readable JSON via
            :func:`aeat.entrypoints.cli._schemas.emit_json_success`.

    Raises:
        :exc:`aeat.entrypoints.cli._errors.CliRefusedBoundaryError`: When
            ``--json`` is set and ``--since`` is not a valid ISO date.
        typer.Exit: With code ``2`` when ``--since`` is not a valid ISO date
            and JSON output was not requested.
    """
    arguments = {"since": since, "json": as_json}
    with cli_run_context(entrypoint="aeat workflow list", arguments=arguments):
        settings = load_settings()
        since_date: date | None = None
        if since is not None:
            try:
                since_date = date.fromisoformat(since)
            except ValueError as exc:
                if as_json or json_output_requested():
                    raise CliRefusedBoundaryError(str(exc), context={"since": since}) from exc
                _CONSOLE.print(f"[red]invalid --since:[/red] {exc}")
                raise typer.Exit(code=2) from exc
        runs = list_runs(runs_dir=settings.aeat_workflow_runs_dir, since=since_date)
        if as_json or json_output_requested():
            emit_json_success("workflow list", runs)
            return

        table = Table(title=f"workflow runs ({len(runs)})")
        table.add_column("run_id")
        table.add_column("started_at")
        table.add_column("final_stage")
        table.add_column("reason")
        for r in runs:
            table.add_row(
                r.run_id,
                r.started_at.isoformat(),
                r.final_stage.value,
                r.aborted_reason.value if r.aborted_reason is not None else "-",
            )
        _CONSOLE.print(table)
