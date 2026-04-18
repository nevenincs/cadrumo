"""``aeat review`` sub-app — unified review queue CLI (#232).

Wires the single subcommand under ``aeat review`` per the feature ADR
[[2026-04-18-unified-review-queue-adr]]:

- ``aeat review queue [--kind K]... [--state pending|all] [--modelo M]
  [--format table|json]``

The command delegates every aggregation decision to
:mod:`aeat.review`; this module is pure CLI glue.
"""

from __future__ import annotations

import typer

from .queue import queue_cmd

app = typer.Typer(
    name="review",
    no_args_is_help=True,
    help="Unified review queue across the pipeline (#232).",
)

app.command(
    name="queue",
    help="List every pending review item across the pipeline in one table.",
)(queue_cmd)


__all__ = ["app"]
