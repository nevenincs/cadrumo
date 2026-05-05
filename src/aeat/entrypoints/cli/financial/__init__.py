"""``aeat financial`` sub-app for ingest, transaction, and invoice catalogues.

Aggregates the financial-input pipeline command surface:

- ``ingest`` validates and loads CSV/XLSX/OFX/PDF sources into
  :class:`aeat.domain.transactions.RawTransaction` records.
- :mod:`aeat.entrypoints.cli.financial.txs` manages the transaction
  catalogue.
- :mod:`aeat.entrypoints.cli.financial.invoices` manages the invoice
  catalogue.
- :mod:`aeat.entrypoints.cli.financial.profile` edits the operator's
  per-category usage-ratio profile.
"""

from __future__ import annotations

import typer

from .._i18n import tr
from .ingest import ingest_cmd
from .invoices import app as invoices_app
from .profile import app as profile_app
from .txs import app as txs_app

app = typer.Typer(
    name="financial",
    no_args_is_help=True,
    help=tr("cli.financial.app_help"),
)

app.command(
    name="ingest",
    help=tr("cli.financial.ingest.help"),
)(ingest_cmd)
app.add_typer(
    txs_app,
    name="txs",
    help=tr("cli.financial.txs.app_help"),
)
app.add_typer(
    invoices_app,
    name="invoices",
    help=tr("cli.financial.invoices.app_help"),
)
app.add_typer(
    profile_app,
    name="profile",
    help=tr("cli.financial.profile.app_help"),
)


__all__ = ["app"]
