"""``aeat`` command-line surface.

Sub-modules expose Typer sub-apps that are wired into the root
``app`` exposed at the package root. The CLI is Kent's command-line
route through the produce -> verify -> export workflow: setup, doctor,
deadlines, filing drafts, guarded AEAT reads, and audit helpers.

The package exposes ``app`` directly so the project entry point in
``pyproject.toml`` reads ``aeat = "aeat.cli:app"``, matching the
single-file convention introduced by the base module structure.
"""

from __future__ import annotations

import logging

import typer

from . import attachments as attachments_module
from . import audit as audit_module
from . import auth as auth_module
from . import bootstrap as bootstrap_module
from . import browser as browser_module
from . import casillas as casillas_module
from . import categories as categories_module
from . import cloud as cloud_module
from . import deadlines as deadlines_module
from . import docs as docs_module
from . import doctor as doctor_module
from . import drive as drive_module
from . import filing as filing_module
from . import financial as financial_module
from . import formulas as formulas_module
from . import justificante as justificante_module
from . import llm as llm_module
from . import manual as manual_module
from . import modelos as modelos_module
from . import normatives as normatives_module
from . import oauth as oauth_module
from . import portals as portals_module
from . import rental as rental_module
from . import review as review_module
from . import run as run_module
from . import sanitize as sanitize_module
from . import schema as schema_module
from . import secrets as secrets_module
from . import security as security_module
from . import sede as sede_module
from . import setup as setup_wizard_module
from . import sheets as sheets_module
from . import submission as submission_module
from . import sync as sync_module
from . import vat as vat_module
from . import workflow as workflow_module
from ._errors import decorate_typer_app
from ._exit_codes import ExitCode, exit_with
from ._log_levels import LogLevel, LogLevelResolutionError, apply_to_root_logger, resolve_log_level
from ._schemas import (
    SCHEMA_REGISTRY,
    OutputSchema,
    OutputSchemaError,
    SchemaEnvelope,
    emit_json_document,
    register_schema,
)
from ._tty import (
    NonTtyRefusedError,
    is_stderr_tty,
    is_stdin_tty,
    is_stdout_tty,
    refuse_if_stdin_non_tty,
    should_show_rich_progress,
    should_use_color,
)

app = typer.Typer(
    name="aeat",
    help="File your Spanish tax returns: produce, verify, and export AEAT-ready drafts and records.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Enable machine-readable JSON mode for commands that support the shared contract.",
    ),
    quiet: bool = typer.Option(False, "--quiet", help="Only emit errors on stderr."),
    verbose: bool = typer.Option(False, "--verbose", help="Emit info-level operation summaries."),
    debug: bool = typer.Option(False, "--debug", help="Emit debug-level diagnostics on stderr."),
    no_color: bool = typer.Option(False, "--no-color", help="Disable ANSI colour output."),
    no_progress: bool = typer.Option(False, "--no-progress", help="Disable progress reporting on stderr."),
) -> None:
    """Apply root-level CLI transport defaults for the current invocation."""

    state = ctx.ensure_object(dict)
    state["json"] = json_output
    state["quiet"] = quiet
    state["verbose"] = verbose
    state["debug"] = debug
    state["no_color"] = no_color
    state["no_progress"] = no_progress
    root_logger = logging.getLogger()
    previous_root_level = root_logger.level
    previous_handler_levels = [handler.level for handler in root_logger.handlers]

    def _restore_root_logger_levels() -> None:
        root_logger.setLevel(previous_root_level)
        for handler, previous_level in zip(root_logger.handlers, previous_handler_levels, strict=False):
            handler.setLevel(previous_level)

    ctx.call_on_close(_restore_root_logger_levels)
    apply_to_root_logger(resolve_log_level(quiet=quiet, verbose=verbose, debug=debug))


@app.command(name="hello", help="Smoke test command - prints a greeting and exits 0.")
def hello() -> None:
    """Sanity check command preserved for the base smoke tests."""
    typer.echo("Hello from AEAT CLI")


