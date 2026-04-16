"""``aeat workflow`` sub-app — end-user composite workflow CLI.

Exposes four subcommands tied to the workflow engine
:mod:`aeat.workflow`:

- ``aeat workflow next`` — run :meth:`WorkflowEngine.run_next`.
- ``aeat workflow run`` — run :meth:`WorkflowEngine.run_for_period`.
- ``aeat workflow show <run-id>`` — pretty-print a persisted
  :class:`aeat.workflow.WorkflowResult`.
- ``aeat workflow list [--since <iso-date>]`` — enumerate persisted
  runs.

Submit-oriented commands require an explicit ``--dry-run`` or
``--live`` choice to match the hardened submission-engine contract.
"""

from __future__ import annotations

import typer

from aeat.cli.workflow.list_cmd import list_cmd
from aeat.cli.workflow.next import next_cmd
from aeat.cli.workflow.run import run_cmd
from aeat.cli.workflow.show import show_cmd

app = typer.Typer(
    name="workflow",
    no_args_is_help=True,
    help="End-user composite workflow engine (#59).",
)

app.command(
    name="next",
    help="Run the workflow for the next pending obligation with explicit mode selection.",
)(next_cmd)
app.command(
    name="run",
    help="Run the workflow for a specific (modelo, period) target with explicit mode selection.",
)(run_cmd)
app.command(name="show", help="Pretty-print a persisted WorkflowResult by run_id.")(show_cmd)
app.command(name="list", help="List persisted WorkflowResult records.")(list_cmd)

__all__ = ["app"]
