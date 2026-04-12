"""``aeat inbox show`` — pretty-print a persisted notification."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.json import JSON

from aeat.cli.inbox._helpers import build_fetcher

_CONSOLE = Console()


def show_cmd(
    notificacion_id: str = typer.Argument(..., help="The notificacion_id to load."),
) -> None:
    """Load and pretty-print a persisted :class:`Notificacion`."""
    fetcher = build_fetcher()
    inbox = fetcher.load_inbox()
    record = inbox.get(notificacion_id)
    if record is None:
        _CONSOLE.print(f"[red]not found:[/red] {notificacion_id}")
        raise typer.Exit(code=1)
    _CONSOLE.print(JSON(record.model_dump_json(indent=2)))
