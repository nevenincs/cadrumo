"""``aeat submission list`` — list persisted SubmittedFiling records."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from aeat.cli.submission._helpers import build_engine
from aeat.submission import SubmissionStatus

_CONSOLE = Console()


def list_cmd(
    modelo: str | None = typer.Option(None, "--modelo", help="Filter by modelo."),
    status: SubmissionStatus | None = typer.Option(None, "--status", help="Filter by SubmissionStatus."),
) -> None:
    """List every persisted :class:`SubmittedFiling`, optionally filtered."""
    engine = build_engine()
    filings = engine.list_submissions(modelo=modelo, status=status)

    table = Table(title="submissions", header_style="bold")
    table.add_column("submission_id", style="cyan")
    table.add_column("modelo")
    table.add_column("period")
    table.add_column("status")
    table.add_column("submitted_at")
    for filing in filings:
        table.add_row(
            filing.submission_id,
            filing.modelo,
            filing.period,
            filing.status.value,
            filing.submitted_at.isoformat(),
        )
    _CONSOLE.print(table)
    _CONSOLE.print(f"[dim]{len(filings)} record(s)[/dim]")
