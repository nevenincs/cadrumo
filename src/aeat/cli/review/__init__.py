"""``aeat review`` sub-app — pipeline-decision review surfaces.

Wires the review subcommands per the feature ADRs:

- ``aeat review queue [--kind K]... [--state pending|all] [--modelo M]
  [--format table|json]`` — unified pending-review dashboard
  (#232, [[2026-04-18-unified-review-queue-adr]]).
- ``aeat review history <transaction-id>`` — classification history
  chain for one transaction (#237).

These commands delegate every domain decision to :mod:`aeat.review`
or :mod:`aeat.financial.transactions`; this module is pure CLI glue.
"""

from __future__ import annotations

import typer

from .history import history_cmd
from .queue import queue_cmd

app = typer.Typer(
    name="review",
    no_args_is_help=True,
    help="Pipeline-decision review surfaces (#232 unified queue, #237 classification history).",
)

app.command(
    name="queue",
    help="List every pending review item across the pipeline in one table.",
)(queue_cmd)
app.command(
    name="history",
    help="Show the classification history chain for one transaction (#237).",
)(history_cmd)


__all__ = ["app"]
