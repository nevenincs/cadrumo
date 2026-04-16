"""``aeat workflow run`` — run the engine for a caller-named target."""

from __future__ import annotations

import typer
from rich.console import Console

from aeat.cli.workflow._helpers import run_engine_for_period

_CONSOLE = Console()


def run_cmd(
    modelo: str = typer.Option(..., "--modelo", help="Modelo identifier (e.g. 130)."),
    period: str = typer.Option(..., "--period", help="Period identifier (e.g. 2026Q1)."),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run the workflow in dry-run mode.",
    ),
    live: bool = typer.Option(
        False,
        "--live",
        help="Attempt a live workflow submission.",
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
        dry_run: When ``True``, enter dry-run mode.
        live: When ``True``, request live mode.
        sync_first: Whether the sync stage should run.
        as_json: When ``True``, print the :class:`WorkflowResult` as JSON.
    """
    if dry_run == live:
        _CONSOLE.print("[red]refusing:[/red] choose exactly one of --dry-run or --live.")
        raise typer.Exit(code=2)
    run_engine_for_period(
        modelo=modelo,
        period=period,
        dry_run=dry_run,
        sync_first=sync_first,
        as_json=as_json,
    )
