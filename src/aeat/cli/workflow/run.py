"""``aeat workflow run`` — run the engine for a caller-named target."""

from __future__ import annotations

import typer
from rich.console import Console

from ._helpers import run_engine_for_period

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
    run_engine_for_period(
        modelo=modelo,
        period=period,
        dry_run=not no_dry_run,
        sync_first=sync_first,
        as_json=as_json,
    )
