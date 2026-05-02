"""Operator-facing local data commands.

Hosts the :mod:`aeat.entrypoints.cli.data.ledgers` sub-app, which
exposes the encrypted local ledgers that back AEAT amortization,
inventory, and Anexo D inputs.
"""

from __future__ import annotations

import typer

from . import ledgers as ledgers_module

app = typer.Typer(
    name="data",
    no_args_is_help=True,
    help="Local encrypted data ledgers.",
)
app.add_typer(ledgers_module.app, name="ledgers", help="Inventory and amortization ledgers.")

__all__ = ["app"]
