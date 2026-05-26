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

from collections.abc import Callable

import click
import typer

from ._stdio import configure_stdio_for_utf8

# Force UTF-8 on stdout / stderr before any echo, log, or Rich console
# instantiation. Default Windows terminals expose cp1252; emoji,
# CJK, the U+2192 arrow used by the review queue, and the § sign
# in some VAT citations all crash typer.echo on cp1252. See
# :mod:`._stdio` for the rationale.
configure_stdio_for_utf8()

from ...core.i18n import SUPPORTED_OUTPUT_LANGUAGES, tr
from ._command_suggestions import AeatTyperGroup, LazySubcommand, register_lazy_subcommand
from ._common import _FORMAT_TEXT, _emit
from ._errors import decorate_typer_app, write_stderr
from ._log_levels import apply_to_root_logger, resolve_log_level

# The command tree is assembled lazily: each leaf command module pulls
# the application layer and, transitively, the ~0.6 s registry parse.
# Importing every module just to build the ``aeat`` app object made
# ``aeat --version`` and ``aeat --help`` pay that cost even though they
# never dispatch into a subcommand. Modules are imported by their
# :class:`LazySubcommand` loader only when an operator actually invokes
# something in the owning subtree (see :mod:`._command_suggestions`).
# ``--version`` / ``--help`` / the bare landing surface short-circuit
# in the callbacks below before any subcommand is resolved.

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
    cls=AeatTyperGroup,
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
    profile: str | None = typer.Option(
        None,
        "--profile",
        help=tr("cli.root.profile_help"),
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
        # with the registry summary populated. The diagnostics import
        # is deferred here so it never loads on a non-version surface.
        from ...application.diagnostics import build_cli_version_report, render_cli_version_text

        report = build_cli_version_report(with_registry=detail)
        if detail:
            typer.echo(render_cli_version_text(report))
        else:
            typer.echo(f"{report.package_name} {report.package_version}")
        raise typer.Exit()
    if help_:
        # The operator-surface import is deferred so the help-document
        # builder loads only on a help surface, not on every dispatch.
        from ...application.operator_surface import build_help_document, render_help_text

        document = build_help_document("root")
        _emit(ctx, document, render_help_text(document).splitlines())
        raise typer.Exit()
    # Wire the active-profile output-language resolver into ``core.i18n``
    # before any subcommand renders prose. Importing the side-effect
    # module registers the resolver; without it, render paths that never
    # touch ``aeat.application.user_profile`` (e.g. ``overview status``)
    # silently ignore a profile's ``preferences.output_language``. Kept
    # after the ``--version`` / ``--help`` fast-path exits so those
    # surfaces stay free of the application-layer import.
    if profile is not None:
        _activate_profile_override(ctx, profile)
    from ...application.user_profile import _language_resolver as _language_resolver

    _activate_active_bucket_session(ctx)
    if ctx.invoked_subcommand is None:
        # The landing surface needs the workflow / overview application
        # layer; deferring the import keeps it off the ``--version`` /
        # ``--help`` fast-paths above.
        from ...application.operator_surface import build_root_landing_report
        from ...application.overview import build_overview_status_report
        from ...application.workflow import workflow_state_repository
        from ...application.workflow._models import resolve_active_bucket_id
        from ._root_landing import render_cli_root_landing_lines

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


def _activate_profile_override(ctx: typer.Context, profile: str) -> None:
    """Resolve ``--profile`` to a bucket id and set the active-profile override."""

    from ...application.workflow._profile_bucket_scan import read_profile_bucket, read_profile_bucket_by_id
    from ...core.config import override_settings
    from ._errors import CliRefusedBoundaryError

    requested = profile.strip()
    if not requested:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=profile))
    pointer = read_profile_bucket(requested) or read_profile_bucket_by_id(requested)
    if pointer is None:
        raise CliRefusedBoundaryError(tr("cli.config.profile.unknown_profile", name=requested))
    ctx.with_resource(override_settings(aeat_active_profile=pointer.bucket_id))


