"""``aeat submission show`` — pretty-print a persisted SubmittedFiling."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.json import JSON

from aeat.cli.submission._helpers import build_engine
from aeat.submission import SubmissionError

_CONSOLE = Console()


def show_cmd(
    submission_id: str = typer.Argument(..., help="The submission id to load."),
) -> None:
    """Load and pretty-print a persisted :class:`SubmittedFiling`."""
    engine = build_engine()
    try:
        filing = engine.load_submission(submission_id)
    except SubmissionError as exc:
        _CONSOLE.print(f"[red]not found:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    _CONSOLE.print(JSON(filing.model_dump_json(indent=2)))
