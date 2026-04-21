"""``aeat inbox ack`` — mark a notification as locally acknowledged.

Acknowledgement is **local state only** — see
[[2026-04-12-notifications-inbox-adr]] decision D1. This command
does not tell AEAT anything.
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console

from ...inbox import InboxError
from .._observability import cli_run_context
from ._helpers import build_fetcher

_CONSOLE = Console()


def ack_cmd(
    notificacion_id: str = typer.Argument(..., help="The notificacion_id to acknowledge."),
    by: str = typer.Option(..., "--by", help="Short identifier (e.g. user initials)."),
) -> None:
    """Mark a notification as acknowledged in the **local** inbox.

    This is bookkeeping only — it does not tell AEAT anything.
    """
    arguments = {"notificacion_id": notificacion_id, "by": by}
    with cli_run_context(
        entrypoint="aeat inbox ack",
        arguments=arguments,
        positional=("notificacion_id",),
    ):
        fetcher = build_fetcher()
        try:
            record = asyncio.run(fetcher.acknowledge(notificacion_id, by=by))
        except InboxError as exc:
            _CONSOLE.print(f"[red]ack failed:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        _CONSOLE.print(
            f"[green]acknowledged[/green] {record.notificacion_id} by {record.acknowledged_by} "
            f"(local only — AEAT is not notified)"
        )
