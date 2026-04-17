"""``aeat workflow next`` — run the engine for the caller's next obligation.

The command refuses to enter live mode unless the caller passes both
``--no-dry-run`` *and* ``--i-understand-this-is-real``, mirroring the
submission engine's double-gate contract. Until the in-flight
sibling branches (#43, #46, #8) land, invoking this command outside
a test context raises a :class:`WorkflowError` because the
certificate / inbox / status protocols cannot be wired without them.
"""

from __future__ import annotations

import typer
from rich.console import Console

from ._helpers import run_engine_next

_CONSOLE = Console()


def next_cmd(
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
    """Drive the workflow for the next pending obligation.

    Args:
        no_dry_run: When ``True``, enter live-submission mode.
        i_understand_this_is_real: Additional gate required alongside
            ``--no-dry-run``.
        sync_first: Whether the sync stage should run.
        as_json: When ``True``, print the :class:`WorkflowResult` as JSON.
    """
    if no_dry_run and not i_understand_this_is_real:
        _CONSOLE.print(
            "[red]refusing:[/red] --no-dry-run requires --i-understand-this-is-real.",
        )
        raise typer.Exit(code=2)
    run_engine_next(
        dry_run=not no_dry_run,
        sync_first=sync_first,
        as_json=as_json,
    )
