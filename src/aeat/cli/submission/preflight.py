"""``aeat submission preflight`` — run preflight gates without browser work."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import typer
from rich.console import Console

from ...submission import Preflight, SubmissionPreflightError
from .._observability import cli_run_context
from ._helpers import build_engine, load_draft

_CONSOLE = Console()


def preflight_cmd(
    draft_path: Path = typer.Argument(..., help="Path to a CLI-format draft JSON."),
) -> None:
    """Run preflight on ``draft_path`` and print the outcome."""
    arguments = {"draft_path": str(draft_path)}
    with cli_run_context(
        entrypoint="aeat submission preflight",
        arguments=arguments,
        positional=("draft_path",),
    ):
        draft = load_draft(draft_path)
        engine = build_engine()
        checker = Preflight(
            deadline_checker=engine.deadline_checker,
            auth_provider=engine.auth_provider,
        )
        try:
            checker.check(draft, today=date.today())
        except SubmissionPreflightError as exc:
            _CONSOLE.print(f"[red]preflight FAILED:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        _CONSOLE.print(f"[green]preflight OK[/green] for draft {draft.draft_id} ({draft.modelo} {draft.period})")
