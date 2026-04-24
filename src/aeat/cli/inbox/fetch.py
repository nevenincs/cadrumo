"""``aeat inbox fetch`` — pull new notifications from the source."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, time

import typer
from rich.console import Console
from rich.table import Table

from ...config import load_settings
from ...inbox import InboxError, Notificacion
from .._live_reader import LiveSessionUnavailableError, build_live_status_reader
from .._observability import cli_run_context
from ._helpers import build_fetcher, build_live_source

_CONSOLE = Console()


def fetch_cmd(
    since: datetime | None = typer.Option(
        None,
        "--since",
        formats=["%Y-%m-%d"],
        help="Only fetch notifications received on or after this date (YYYY-MM-DD).",
    ),
    from_aeat: bool = typer.Option(
        False,
        "--from-aeat",
        help=(
            "Pull notifications live from the authenticated AEAT Sede via "
            "StatusReader. Requires an active `aeat auth login` session. "
            "Default is the safe file-backed source."
        ),
    ),
) -> None:
    """Pull new notifications from the configured source and persist them."""
    arguments = {
        "since": since.isoformat() if since is not None else None,
        "from_aeat": from_aeat,
    }
    with cli_run_context(entrypoint="aeat inbox fetch", arguments=arguments):
        since_dt: datetime | None = None
        if since is not None:
            since_dt = datetime.combine(date(since.year, since.month, since.day), time.min, tzinfo=UTC)

        try:
            added = asyncio.run(_run(since_dt, from_aeat=from_aeat))
        except LiveSessionUnavailableError as exc:
            _CONSOLE.print(f"[red]live fetch unavailable:[/red] {exc}")
            raise typer.Exit(code=2) from exc
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


async def _run(since_dt: datetime | None, *, from_aeat: bool) -> tuple[Notificacion, ...]:
    """Resolve the source and run an inbox fetch.

    Keeping the async plumbing here lets the sync click/typer shell
    stay free of nested event-loop boilerplate, and lets
    :func:`build_live_status_reader` clean up the reader deterministically.
    """
    settings = load_settings()
    if not from_aeat:
        fetcher = build_fetcher(settings)
        return await fetcher.fetch_new(since=since_dt)
    async with build_live_status_reader(settings) as reader:
        fetcher = build_fetcher(settings, source=build_live_source(reader))
        return await fetcher.fetch_new(since=since_dt)
