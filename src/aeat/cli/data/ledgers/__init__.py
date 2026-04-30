"""`aeat data ledgers` command group."""

from __future__ import annotations

import typer

from . import anexo_d as anexo_d_module
from . import assets as assets_module
from . import inventory as inventory_module

app = typer.Typer(
    name="ledgers",
    no_args_is_help=True,
    help="Encrypted ledgers for assets, amortization, and inventory.",
)
app.add_typer(assets_module.app, name="assets", help="Technical kit and other depreciable assets.")
app.add_typer(inventory_module.app, name="inventory", help="Stock movements and valuation by actividad.")
app.add_typer(anexo_d_module.app, name="anexo-d", help="Modelo 100 Anexo D ledger preview.")

__all__ = ["app"]
