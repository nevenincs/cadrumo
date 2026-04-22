"""``aeat run`` sub-app — run-trace inspection and dry-run replay (#99).

Wires three subcommands under ``aeat run``:

- ``aeat run list`` — table of persisted runs.
- ``aeat run show <run_id>`` — pretty-print a :class:`RunTrace` and its events.
- ``aeat run replay <run_id> [--dry-run/--no-dry-run]`` — deterministic
  dry-run replay gated on ``corpus_sha256`` drift.
"""

from __future__ import annotations

import typer

from .list_cmd import list_cmd
from .replay import replay_cmd
from .show import show_cmd

app = typer.Typer(
    name="run",
    no_args_is_help=True,
    help="Run-trace inspection and deterministic dry-run replay (#99).",
)

app.command(name="list", help="List persisted run traces.")(list_cmd)
app.command(name="show", help="Pretty-print a persisted RunTrace and its events.")(show_cmd)
app.command(name="replay", help="Deterministic dry-run replay of a recorded run.")(replay_cmd)


__all__ = ["app"]
