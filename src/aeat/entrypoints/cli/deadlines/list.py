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
    year: int = typer.Option(..., "--year", help=tr("cli.deadlines.list.year_help")),
    profile: Path | None = typer.Option(
        None,
        "--profile",
        help=tr("cli.deadlines.list.profile_help"),
    ),
) -> None:
    """Print the full :class:`aeat.domain.deadlines.Schedule` for the given year."""
    profile_path = resolve_profile_path(profile)
    loaded_profile = load_profile(profile_path)
    engine = build_engine()
    schedule = engine.compute(loaded_profile, year)

    table = Table(title=tr("cli.deadlines.list.table_title", year=year), header_style="bold")
    table.add_column(tr("cli.deadlines.list.modelo_col"), style="cyan")
    table.add_column(tr("cli.deadlines.list.period_col"))
    table.add_column(tr("cli.deadlines.list.opens_on_col"))
    table.add_column(tr("cli.deadlines.list.closes_on_col"))
    table.add_column(tr("cli.deadlines.list.status_col"))
    for obligation in schedule.obligations:
        table.add_row(
            obligation.modelo,
            obligation.period,
            obligation.opens_on.isoformat(),
            obligation.closes_on.isoformat(),
            obligation.status.value,
        )
    _CONSOLE.print(table)
    count = len(schedule.obligations)
    label = tr("cli.deadlines.list.labels.tax_deadlines")
    _CONSOLE.print(f"[dim]{count} {label}[/dim]")
