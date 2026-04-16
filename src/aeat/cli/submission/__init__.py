"""``aeat submission`` sub-app — CLI surface for the filing submission engine.

Wires five subcommands under ``aeat submission`` per the submission
engine ADR [[2026-04-12-submission-engine-adr]]:

- ``aeat submission preflight <draft-path>`` — run preflight only.
- ``aeat submission dry-run <draft-path>`` — full walk, abort before submit.
- ``aeat submission submit <draft-path> --dry-run|--live`` — explicit
  execution-mode entry point for the submit leg.
- ``aeat submission audit-log`` — inspect append-only audit records.
- ``aeat submission show <submission-id>`` — pretty-print a persisted
  :class:`aeat.submission.SubmittedFiling`.
- ``aeat submission list [--modelo ...] [--status ...]`` — list every
  persisted filing, optionally filtered.
"""

from __future__ import annotations

import typer

from .audit_log import audit_log_cmd
from .dry_run import dry_run_cmd
from .list import list_cmd
from .preflight import preflight_cmd
from .show import show_cmd
from .submit import submit_cmd

app = typer.Typer(
    name="submission",
    no_args_is_help=True,
    help="Filing submission engine (#42).",
)

app.command(name="preflight", help="Run preflight gates against a draft (no browser action).")(preflight_cmd)
app.command(name="dry-run", help="Run the full portal walk, aborting before the final submit.")(dry_run_cmd)
app.command(
    name="submit",
    help="Explicit submit entry point. Requires exactly one of --dry-run or --live.",
)(submit_cmd)
app.command(name="audit-log", help="Inspect append-only submission audit records.")(audit_log_cmd)
app.command(name="show", help="Pretty-print a persisted SubmittedFiling by submission_id.")(show_cmd)
app.command(name="list", help="List persisted SubmittedFiling records.")(list_cmd)


__all__ = ["app"]
