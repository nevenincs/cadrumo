"""``aeat submission preflight`` — run preflight gates without browser work."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import typer
from rich.console import Console

from aeat.cli.submission._helpers import build_engine, load_draft
from aeat.submission import Preflight, SubmissionPreflightError

_CONSOLE = Console()


def preflight_cmd(
    draft_path: Path = typer.Argument(..., help="Path to a CLI-format draft JSON."),
) -> None:
    """Run preflight on ``draft_path`` and print the outcome."""
    draft = load_draft(draft_path)
    engine = build_engine()
    checker = Preflight(
        deadline_checker=engine.deadline_checker,
        cert_backend=engine.cert_backend,
    )
    try:
        checker.check(draft, today=date.today())
    except SubmissionPreflightError as exc:
        _CONSOLE.print(f"[red]preflight FAILED:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    _CONSOLE.print(f"[green]preflight OK[/green] for draft {draft.draft_id} ({draft.modelo} {draft.period})")
