"""``aeat deadlines next`` - show the next non-overdue obligation."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import typer
from rich.console import Console

from ....domain.deadlines import next_deadline
from ._helpers import build_engine, load_profile, resolve_profile_path

_CONSOLE = Console()


def next_obligation(
    year: int = typer.Option(
        date.today().year,
        "--year",
        help="Fiscal year to compute the schedule for (default: current year).",
    ),
    profile: Path | None = typer.Option(
        None,
        "--profile",
        help="Path to a JSON AutonomoProfile (defaults to AEAT_DEFAULT_PROFILE_PATH).",
    ),
) -> None:
    """Print the next :class:`aeat.domain.deadlines.FilingObligation` due."""
    profile_path = resolve_profile_path(profile)
    loaded_profile = load_profile(profile_path)
    engine = build_engine()
    schedule = engine.compute(loaded_profile, year)
    obligation = next_deadline(schedule)
    if obligation is None:
        _CONSOLE.print(f"[yellow]no upcoming obligations for {year}: every entry is overdue[/yellow]")
        raise typer.Exit(code=0)
    _CONSOLE.print(
        f"[bold cyan]{obligation.modelo}[/bold cyan] {obligation.period} - "
        f"closes {obligation.closes_on.isoformat()} ({obligation.status.value})"
    )
    _CONSOLE.print(f"[dim]{obligation.applies_because}[/dim]")
