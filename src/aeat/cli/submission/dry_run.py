"""``aeat submission dry-run`` — walk the portal up to but not including submit."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from aeat.cli._observability import cli_run_context
from aeat.cli.submission._helpers import build_engine, load_draft

_CONSOLE = Console()


def dry_run_cmd(
    draft_path: Path = typer.Argument(..., help="Path to a CLI-format draft JSON."),
) -> None:
    """Dry-run the submission engine against ``draft_path``."""
    arguments = {"draft_path": str(draft_path)}
    with cli_run_context(entrypoint="aeat submission dry-run", arguments=arguments):
        draft = load_draft(draft_path)
        engine = build_engine()
        filing = asyncio.run(engine.submit_draft(draft, dry_run=True))
        _CONSOLE.print(f"[green]dry-run OK[/green]: submission_id={filing.submission_id} status={filing.status.value}")
