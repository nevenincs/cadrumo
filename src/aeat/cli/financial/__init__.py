"""`aeat financial` sub-app for T1 ingest and transaction catalogue commands."""

from __future__ import annotations

import typer

from .ingest import ingest_cmd
from .txs import app as txs_app

app = typer.Typer(
    name="financial",
    no_args_is_help=True,
    help="Financial ingest providers and transaction catalogue helpers (#73, #74).",
)

app.command(
    name="ingest",
    help="Validate and ingest a CSV/XLSX/OFX source into RawTransaction records.",
)(ingest_cmd)
app.add_typer(
    txs_app,
    name="txs",
    help="Transaction catalogue helpers (#74).",
)


__all__ = ["app"]
