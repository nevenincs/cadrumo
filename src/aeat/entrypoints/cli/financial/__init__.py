"""``aeat financial`` sub-app for ingest, transaction, and invoice catalogues.

Aggregates the financial-input pipeline command surface:

- ``ingest`` validates and loads CSV/XLSX/OFX/PDF sources into
  :class:`aeat.domain.transactions.RawTransaction` records.
- ``aggregate`` rolls classified transactions up into AEAT casilla
  inputs.
- :mod:`aeat.entrypoints.cli.financial.txs` manages the transaction
  catalogue.
- :mod:`aeat.entrypoints.cli.financial.invoices` manages the invoice
  catalogue.
- :mod:`aeat.entrypoints.cli.financial.profile` edits the operator's
  per-category usage-ratio profile.
"""

from __future__ import annotations

import typer

from .aggregate import aggregate_cmd
from .ingest import ingest_cmd
from .invoices import app as invoices_app
from .profile import app as profile_app
from .txs import app as txs_app

app = typer.Typer(
    name="financial",
    no_args_is_help=True,
    help="Financial ingest providers, transaction catalogue, and invoice catalogue.",
)

app.command(
    name="ingest",
    help="Validate and ingest a CSV/XLSX/OFX/PDF source into RawTransaction records.",
)(ingest_cmd)
app.command(
    name="aggregate",
    help="Aggregate classified transactions into AEAT casilla inputs.",
)(aggregate_cmd)
app.add_typer(
    txs_app,
    name="txs",
    help="Transaction catalogue helpers.",
)
app.add_typer(
    invoices_app,
    name="invoices",
    help="Invoice catalogue helpers.",
)
app.add_typer(
    profile_app,
    name="profile",
    help="Operator financial profile: per-category usage ratios.",
)


__all__ = ["app"]
