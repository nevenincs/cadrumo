"""``aeat workflow run`` — run the engine for a caller-named target."""

from __future__ import annotations

import typer
from rich.console import Console

from aeat.cli._observability import cli_run_context
from aeat.cli.workflow._helpers import run_engine_for_period
from aeat.observability import (
    RunEventKind,
    RunEventPayload,
    WorkflowLinkPayload,
    record_event,
)

_CONSOLE = Console()


def run_cmd(
    modelo: str = typer.Option(..., "--modelo", help="Modelo identifier (e.g. 130)."),
    period: str = typer.Option(..., "--period", help="Period identifier (e.g. 2026Q1)."),
    no_dry_run: bool = typer.Option(
        False,
        "--no-dry-run",
        help="Attempt a live submission instead of a dry-run walk.",
    ),
    i_understand_this_is_real: bool = typer.Option(
        False,
        "--i-understand-this-is-real",
        help="Explicit confirmation flag required alongside --no-dry-run.",
    ),
    sync_first: bool = typer.Option(
        True,
        "--sync/--no-sync",
        help="Run the self-healing sync before the deadline stage (default: on).",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit the WorkflowResult as JSON on stdout.",
    ),
) -> None:
    """Drive the workflow for a named ``(modelo, period)`` target.

    Args:
        modelo: Target modelo identifier.
        period: Target period identifier.
        no_dry_run: When ``True``, enter live-submission mode.
        i_understand_this_is_real: Additional confirmation gate.
        sync_first: Whether the sync stage should run.
        as_json: When ``True``, print the :class:`WorkflowResult` as JSON.
    """
    if no_dry_run and not i_understand_this_is_real:
        _CONSOLE.print(
            "[red]refusing:[/red] --no-dry-run requires --i-understand-this-is-real.",
        )
        raise typer.Exit(code=2)
    arguments = {
        "modelo": modelo,
        "period": period,
        "no-dry-run": no_dry_run,
        "i-understand-this-is-real": i_understand_this_is_real,
        "sync": sync_first,
        "json": as_json,
    }
    with cli_run_context(entrypoint="aeat workflow run", arguments=arguments):
        result = run_engine_for_period(
            modelo=modelo,
            period=period,
            dry_run=not no_dry_run,
            override_confirmation=i_understand_this_is_real,
            sync_first=sync_first,
            as_json=as_json,
        )
        record_event(
            RunEventKind.WORKFLOW_STARTED,
            payload=RunEventPayload(workflow_link=WorkflowLinkPayload(workflow_run_id=result.run_id)),
        )
        record_event(
            RunEventKind.WORKFLOW_COMPLETED,
            payload=RunEventPayload(workflow_link=WorkflowLinkPayload(workflow_run_id=result.run_id)),
        )
