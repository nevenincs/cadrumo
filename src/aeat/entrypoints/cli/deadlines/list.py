"""``aeat deadlines list`` — print the full filing schedule for a year.

Renders every :class:`aeat.domain.deadlines.FilingObligation` for the
requested year as a Rich table, in the order produced by
:meth:`aeat.domain.deadlines.DeadlineEngine.compute`.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .._i18n import tr
from ._helpers import build_engine, load_profile, resolve_profile_path

_CONSOLE = Console()


def list_schedule(
    year: int = typer.Option(..., "--year", help="Fiscal year to compute the schedule for."),
    profile: Path | None = typer.Option(
        None,
        "--profile",
        help="Path to a JSON AutonomoProfile (defaults to AEAT_DEFAULT_PROFILE_PATH).",
    ),
) -> None:
    """Print the full :class:`aeat.domain.deadlines.Schedule` for the given year."""
    profile_path = resolve_profile_path(profile)
    loaded_profile = load_profile(profile_path)
    engine = build_engine()
    schedule = engine.compute(loaded_profile, year)

    table = Table(title=f"filing schedule {year}", header_style="bold")
    table.add_column("modelo", style="cyan")
    table.add_column("period")
    table.add_column("opens_on")
    table.add_column("closes_on")
    table.add_column("status")
    for obligation in schedule.obligations:
        table.add_row(
            obligation.modelo,
            obligation.period,
            obligation.opens_on.isoformat(),
            obligation.closes_on.isoformat(),
            obligation.status.value,
        )
    _CONSOLE.print(table)
    len(schedule.obligations)
    label = tr("deadlines.list.t_125112")
    _CONSOLE.print(f"[dim]{label}[/dim]")
