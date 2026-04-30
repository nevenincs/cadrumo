"""Kent-facing local data commands."""

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
