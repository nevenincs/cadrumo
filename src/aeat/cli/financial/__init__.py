"""`aeat financial` sub-app for T1 ingest commands."""

from __future__ import annotations

import typer

from .ingest import ingest_cmd

app = typer.Typer(
    name="financial",
    no_args_is_help=True,
    help="Financial ingest providers and raw transaction helpers (#73).",
)

app.command(
    name="ingest",
    help="Validate and ingest a CSV/XLSX/OFX source into RawTransaction records.",
)(ingest_cmd)


__all__ = ["app"]
