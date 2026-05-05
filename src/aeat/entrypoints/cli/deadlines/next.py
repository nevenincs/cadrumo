"""``aeat deadlines next`` — show the next non-overdue obligation.

Queries :func:`aeat.domain.deadlines.next_deadline` for the soonest
upcoming :class:`aeat.domain.deadlines.FilingObligation` and prints its
modelo, period, due date, status, and applies-because rationale.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import typer
from rich.console import Console

from ....domain.deadlines import next_deadline
from .._i18n import tr
from ._helpers import build_engine, load_profile, resolve_profile_path

_CONSOLE = Console()


def next_obligation(
    year: int = typer.Option(
        date.today().year,
        "--year",
        help=tr("cli.deadlines.next.year_help"),
    ),
    profile: Path | None = typer.Option(
        None,
        "--profile",
        help=tr("cli.deadlines.next.profile_help"),
    ),
) -> None:
    """Print the next :class:`aeat.domain.deadlines.FilingObligation` due."""
    profile_path = resolve_profile_path(profile)
    loaded_profile = load_profile(profile_path)
    engine = build_engine()
    schedule = engine.compute(loaded_profile, year)
    obligation = next_deadline(schedule)
    if obligation is None:
        msg = tr("cli.deadlines.next.labels.no_upcoming")
        _CONSOLE.print(f"[yellow]{msg}[/yellow]")
        raise typer.Exit(code=0)
    closes_label = tr("cli.deadlines.next.labels.closes")
    _CONSOLE.print(
        f"[bold cyan]{obligation.modelo}[/bold cyan] {obligation.period} - "
        f"{closes_label} {obligation.closes_on.isoformat()} ({obligation.status.value})"
    )
    _CONSOLE.print(f"[dim]{obligation.applies_because}[/dim]")
