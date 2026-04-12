"""``aeat status`` sub-app — live AEAT status reader CLI (#43).

Wires one subcommand per status surface under ``aeat status``. Only
the ``expedientes`` command is fully wired in v1; the remaining
subcommands construct the reader and invoke its stub fetchers,
which raise :class:`aeat.status.StatusReaderError`. That is
surfaced to the operator as ``typer.Exit(1)`` with a clear message.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from aeat.config import load_settings
from aeat.logging import get_logger
from aeat.status import (
    Expediente,
    StatusCache,
    StatusReader,
    StatusReaderError,
)

logger = get_logger(__name__)

app = typer.Typer(
    name="status",
    no_args_is_help=True,
    help=(
        "Live AEAT status reader (#43): expedientes, notificaciones, "
        "devoluciones, borrador, datos fiscales, calendario."
    ),
)

_CONSOLE = Console()


def _not_yet_wired(surface: str) -> None:
    """Emit a uniform "not yet implemented" error for stub surfaces."""
    _CONSOLE.print(f"[yellow]status surface '{surface}' not yet implemented in v1 — see #43 follow-up[/yellow]")
    raise typer.Exit(code=1)


def _render_expedientes_table(records: tuple[Expediente, ...]) -> None:
    table = Table(title=f"Mis expedientes ({len(records)} row(s))", header_style="bold")
    table.add_column("expediente_id", style="cyan")
    table.add_column("modelo")
    table.add_column("period")
    table.add_column("status")
    table.add_column("presented_at")
    table.add_column("csv")
    for r in records:
        table.add_row(
            r.expediente_id,
            r.modelo,
            r.period,
            r.status,
            r.presented_at.isoformat(),
            r.csv or "-",
        )
    _CONSOLE.print(table)


def _emit_json(records: tuple[Any, ...]) -> None:
    payload = [r.model_dump(mode="json") for r in records]
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


@app.command("expedientes", help="List 'Mis expedientes' rows.")
def expedientes(
    since: str | None = typer.Option(
        None,
        "--since",
        help="Filter by presented_at >= YYYY-MM-DD.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit JSON instead of a pretty table.",
    ),
) -> None:
    """Fetch and display the user's expediente history."""
    since_date = date.fromisoformat(since) if since else None
    records = asyncio.run(_run_expedientes(since_date))
    if json_output:
        _emit_json(records)
    else:
        _render_expedientes_table(records)


async def _run_expedientes(since: date | None) -> tuple[Expediente, ...]:
    _, reader = _build_reader_unused_browser()
    try:
        return await reader.fetch_expedientes(since=since)
    except StatusReaderError as exc:
        _CONSOLE.print(f"[red]status fetch failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    finally:
        await reader.close()


def _build_reader_unused_browser() -> tuple[None, StatusReader]:
    """Construct a :class:`StatusReader` for CLI use.

    This helper intentionally raises if called without a live
    Playwright runtime — in v1 the CLI requires a running browser
    and a concrete cert backend. Unit tests never call this helper;
    they build :class:`StatusReader` directly.
    """
    settings = load_settings()
    cache = StatusCache(
        settings.aeat_status_cache_dir,
        ttl_s=settings.aeat_status_cache_ttl_s,
    )
    # The concrete browser + cert wiring lands when #8 merges. Until
    # then, the CLI path errors out cleanly instead of booting a
    # half-wired pipeline.
    _ = cache
    _CONSOLE.print(
        "[red]aeat status CLI requires the cert auth backend (#8) and a "
        "live Playwright runtime; run the reader programmatically in the "
        "meantime.[/red]"
    )
    raise typer.Exit(code=2)


@app.command("notificaciones", help="List 'Mis notificaciones' rows.")
def notificaciones(
    since: str | None = typer.Option(None, "--since"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Stub: not yet implemented in v1."""
    del since, json_output
    _not_yet_wired("notificaciones")


@app.command("devoluciones", help="List 'Mis devoluciones' rows.")
def devoluciones(
    year: int | None = typer.Option(None, "--year"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Stub: not yet implemented in v1."""
    del year, json_output
    _not_yet_wired("devoluciones")


@app.command("borrador", help="Show the IRPF draft state.")
def borrador(
    year: int = typer.Option(..., "--year"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Stub: not yet implemented in v1."""
    del year, json_output
    _not_yet_wired("borrador")


@app.command("datos-fiscales", help="Show third-party tax data.")
def datos_fiscales(
    year: int = typer.Option(..., "--year"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Stub: not yet implemented in v1."""
    del year, json_output
    _not_yet_wired("datos-fiscales")


@app.command("calendario", help="Show the personalised filing calendar.")
def calendario(
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Stub: not yet implemented in v1."""
    del json_output
    _not_yet_wired("calendario")


__all__ = ["app"]
