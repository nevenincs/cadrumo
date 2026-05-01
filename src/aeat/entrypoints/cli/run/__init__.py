"""``aeat run`` Typer sub-app for run-trace inspection and read-only replay.

Wires three subcommands under ``aeat run``:

- ``aeat run list`` — table of persisted runs.
- ``aeat run show <run_id>`` — pretty-print a
  :class:`aeat.core.observability.RunTrace` and its event log.
- ``aeat run replay <run_id>`` — deterministic read-only replay gated
  on ``corpus_sha256`` drift via
  :exc:`aeat.core.observability.AeatCorpusDriftError`.
"""

from __future__ import annotations

import typer

from .list_cmd import list_cmd
from .replay import replay_cmd
from .show import show_cmd

app = typer.Typer(
    name="run",
    no_args_is_help=True,
    help="Run-trace inspection and deterministic read-only replay.",
)

app.command(name="list", help="List persisted run traces.")(list_cmd)
app.command(name="show", help="Pretty-print a persisted RunTrace and its events.")(show_cmd)
app.command(name="replay", help="Deterministic read-only replay of a recorded run.")(replay_cmd)


__all__ = ["app"]
