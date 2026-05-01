"""``aeat deadlines`` sub-app - filing-deadline computation engine CLI.

Wires three subcommands under ``aeat deadlines`` per the deadline
engine ADR [[2026-04-12-deadline-engine-adr]]:

- ``aeat deadlines list --year YYYY [--profile PATH]``
- ``aeat deadlines next [--year YYYY] [--profile PATH]``
- ``aeat deadlines explain MODELO [--profile PATH]``

The commands are pure typer glue: they parse arguments, load the
profile from disk (or from the optional ``AEAT_DEFAULT_PROFILE_PATH``
setting), construct an in-process catalogue implementation, and delegate every
domain decision to :mod:`aeat.domain.deadlines`.
"""

from __future__ import annotations

import typer

from .explain import explain_modelo
from .list import list_schedule
from .next import next_obligation

app = typer.Typer(
    name="deadlines",
    no_args_is_help=True,
    help="Filing-deadline computation engine (#38).",
)

app.command(name="list", help="List the full filing schedule for a year.")(list_schedule)
app.command(name="next", help="Show the next non-overdue filing obligation.")(next_obligation)
app.command(name="explain", help="Explain why a modelo applies to the profile.")(explain_modelo)


__all__ = ["app"]
