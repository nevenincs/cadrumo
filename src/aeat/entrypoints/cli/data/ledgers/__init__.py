"""``aeat data ledgers`` command group."""

from __future__ import annotations

import typer

from ..._i18n import tr
from . import inventory as inventory_module

app = typer.Typer(
    name="ledgers",
    no_args_is_help=True,
    help=tr("cli.data.ledgers.app_help"),
)
app.add_typer(inventory_module.app, name="inventory", help=tr("cli.data.ledgers.inventory_help"))

__all__ = ["app"]
