"""``aeat justificante`` sub-app — PDF receipt parser + live CSV verify (#44).

Subcommands:

- ``aeat justificante parse <pdf-path>`` — parse a PDF and pretty-print it.
- ``aeat justificante verify <pdf-path>`` — parse + live-verify the CSV
  against AEAT's Sede electrónica.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from ....core.logging import get_logger
from ....domain.justificante import (
    Justificante,
    JustificanteError,
    parse_justificante,
    verify_csv,
)

app = typer.Typer(
    name="justificante",
    no_args_is_help=True,
    help="AEAT justificante (PDF receipt) parser and live verifier (#44).",
)

_console = Console()
_logger = get_logger(__name__)


def _render(record: Justificante) -> None:
    """Pretty-print a parsed justificante to the console."""
    table = Table(title=f"Justificante {record.csv}", show_header=False)
    table.add_row("modelo", record.modelo)
    table.add_row("period", record.period)
    table.add_row("tax_id", record.tax_id)
    table.add_row("presentation_id", record.presentation_id or "-")
    table.add_row("presented_at", record.presented_at.isoformat())
    table.add_row(
        "total_a_ingresar",
        "-" if record.total_a_ingresar is None else str(record.total_a_ingresar),
    )
    table.add_row(
        "total_a_devolver",
        "-" if record.total_a_devolver is None else str(record.total_a_devolver),
    )
    table.add_row("verification_url", str(record.verification_url))
    table.add_row("source_pdf_path", str(record.source_pdf_path))
    table.add_row("source_pdf_sha256", record.source_pdf_sha256)
    table.add_row("parsed_at", record.parsed_at.isoformat())
    _console.print(table)


@app.command("parse")
def parse(
    pdf_path: Annotated[Path, typer.Argument(help="Path to a justificante PDF")],
) -> None:
    """Parse ``pdf_path`` and pretty-print the resulting record."""
    try:
        record = parse_justificante(pdf_path)
    except JustificanteError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _render(record)


@app.command("verify")
def verify(
    pdf_path: Annotated[Path, typer.Argument(help="Path to a justificante PDF")],
) -> None:
    """Parse ``pdf_path`` and live-verify its CSV against AEAT."""
    try:
        record = parse_justificante(pdf_path)
    except JustificanteError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _render(record)
    typer.echo(f"Verifying CSV {record.csv} against AEAT...")
    try:
        ok = asyncio.run(verify_csv(record.csv))
    except JustificanteError as exc:
        typer.echo(f"verification failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"AEAT verification result: {'VALID' if ok else 'UNKNOWN'}")


__all__ = ["app"]
