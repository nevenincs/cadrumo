"""``aeat workflow`` sub-app — end-user composite workflow CLI.

Exposes four subcommands tied to the workflow engine
:mod:`aeat.application.workflow`:

- ``aeat workflow next`` — run :meth:`WorkflowEngine.run_next`.
- ``aeat workflow run`` — run :meth:`WorkflowEngine.run_for_period`.
- ``aeat workflow show <run-id>`` — pretty-print a persisted
  :class:`aeat.application.workflow.WorkflowResult`.
- ``aeat workflow list [--since <iso-date>]`` — enumerate persisted
  runs.

The ``next`` and ``run`` subcommands are read-only on the default
CLI surface. Live AEAT submission is permanently forbidden, so these
subcommands only participate in the produce -> verify -> export flow.
"""

from __future__ import annotations

import typer

from .list_cmd import list_cmd
from .next import next_cmd
from .run import run_cmd
from .show import show_cmd

app = typer.Typer(
    name="workflow",
    no_args_is_help=True,
    help="Drive Kent's produce -> verify -> export filing workflow.",
)

app.command(
    name="next",
    help="Run the read-only workflow for the next pending obligation.",
)(next_cmd)
app.command(
    name="run",
    help="Run the workflow for a specific (modelo, period) target.",
)(run_cmd)
app.command(name="show", help="Pretty-print a persisted WorkflowResult by run_id.")(show_cmd)
app.command(name="list", help="List persisted WorkflowResult records.")(list_cmd)

__all__ = ["app"]
