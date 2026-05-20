"""User-facing ``aeat`` CLI.

The command tree exposes two top-level namespaces:

- ``aeat config`` — local configuration, on-ramp wizard, diagnostics.
- ``aeat app`` — operational tax work: overview, ledger, modelo,
  registry, and review.

Every command in this package is a thin transport over the backend API.
The handler bodies parse argv, call into
``aeat.application`` / ``aeat.domain``, and render the typed result.
No business logic lives in the CLI layer: validation, mutation,
schema-decision, and persistence all live behind the imported
application functions and pydantic records.
"""

from __future__ import annotations

import types

import click
import typer

from ._stdio import configure_stdio_for_utf8

# Force UTF-8 on stdout / stderr before any echo, log, or Rich console
# instantiation. Default Windows terminals expose cp1252; emoji,
# CJK, the U+2192 arrow used by the review queue, and the § sign
# in some VAT citations all crash typer.echo on cp1252. See
# :mod:`._stdio` for the rationale.
configure_stdio_for_utf8()

from ...application.diagnostics import build_cli_version_report, render_cli_version_text
from ...application.operator_surface import (
    build_help_document,
    build_root_landing_report,
    render_help_text,
)
from ...application.overview import build_overview_status_report
from ...application.workflow import workflow_state_repository
from ...core.i18n import SUPPORTED_OUTPUT_LANGUAGES, tr
from . import _config
from ._common import _FORMAT_TEXT, _emit
from ._errors import decorate_typer_app, write_stderr
from ._log_levels import apply_to_root_logger, resolve_log_level
from ._root_landing import render_cli_root_landing_lines

_overview_module: types.ModuleType | None = None
_ledger_module: types.ModuleType | None = None
_live_module: types.ModuleType | None = None
_modelo_module: types.ModuleType | None = None
_registry_module: types.ModuleType | None = None
_review_module: types.ModuleType | None = None

try:
    from . import _app_live as _live_module
    from . import _ledger as _ledger_module
    from . import _modelo as _modelo_module
    from . import _overview as _overview_module
    from . import _review as _review_module
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
    add_help_option=False,
    add_completion=True,
)


