"""``aeat workflow next`` — run the engine for the caller's next obligation.

The command refuses to enter live mode unless the caller passes both
an explicit ``--dry-run`` or ``--live`` choice, mirroring the
submission engine's explicit-mode contract. Until the in-flight
sibling branches (#43, #46, #8) land, invoking this command outside
a test context raises a :class:`WorkflowError` because the
certificate / inbox / status protocols cannot be wired without them.
"""

from __future__ import annotations

import typer
from rich.console import Console

from aeat.cli.workflow._helpers import run_engine_next

_CONSOLE = Console()


def next_cmd(
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
    """Drive the workflow for the next pending obligation.

    Args:
        dry_run: When ``True``, enter dry-run mode.
        live: When ``True``, request live mode.
        sync_first: Whether the sync stage should run.
        as_json: When ``True``, print the :class:`WorkflowResult` as JSON.
    """
    if dry_run == live:
        _CONSOLE.print("[red]refusing:[/red] choose exactly one of --dry-run or --live.")
        raise typer.Exit(code=2)
    run_engine_next(
        dry_run=dry_run,
        sync_first=sync_first,
        as_json=as_json,
    )
