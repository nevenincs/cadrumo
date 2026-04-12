"""``aeat inbox fetch`` — pull new notifications from the source."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, time

import typer
from rich.console import Console
from rich.table import Table

from aeat.cli.inbox._helpers import build_fetcher
from aeat.inbox import InboxError

_CONSOLE = Console()


def fetch_cmd(
    since: datetime | None = typer.Option(
        None,
        "--since",
        formats=["%Y-%m-%d"],
        help="Only fetch notifications received on or after this date (YYYY-MM-DD).",
    ),
) -> None:
    """Pull new notifications from the configured source and persist them."""
    fetcher = build_fetcher()
    since_dt: datetime | None = None
    if since is not None:
        since_dt = datetime.combine(date(since.year, since.month, since.day), time.min, tzinfo=UTC)
    try:
        added = asyncio.run(fetcher.fetch_new(since=since_dt))
    except InboxError as exc:
        _CONSOLE.print(f"[red]fetch failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    table = Table(title="inbox fetch", header_style="bold")
    table.add_column("id", style="cyan")
    table.add_column("kind")
    table.add_column("priority")
    table.add_column("effective_at")
    table.add_column("appeal_deadline")
    for record in added:
        table.add_row(
            record.notificacion_id,
            record.kind.value,
            record.priority.value,
            record.effective_at.isoformat(),
            record.appeal_deadline.isoformat() if record.appeal_deadline else "-",
        )
    _CONSOLE.print(table)
    _CONSOLE.print(f"[dim]{len(added)} new notification(s)[/dim]")