app.command(
    name="doctor",
    help="Report whether this workstation is ready for Kent's filing workflow.",
)(doctor_module.doctor)
app.command(name="bootstrap", help="Provision scratch resources and persist their IDs to env/.env.")(
    bootstrap_module.bootstrap
)
app.add_typer(
    auth_module.app,
    name="auth",
    help="Kent-first auth setup and AEAT authentication provider management.",
)
app.add_typer(
    attachments_module.app,
    name="attachments",
    help="Content-addressed attachment service (#76).",
)
app.add_typer(browser_module.app, name="browser", help="Playwright browser session health probes (#95).")
app.add_typer(casillas_module.app, name="casillas", help="Curated AEAT casilla catalogue helpers.")
app.add_typer(categories_module.app, name="categories", help="AEAT spending-category taxonomy helpers (#77).")
app.add_typer(drive_module.app, name="drive", help="Google Drive helpers.")
app.add_typer(sheets_module.app, name="sheets", help="Google Sheets helpers.")
app.add_typer(docs_module.app, name="docs", help="Google Docs helpers.")
app.add_typer(cloud_module.app, name="cloud", help="GCP product helpers (Functions / Run / Storage).")
app.add_typer(llm_module.app, name="llm", help="LLM prompt, translation, cache, and usage helpers.")
app.add_typer(oauth_module.app, name="oauth-client", help="OAuth 2.0 Desktop client provisioning.")
app.add_typer(manual_module.app, name="manual", help="AEAT Manual práctico corpus helpers (#25).")
app.add_typer(modelos_module.app, name="modelos", help="AEAT modelo inventory + applicability helpers.")
app.add_typer(normatives_module.app, name="normatives", help="Spanish tax normatives corpus helpers (#45).")
app.add_typer(portals_module.app, name="portals", help="AEAT portal catalogue + modelo cross-reference (#7).")
app.add_typer(schema_module.app, name="schema", help="Programmatic AEAT modelo schema extraction (#9).")
app.add_typer(vat_module.app, name="vat", help="Spanish VAT (IVA) taxonomy + rules (#85).")
app.add_typer(sync_module.app, name="sync", help="Self-healing live-to-local sync runner (#11).")
app.add_typer(deadlines_module.app, name="deadlines", help="Filing-deadline computation engine (#38).")
app.add_typer(filing_module.app, name="filing", help="Filing draft engine commands (#39).")
app.add_typer(formulas_module.app, name="formulas", help="Per-modelo calculation formula engine (#173).")
app.add_typer(
    financial_module.app,
    name="financial",
    help="Financial ingest, transaction catalogue, and invoice tooling (#73, #74, #75).",
)
app.add_typer(
    financial_module.invoices_app,
    name="invoices",
    help="Invoice catalogue helpers (#75) — alias for `aeat financial invoices`.",
)
app.add_typer(sede_module.app, name="sede", help="Post-auth AEAT sede discovery (read-only, #239).")
app.add_typer(
    secrets_module.app,
    name="secrets",
    help="Operator-facing secret-store management (#216).",
)
app.add_typer(
    security_module.app,
    name="security",
    help="Operator key-management commands (rotate the master key, etc.).",
)
app.add_typer(
    sanitize_module.app,
    name="sanitize",
    help="PDF PII sanitiser for fixture commits (read-only on AEAT, #239).",
)
app.add_typer(
    submission_module.app,
    name="submission",
    help="Preflight, export, verify, and inspect local AEAT filing records; the tool never writes to AEAT.",
)
app.add_typer(
    rental_module.app,
    name="rental",
    help="Per-finca rental register, Ley 12/2023 tier auto-resolver, art. 23.1.f amortización ledger (#454).",
)
app.add_typer(
    review_module.app,
    name="review",
    help="Review surfaces: queue (#232), history (#237), draft approve/unapprove/show/stale (#230).",
)
app.add_typer(
    workflow_module.app,
    name="workflow",
    help="Drive Kent's produce -> verify -> export filing workflow.",
)
app.add_typer(
    run_module.app,
    name="run",
    help="Run-trace inspection and deterministic read-only replay (#99).",
)
app.add_typer(
    justificante_module.app,
    name="justificante",
    help="AEAT justificante (PDF receipt) parser and live CSV verifier (#44).",
)
app.add_typer(setup_wizard_module.app, name="setup", help="First-run interactive setup wizard (#61).")
app.add_typer(
    audit_module.audit_app,
    name="audit",
    help="Audit helpers (dev-only, #339).",
    hidden=True,
)

decorate_typer_app(app)


__all__ = [
    "SCHEMA_REGISTRY",
    "ExitCode",
    "LogLevel",
    "LogLevelResolutionError",
    "NonTtyRefusedError",
    "OutputSchema",
    "OutputSchemaError",
    "SchemaEnvelope",
    "app",
    "apply_to_root_logger",
    "emit_json_document",
    "exit_with",
    "is_stderr_tty",
    "is_stdin_tty",
    "is_stdout_tty",
    "refuse_if_stdin_non_tty",
    "register_schema",
    "resolve_log_level",
    "should_show_rich_progress",
    "should_use_color",
]