@app.callback()
def _root(
    ctx: typer.Context,
    language: str | None = typer.Option(
        None,
        "--language",
        "--lang",
        click_type=click.Choice(SUPPORTED_OUTPUT_LANGUAGES),
        help=tr("cli.root.language_help"),
        is_eager=True,
    ),
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help=tr("cli.root.version_help"),
        is_eager=True,
    ),
    detail: bool = typer.Option(
        False,
        "--detail",
        help=tr("cli.root.detail_help"),
        is_eager=True,
    ),
    help_: bool = typer.Option(
        False,
        "--help",
        "-h",
        help=tr("cli.root.help_help"),
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
    if language is not None:
        from ...core.config import override_settings

        ctx.with_resource(override_settings(aeat_output_language=language))
    apply_to_root_logger(resolve_log_level(quiet=quiet, verbose=verbose, debug=debug))
    state = ctx.ensure_object(dict)
    state["format"] = format_.strip().lower() or _FORMAT_TEXT
    if version:
        # Fast-path: bare `aeat --version` skips the registry load
        # (disaster ADR Ruling 4 — registry validation must not run
        # on the version surface). The `--detail` variant re-invokes
        # with the registry summary populated.
        report = build_cli_version_report(with_registry=detail)
        if detail:
            typer.echo(render_cli_version_text(report))
        else:
            typer.echo(f"{report.package_name} {report.package_version}")
        raise typer.Exit()
    if help_:
        document = build_help_document("root")
        _emit(ctx, document, render_help_text(document).splitlines())
        raise typer.Exit()
    _activate_active_bucket_session(ctx)
    if ctx.invoked_subcommand is None:
        if _app_import_error is not None:
            _emit_startup_import_error(_app_import_error)
        from ...application.workflow._models import resolve_active_bucket_id

        active = resolve_active_bucket_id()
        landing = build_root_landing_report(active)
        if active is None:
            # Bare invocation with no active profile: render the
            # landing card (which names `profile create` as the next
            # action) and exit. Reading the workflow state here would
            # require an active session the operator has not yet
            # established — the F1 / F2 deadlock the disaster ADR
            # closes.
            _emit(ctx, landing, render_cli_root_landing_lines(landing))
            raise typer.Exit()
        workflow_state = workflow_state_repository().load()
        overview_report = build_overview_status_report(state=workflow_state)
        _emit(ctx, overview_report, render_cli_root_landing_lines(landing))
        raise typer.Exit()


def _activate_active_bucket_session(ctx: typer.Context) -> None:
    """Active-gate the CLI session against the bootstrap-exempt registry.

    Bootstrap-exempt verbs (``profile create``, ``profile import``,
    ``config repair`` family) run without a session. Every other
    verb either opens the pointed-at bucket's session (when
    ``resolve_active_bucket_id`` returns a name) or refuses with a
    translated :class:`CliRefusedBoundaryError` that names
    ``profile create`` / ``profile switch`` as next actions.

    The refusal path replaces the silent-skip pattern that previously
    let every non-exempt verb raise ``NoActiveBucketSessionError``
    from inside its own body — the F1 / F2 cold-start deadlock the
    2026-05-19 operator testimonies catalogued.
    """

    from ...adapters.persistence.storage import get_master_key_provider, has_active_bucket_session
    from ...application.workflow._models import resolve_active_bucket_id
    from ._bootstrap_exempt import is_bootstrap_exempt

    if is_bootstrap_exempt(_full_invocation_verb_path()):
        return
    if resolve_active_bucket_id() is None:
        # No active profile: each non-exempt verb refuses for itself
        # with a translated message (see the per-verb
        # ``resolve_active_bucket_id() is None`` guards). Returning here
        # avoids opening a session against an absent per-bucket
        # database and keeps the bare-invocation landing card path
        # (handled by the caller) intact.
        return
    if has_active_bucket_session():
        return
    ctx.with_resource(get_master_key_provider())


def _full_invocation_verb_path() -> str | None:
    """Return the operator-typed verb path stripped of top-level flags.

    Reads ``sys.argv`` and removes top-level option flags
    (``--version``, ``--help``, ``--language``, ``--format``, etc.)
    so the returned string is the canonical subcommand chain the
    operator typed: ``"config profile create"`` for
    ``aeat --quiet config profile create alice``. Returns ``None``
    for the bare invocation.

    Matched against :data:`BOOTSTRAP_EXEMPT_VERB_PATHS` via prefix
    so ``"config profile create alice"`` matches the exempt entry
    ``"config profile create"``.
    """

    import sys

    tokens = sys.argv[1:]
    verb_tokens: list[str] = []
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token.startswith("-"):
            if token in ("--language", "--lang", "--format") and "=" not in token:
                skip_next = True
            continue
        verb_tokens.append(token)
    if not verb_tokens:
        return None
    return " ".join(verb_tokens)


def _import_failure_surface(name: str, error: ModuleNotFoundError) -> typer.Typer:
    failed_app = typer.Typer(
        name=name,
        help=tr("cli.root.unavailable_app_help"),
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
    return f"Cannot start AEAT command surface: missing dependency {dependency!r}.\nRun: aeat config repair\n"


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
    no_args_is_help=False,
    invoke_without_command=True,
    add_help_option=False,
)


@app_app.callback()
def _app_root(
    ctx: typer.Context,
    help_: bool = typer.Option(False, "--help", "-h", help=tr("cli.root.app_help_help"), is_eager=True),
) -> None:
    """Render app-level workflow help when requested."""

    if help_ or ctx.invoked_subcommand is None:
        document = build_help_document("app")
        _emit(ctx, document, render_help_text(document).splitlines())
        raise typer.Exit()


if _app_import_error is None:
    assert _overview_module is not None
    assert _ledger_module is not None
    assert _live_module is not None
    assert _modelo_module is not None
    assert _registry_module is not None
    assert _review_module is not None
    app_app.add_typer(_overview_module.app, name="overview")
    app_app.add_typer(_ledger_module.app, name="ledger")
    app_app.add_typer(_live_module.app, name="live")
    app_app.add_typer(_modelo_module.app, name="modelo")
    app_app.add_typer(_registry_module.app, name="registry")
    app_app.add_typer(_review_module.app, name="review")


# ---------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------


app.add_typer(_config.app, name="config")
if _app_import_error is None:
    app.add_typer(app_app, name="app")
else:
    app.add_typer(_import_failure_surface("app", _app_import_error), name="app")
decorate_typer_app(app)


def main() -> None:
    """Console-script entry point. Pins ``prog_name`` so Typer's usage
    lines say ``aeat`` even when the launcher is ``aeat.EXE`` on Windows."""

    app(prog_name="aeat")


__all__ = ["app", "main"]
