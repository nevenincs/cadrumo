"""``aeat deadlines`` sub-app — filing-deadline computation engine CLI.

Wires three subcommands under ``aeat deadlines``:

- ``aeat deadlines list --year YYYY``
- ``aeat deadlines next [--year YYYY]``
- ``aeat deadlines explain MODELO``

The commands are pure typer glue: they parse arguments, load the active
profile bucket through workflow state, construct an in-process catalogue
implementation, and delegate every domain decision to
:mod:`aeat.domain.deadlines`.
"""

from __future__ import annotations

import typer

from .._i18n import tr
from .explain import explain_modelo
from .list import list_schedule
from .next import next_obligation

app = typer.Typer(
    name="deadlines",
    no_args_is_help=True,
    help=tr("cli.deadlines.app_help"),
)

app.command(name="list", help=tr("cli.deadlines.list_help"))(list_schedule)
app.command(name="next", help=tr("cli.deadlines.next_help"))(next_obligation)
app.command(name="explain", help=tr("cli.deadlines.explain_help"))(explain_modelo)


__all__ = ["app"]
