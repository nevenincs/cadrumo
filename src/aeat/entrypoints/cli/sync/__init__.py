"""``aeat sync`` sub-app -- self-healing sync runner CLI.

Wires four subcommands under ``aeat sync``:

- ``aeat sync run [--modelo ID] [--period P] [--auto-heal]``
- ``aeat sync list-divergences [--state S]``
- ``aeat sync show-divergence <record-id>``
- ``aeat sync resolve-divergence <record-id> --action approve|reject
  [--notes TEXT]``

The commands delegate every domain decision to
:mod:`aeat.application.sync`; this module is pure CLI glue that
binds Typer command names to the underlying handler functions.
"""

from __future__ import annotations

import typer

from .list import list_divergences
from .resolve import resolve_divergence
from .run import run
from .show import show_divergence

app = typer.Typer(
    name="sync",
    no_args_is_help=True,
    help="Self-healing live-to-local sync runner (#11).",
)

app.command(name="run", help="Execute a single live-to-local sync run.")(run)
app.command(
    name="list-divergences",
    help="List persisted divergence records.",
)(list_divergences)
app.command(
    name="show-divergence",
    help="Show the full payload of a divergence record.",
)(show_divergence)
app.command(
    name="resolve-divergence",
    help="Approve or reject a PENDING divergence record.",
)(resolve_divergence)


__all__ = ["app"]
