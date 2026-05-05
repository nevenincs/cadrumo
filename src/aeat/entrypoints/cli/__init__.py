"""User-facing ``aeat`` CLI.

The command tree exposes two top-level namespaces:

- ``aeat setup`` — local prerequisites: profile, authentication, status.
- ``aeat app`` — operational tax work: overview, ledger, invoice,
  declaration.

Every command in this package is a thin transport over the backend API.
The handler bodies parse argv, call into
``aeat.application`` / ``aeat.domain``, and render the typed result.
No business logic lives in the CLI layer: validation, mutation,
schema-decision, and persistence all live behind the imported
application functions and pydantic records.
"""

from __future__ import annotations

import typer

from . import _declaration, _invoice, _ledger, _overview, _setup, registry
from ._common import _FORMAT_TEXT
from ._i18n import tr

# ---------------------------------------------------------------------
# Root app + callback
# ---------------------------------------------------------------------


app = typer.Typer(
    name="aeat",
    help=tr("cli.root.app_help"),
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def _root(
    ctx: typer.Context,
    format_: str = typer.Option(
        _FORMAT_TEXT,
        "--format",
        help=tr("cli.root.format_help"),
    ),
) -> None:
    """Capture root-level CLI flags into the Typer context."""
    state = ctx.ensure_object(dict)
    state["format"] = format_.strip().lower() or _FORMAT_TEXT


# ---------------------------------------------------------------------
# `aeat app` — workflow aggregator
# ---------------------------------------------------------------------


app_app = typer.Typer(
    name="app",
    help=tr("cli.root.app_app_help"),
    no_args_is_help=True,
)

app_app.add_typer(_overview.app, name="overview")
app_app.add_typer(_ledger.app, name="ledger")
app_app.add_typer(_invoice.app, name="invoice")
app_app.add_typer(_declaration.app, name="declaration")
app_app.add_typer(registry.app, name="registry")


# ---------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------


app.add_typer(_setup.app, name="setup")
app.add_typer(app_app, name="app")


__all__ = ["app"]
