"""`aeat financial` sub-app for ingest, transaction, and invoice catalogues."""

from __future__ import annotations

import typer

from .ingest import ingest_cmd
from .invoices import app as invoices_app
from .profile import app as profile_app
from .txs import app as txs_app

app = typer.Typer(
    name="financial",
    no_args_is_help=True,
    help="Financial ingest providers, transaction catalogue, and invoice catalogue (#73, #74, #75).",
)

app.command(
    name="ingest",
    help="Validate and ingest a CSV/XLSX/OFX/PDF source into RawTransaction records.",
)(ingest_cmd)
app.add_typer(
    txs_app,
    name="txs",
    help="Transaction catalogue helpers (#74).",
)
app.add_typer(
    invoices_app,
    name="invoices",
    help="Invoice catalogue helpers (#75).",
)
app.add_typer(
    profile_app,
    name="profile",
    help="Kent's financial profile: per-category usage ratios (#259).",
)


__all__ = ["app", "invoices_app", "profile_app"]