def _activate_active_bucket_session(ctx: typer.Context) -> None:
    """Active-gate the CLI session against the bootstrap-exempt registry.

    Three outcomes:

    - Bootstrap-exempt verbs (``profile create``, ``profile import``,
      ``config repair`` family) run without a session — return early.
    - No active profile resolves — return without opening a session.
      Each non-exempt verb carries its own
      ``resolve_active_bucket_id() is None`` guard that refuses with a
      translated message; opening a session here against an absent
      per-bucket database would pre-empt that cleaner per-verb refusal
      and break the bare-invocation landing card.
    - An active profile resolves — open its bucket session (unless one
      is already active) so the verb body can decrypt stored records.

    The per-verb guards remain the primary refusal surface. This root
    callback adds only one fail-closed guard before the verb body: a
    real operator invocation of a guarded profile-bound mutation verb
    may not proceed when settings route the primary SQL store to the
    root fallback database.
    ``_full_invocation_verb_path`` returns ``None`` for in-process test
    runner invocations, so this guard does not misclassify cached
    Typer tests that do not populate the console-script argv shape.
    """

    from ...adapters.persistence.storage import get_master_key_provider, has_active_bucket_session
    from ...application.storage_write_policy import inspect_storage_write_policy
    from ...application.workflow._models import resolve_active_bucket_id
    from ._bootstrap_exempt import is_bootstrap_exempt
    from ._errors import CliRefusedBoundaryError

    verb_path = _full_invocation_verb_path()
    exempt = is_bootstrap_exempt(verb_path)
    write_policy = inspect_storage_write_policy(verb_path, bootstrap_exempt=exempt)
    if not write_policy.allowed:
        raise CliRefusedBoundaryError(write_policy.render_refusal_message())
    if resolve_active_bucket_id() is None:
        # No active profile: each non-exempt verb refuses for itself
        # with a translated message (see the per-verb
        # ``resolve_active_bucket_id() is None`` guards). Returning here
        # avoids opening a session against an absent per-bucket
        # database and keeps the bare-invocation landing card path
        # (handled by the caller) intact. Bootstrap-exempt verbs also
        # return — they run cleanly with no profile by design.
        return
    if has_active_bucket_session():
        return
    if exempt:
        return
    ctx.with_resource(get_master_key_provider())
    # The active profile's encrypted record is only decryptable once the
    # bucket session above is open. ``output_language()`` is cached, and
    # its cache key (env vars + `.env` mtime) does not vary when a
    # session opens — so any `tr()` fired during module import or the
    # root callback cached the settings-default language before the
    # profile preference was readable. Drop the cache here so the verb
    # body re-resolves through the now-readable profile preference.
    from ...core.i18n._render import clear_output_language_cache

    clear_output_language_cache()


def _full_invocation_verb_path() -> str | None:
    """Return the operator-typed verb path stripped of top-level flags.

    Reads ``sys.argv`` and removes top-level option flags
    (``--version``, ``--help``, ``--language``, ``--format``, etc.)
    so the returned string is the canonical subcommand chain the
    operator typed: ``"config profile create"`` for
    ``aeat --quiet config profile create alice``. Returns ``None``
    for the bare invocation and for non-entrypoint processes such as
    in-process test runners.

    Matched against :data:`BOOTSTRAP_EXEMPT_VERB_PATHS` via prefix
    so ``"config profile create alice"`` matches the exempt entry
    ``"config profile create"``.
    """

    import sys
    from pathlib import Path

    executable = Path(sys.argv[0]).name.lower()
    if executable not in {"aeat", "aeat.exe", "__main__.py"}:
        return None

    tokens = sys.argv[1:]
    if any(token in {"--help", "-h", "--version", "-V"} for token in tokens):
        return None
    verb_tokens: list[str] = []
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token.startswith("-"):
            if token in ("--language", "--lang", "--format", "--profile") and "=" not in token:
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
    return tr("cli.root.startup_import_error", dependency=dependency) + "\n"


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
    cls=AeatTyperGroup,
)


@app_app.callback()
def _app_root(
    ctx: typer.Context,
    help_: bool = typer.Option(False, "--help", "-h", help=tr("cli.root.app_help_help"), is_eager=True),
) -> None:
    """Render app-level workflow help when requested."""

    if help_ or ctx.invoked_subcommand is None:
        from ...application.operator_surface import build_help_document, render_help_text

        document = build_help_document("app")
        _emit(ctx, document, render_help_text(document).splitlines())
        raise typer.Exit()


def _lazy_loader(module_name: str, group_label: str) -> Callable[[], typer.Typer]:
    """Build a deferred factory importing ``module_name``'s ``app`` Typer.

    A :exc:`ModuleNotFoundError` from a missing optional dependency is
    converted into a failure-surface Typer that refuses cleanly and
    points the operator at ``aeat config repair`` — the same behaviour
    the eager startup path produced, now deferred to the first time the
    subtree is actually invoked.
    """

    def _factory() -> typer.Typer:
        from importlib import import_module

        try:
            module = import_module(module_name, __name__)
        except ModuleNotFoundError as error:
            return _import_failure_surface(group_label, error)
        return module.app

    return _factory


def _lazy(group_name: str, name: str, module_name: str) -> None:
    """Register ``module_name`` as a lazily-loaded subcommand of ``group_name``."""

    register_lazy_subcommand(
        group_name,
        LazySubcommand(name, _lazy_loader(module_name, name), decorate=decorate_typer_app),
    )


# ---------------------------------------------------------------------
# Wiring — every heavy subcommand module is registered lazily so the
# `aeat` app object can be constructed without importing the command
# tree (and therefore without the registry parse).
# ---------------------------------------------------------------------


_lazy("app", "overview", "._overview")
_lazy("app", "ledger", "._ledger")
_lazy("app", "live", "._app_live")
_lazy("app", "modelo", "._modelo")
_lazy("app", "registry", ".registry")
_lazy("app", "review", "._review")

_lazy("aeat", "config", "._config")
app.add_typer(app_app, name="app")
decorate_typer_app(app)


def main() -> None:
    """Console-script entry point. Pins ``prog_name`` so Typer's usage
    lines say ``aeat`` even when the launcher is ``aeat.EXE`` on Windows."""

    app(prog_name="aeat")


__all__ = ["app", "main"]
