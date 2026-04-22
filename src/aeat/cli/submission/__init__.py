"""``aeat submission`` sub-app — preflight and dry-run filing helpers.

Wires four subcommands under ``aeat submission`` per the submission
engine ADR [[2026-04-12-submission-engine-adr]] and the live-submit
excision ADR [[2026-04-18-live-submit-cli-excision-adr]]:

- ``aeat submission preflight <draft-path>`` — run preflight only.
- ``aeat submission dry-run <draft-path>`` — full walk, abort before submit.
- ``aeat submission show <submission-id>`` — pretty-print a persisted
  :class:`aeat.submission.SubmittedFiling`.
- ``aeat submission list [--modelo ...] [--status ...]`` — list every
  persisted filing, optionally filtered.

The previously-registered ``submit`` subcommand was removed per the
2026-04-18 excision ADR. Kent's normal CLI path remains produce ->
verify -> export, with live submission deferred to 1.0.0 behind
stricter gates outside the default surface. Programmatic callers that
genuinely need the live path must construct
:class:`aeat.submission.SubmissionEngine` with explicit
``live_transport_supported=True`` — a default-constructed engine
raises :class:`AeatLiveTransportUnavailableError` on
``submit_draft(dry_run=False)``.
"""

from __future__ import annotations

import typer

from .check_nif import check_nif_cmd
from .diff import diff_cmd
from .dry_run import dry_run_cmd
from .export import export_cmd
from .list import list_cmd
from .preflight import preflight_cmd
from .schemas import schemas_cmd
from .show import show_cmd
from .verify import verify_cmd

app = typer.Typer(
    name="submission",
    no_args_is_help=True,
    help="Preflight, dry-run, export, and inspect AEAT filing attempts; no default CLI live-submit command.",
)

app.command(name="preflight", help="Run preflight gates against a draft (no browser action).")(preflight_cmd)
app.command(name="dry-run", help="Run the full portal walk, aborting before the final submit.")(dry_run_cmd)
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
