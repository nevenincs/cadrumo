"""``aeat data ledgers`` command group."""

from __future__ import annotations

import typer

from . import inventory as inventory_module

app = typer.Typer(
    name="ledgers",
    no_args_is_help=True,
    help="Encrypted inventory ledgers.",
)
app.add_typer(inventory_module.app, name="inventory", help="Stock movements and valuation by actividad.")

__all__ = ["app"]
