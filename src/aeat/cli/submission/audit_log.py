"""``aeat submission audit-log`` — inspect append-only submission audit events."""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from aeat.cli.submission._helpers import build_engine

_CONSOLE = Console()


def audit_log_cmd(
    limit: int = typer.Option(20, "--limit", min=1, help="Maximum number of recent audit records to print."),
    as_json: bool = typer.Option(False, "--json", help="Emit the selected audit records as JSON."),
) -> None:
    """Print recent append-only submission audit records."""
    records = build_engine().list_audit_records(limit=limit)
    if as_json:
        typer.echo(json.dumps([record.model_dump(mode="json") for record in records], indent=2))
        return

    table = Table(title="submission audit log", header_style="bold")
    table.add_column("recorded_at", style="cyan")
    table.add_column("event")
    table.add_column("modelo")
    table.add_column("period")
    table.add_column("status")
    table.add_column("reason")
    for record in records:
        table.add_row(
            record.recorded_at.isoformat(),
            record.event.value,
            record.modelo,
            record.period,
            record.status,
            record.reason or "-",
        )
    _CONSOLE.print(table)
    _CONSOLE.print(f"[dim]{len(records)} record(s)[/dim]")
