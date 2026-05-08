"""User-facing ``aeat`` CLI.

The command tree exposes two top-level namespaces:

- ``aeat setup`` — local prerequisites: profile, authentication, status.
- ``aeat app`` — operational tax work: overview, ledger, invoice,
  declaration.

Every command in this package is a thin transport over the backend API.
The handler bodies parse argv, call into
``aeat.application`` / ``aeat.domain``, and render the typed result.
No business logic lives in the CLI layer: validation, mutation,
schema-decision, and persistence all live behind the imported
application functions and pydantic records.
"""

from __future__ import annotations

import typer

from ...application.diagnostics import build_cli_version_report, render_cli_version_text
from . import _declaration, _invoice, _ledger, _overview, _setup, registry
from ._common import _FORMAT_TEXT
from ._errors import decorate_typer_app
from ._i18n import tr
from ._log_levels import apply_to_root_logger, resolve_log_level

# ---------------------------------------------------------------------
# Root app + callback
# ---------------------------------------------------------------------


app = typer.Typer(
    name="aeat",
    help=tr("cli.root.app_help"),
    no_args_is_help=False,
    invoke_without_command=True,
    add_completion=False,
)


@app.callback()
def _root(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help=tr("cli.root.version_help"),
        is_eager=True,
    ),
    format_: str = typer.Option(
        _FORMAT_TEXT,
        "--format",
        help=tr("cli.root.format_help"),
    ),
    quiet: bool = typer.Option(False, "--quiet", help=tr("cli.root.quiet_help")),
    verbose: bool = typer.Option(False, "--verbose", help=tr("cli.root.verbose_help")),
    debug: bool = typer.Option(False, "--debug", help=tr("cli.root.debug_help")),
) -> None:
    """Capture root-level CLI flags into the Typer context."""
    apply_to_root_logger(resolve_log_level(quiet=quiet, verbose=verbose, debug=debug))
    if version:
        typer.echo(render_cli_version_text(build_cli_version_report()))
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()
    state = ctx.ensure_object(dict)
    state["format"] = format_.strip().lower() or _FORMAT_TEXT


@app.command("version", help=tr("cli.root.version_command_help"))
def version_cmd(ctx: typer.Context) -> None:
    """Show package and registry version information."""

    report = build_cli_version_report()
    state = ctx.ensure_object(dict)
    if state.get("format") == "json":
        typer.echo(report.model_dump_json())
        return
    typer.echo(render_cli_version_text(report))


# ---------------------------------------------------------------------
# `aeat app` — workflow aggregator
# ---------------------------------------------------------------------


app_app = typer.Typer(
    name="app",
    help=tr("cli.root.app_app_help"),
    no_args_is_help=True,
)

app_app.add_typer(_overview.app, name="overview")
app_app.add_typer(_ledger.app, name="ledger")
app_app.add_typer(_invoice.app, name="invoice")
app_app.add_typer(_declaration.app, name="declaration")
app_app.add_typer(registry.app, name="registry")


# ---------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------


app.add_typer(_setup.app, name="setup")
app.add_typer(app_app, name="app")
decorate_typer_app(app)


__all__ = ["app"]
