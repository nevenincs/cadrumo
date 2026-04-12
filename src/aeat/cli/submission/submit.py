"""``aeat submission submit`` — live submission gated on an explicit flag."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from aeat.cli.submission._helpers import build_engine, load_draft

_CONSOLE = Console()


def submit_cmd(
    draft_path: Path = typer.Argument(..., help="Path to a CLI-format draft JSON."),
    i_understand_this_is_real: bool = typer.Option(
        False,
        "--i-understand-this-is-real",
        help=("Explicit consent flag required to enter live submission mode. Without this flag the command exits 2."),
    ),
) -> None:
    """Submit ``draft_path`` to the real AEAT portal — IRREVERSIBLE.

    The command refuses to run unless ``--i-understand-this-is-real``
    is explicitly passed on the command line. Even with the flag set,
    the engine enforces the ``AEAT_SUBMISSION_REQUIRE_HUMAN_CONFIRMATION``
    settings gate.
    """
    if not i_understand_this_is_real:
        _CONSOLE.print("[red]refusing:[/red] live submission requires --i-understand-this-is-real on the command line.")
        raise typer.Exit(code=2)

    draft = load_draft(draft_path)
    engine = build_engine()
    filing = asyncio.run(engine.submit_draft(draft, dry_run=False, override_confirmation=True))
    _CONSOLE.print(
        f"[green]LIVE submission OK[/green]: submission_id={filing.submission_id} status={filing.status.value}"
    )
