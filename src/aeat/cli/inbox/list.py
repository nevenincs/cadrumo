"""``aeat inbox list`` — list persisted notifications."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from ...inbox import NotificacionPriority
from .._observability import cli_run_context
from ._helpers import build_fetcher

_CONSOLE = Console()


def list_cmd(
    unread: bool = typer.Option(False, "--unread", help="Only show unacknowledged records."),
    priority: NotificacionPriority | None = typer.Option(
        None,
        "--priority",
        help="Only show records at this priority (CRITICAL/HIGH/NORMAL/INFO).",
    ),
) -> None:
    """List every persisted notification, optionally filtered."""
    arguments = {"unread": unread, "priority": priority}
    with cli_run_context(entrypoint="aeat inbox list", arguments=arguments):
        fetcher = build_fetcher()
        inbox = fetcher.load_inbox()
        records = list(inbox.values())
        if unread:
            records = [r for r in records if r.acknowledged_at is None]
        if priority is not None:
            records = [r for r in records if r.priority is priority]
        records.sort(key=lambda r: (r.appeal_deadline or r.effective_at.date(),))

        table = Table(title="inbox", header_style="bold")
        table.add_column("id", style="cyan")
        table.add_column("kind")
        table.add_column("priority")
        table.add_column("deadline")
        table.add_column("ack")
        for record in records:
            table.add_row(
                record.notificacion_id,
                record.kind.value,
                record.priority.value,
                record.appeal_deadline.isoformat() if record.appeal_deadline else "-",
                record.acknowledged_by or "-",
            )
        _CONSOLE.print(table)
        _CONSOLE.print(f"[dim]{len(records)} record(s)[/dim]")
