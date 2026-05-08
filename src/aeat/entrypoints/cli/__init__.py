"""User-facing ``aeat`` CLI.

The command tree exposes two top-level namespaces:

- ``aeat setup`` — local prerequisites: profile, authentication, status.
- ``aeat config`` — local configuration and diagnostics.
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

from typing import Any

import typer

from ...application.diagnostics import build_cli_version_report, render_cli_version_text
from . import _archive, _config
from ._common import _FORMAT_TEXT
from ._errors import decorate_typer_app, write_stderr
from ._i18n import tr
from ._log_levels import apply_to_root_logger, resolve_log_level

_setup_module: Any | None = None
_overview_module: Any | None = None
_ledger_module: Any | None = None
_invoice_module: Any | None = None
_declaration_module: Any | None = None
_modelo_module: Any | None = None
_registry_module: Any | None = None

try:
    from . import _setup as _setup_module
except ModuleNotFoundError as exc:
    _setup_import_error: ModuleNotFoundError | None = exc
else:
    _setup_import_error = None

try:
    from . import _declaration as _declaration_module
    from . import _invoice as _invoice_module
    from . import _ledger as _ledger_module
    from . import _modelo as _modelo_module
    from . import _overview as _overview_module
    from . import registry as _registry_module
except ModuleNotFoundError as exc:
    _app_import_error: ModuleNotFoundError | None = exc
else:
    _app_import_error = None

# ---------------------------------------------------------------------
# Root app + callback
# ---------------------------------------------------------------------


app = typer.Typer(
    name="aeat",
    help=tr("cli.root.app_help"),
    no_args_is_help=False,
    invoke_without_command=True,
    add_completion=True,
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
        if _setup_import_error is not None:
            _emit_startup_import_error(_setup_import_error)
        if _app_import_error is not None:
            _emit_startup_import_error(_app_import_error)
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


def _import_failure_surface(name: str, error: ModuleNotFoundError) -> typer.Typer:
    failed_app = typer.Typer(
        name=name,
        help=f"Unavailable: missing dependency {_missing_dependency_name(error)!r}",
        no_args_is_help=False,
        invoke_without_command=True,
    )

    @failed_app.callback()
    def _failed() -> None:
        _emit_startup_import_error(error)

    return failed_app


def _emit_startup_import_error(error: ModuleNotFoundError) -> None:
    write_stderr(_startup_import_error_text(error))
    raise typer.Exit(code=1)


def _startup_import_error_text(error: ModuleNotFoundError) -> str:
    dependency = _missing_dependency_name(error)
    return f"Cannot start AEAT command surface: missing dependency {dependency!r}.\nRun: aeat config doctor\n"


def _missing_dependency_name(error: ModuleNotFoundError) -> str:
    if error.name:
        return error.name
    text = str(error).strip()
    if text:
        return text
    return type(error).__name__


# ---------------------------------------------------------------------
# `aeat app` — workflow aggregator
# ---------------------------------------------------------------------


app_app = typer.Typer(
    name="app",
    help=tr("cli.root.app_app_help"),
    no_args_is_help=True,
)

if _app_import_error is None:
    assert _overview_module is not None
    assert _ledger_module is not None
    assert _invoice_module is not None
    assert _declaration_module is not None
    assert _modelo_module is not None
    assert _registry_module is not None
    app_app.add_typer(_overview_module.app, name="overview")
    app_app.add_typer(_ledger_module.app, name="ledger")
    app_app.add_typer(_invoice_module.app, name="invoice")
    app_app.add_typer(_declaration_module.app, name="declaration")
    app_app.add_typer(_modelo_module.app, name="modelo")
    app_app.add_typer(_registry_module.app, name="registry")


# ---------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------


if _setup_import_error is None:
    assert _setup_module is not None
    app.add_typer(_setup_module.app, name="setup")
else:
    app.add_typer(_import_failure_surface("setup", _setup_import_error), name="setup")
app.add_typer(_config.app, name="config")
app.add_typer(_archive.app, name="archive")
if _app_import_error is None:
    app.add_typer(app_app, name="app")
else:
    app.add_typer(_import_failure_surface("app", _app_import_error), name="app")
decorate_typer_app(app)


__all__ = ["app"]
