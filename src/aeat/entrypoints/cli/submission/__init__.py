"""Expose the ``aeat submission`` Typer sub-app for local filing operations.

Wires every read-only and export-only command under ``aeat submission``:

- ``aeat submission preflight <draft-path>`` runs the preflight gates
  against a persisted draft (no browser action).
- ``aeat submission export <draft-path>`` exports an approved draft to
  an AEAT-importable ``fichero-BOE`` file.
- ``aeat submission verify <file>`` re-parses an exported fichero-BOE
  file and prints its decoded headers and casillas.
- ``aeat submission diff <a> <b>`` diffs two fichero-BOE files and
  reports byte and per-casilla deltas.
- ``aeat submission schemas`` lists every ``(modelo, ejercicio)`` pair
  the CLI can export and verify.
- ``aeat submission check-nif <id>`` validates a Spanish NIF / NIE / CIF
  against AEAT's check-letter rules.
- ``aeat submission show <submission-id>`` pretty-prints a persisted
  :class:`aeat.adapters.outbound.aeat.export.SubmittedFiling`.
- ``aeat submission list [--modelo ...] [--status ...]`` lists every
  persisted filing, optionally filtered.

The previously-registered ``submit`` and ``dry-run`` subcommands are
absent by design. The supported CLI path is
produce -> verify -> export. Live AEAT submission and write-shaped
portal walks are permanently forbidden.
"""

from __future__ import annotations

import typer

from .check_nif import check_nif_cmd
from .diff import diff_cmd
from .export import export_cmd
from .list import list_cmd
from .preflight import preflight_cmd
from .schemas import schemas_cmd
from .show import show_cmd
from .verify import verify_cmd

app = typer.Typer(
    name="submission",
    no_args_is_help=True,
    help="Preflight, export, verify, and inspect local AEAT filing records; the tool never writes to AEAT.",
)

app.command(name="preflight", help="Run preflight gates against a draft (no browser action).")(preflight_cmd)
app.command(name="export", help="Export an approved draft to an AEAT-importable fichero-BOE file.")(export_cmd)
app.command(name="verify", help="Re-parse an exported fichero-BOE file and print its decoded headers + casillas.")(
    verify_cmd
)
app.command(
    name="diff",
    help="Diff two fichero-BOE files and report byte + per-casilla deltas.",
)(diff_cmd)
app.command(
    name="schemas",
    help="List every (modelo, ejercicio) the CLI can export + verify.",
)(schemas_cmd)
app.command(
    name="check-nif",
    help="Validate a Spanish NIF / NIE / CIF against AEAT's check-letter rules.",
)(check_nif_cmd)
app.command(name="show", help="Pretty-print a persisted SubmittedFiling by submission_id.")(show_cmd)
app.command(name="list", help="List persisted SubmittedFiling records.")(list_cmd)


__all__ = ["app"]
