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
from typing import TYPE_CHECKING, cast

import typer

if TYPE_CHECKING:
    import click
from typer._types import TyperChoice as _TyperChoice

from ._stdio import configure_stdio_for_utf8 as _configure_stdio_for_utf8

# Force UTF-8 on stdout / stderr before any echo, log, or Rich console
# instantiation. Default Windows terminals expose cp1252; emoji,
# CJK, the U+2192 arrow used by the review queue, and the § sign
# in some IVA citations all crash typer.echo on cp1252. See
# :mod:`._stdio` for the rationale.
_configure_stdio_for_utf8()

from ...core.i18n import SUPPORTED_OUTPUT_LANGUAGES as _SUPPORTED_OUTPUT_LANGUAGES
from ...core.i18n import tr
from ...core.redaction import redact_for_cli_output as _redact_for_cli_output
from ._command_suggestions import (
    AeatTyperGroup as _AeatTyperGroup,
)
from ._command_suggestions import (
    LazySubcommand as _LazySubcommand,
)
from ._command_suggestions import (
    register_lazy_subcommand as _register_lazy_subcommand,
)
from ._common import _FORMAT_TEXT, _emit_envelope
from ._errors import decorate_typer_app as _decorate_typer_app
from ._errors import write_stderr as _write_stderr
from ._language_argv import apply_language_argv_to_environment as _apply_language_argv_to_environment
from ._log_levels import apply_to_root_logger as _apply_to_root_logger
from ._log_levels import resolve_log_level as _resolve_log_level
from ._root_payloads import AppRootResult, RootStatusResult

# The command tree is assembled lazily: each leaf command module pulls
# the application layer and, transitively, the ~0.6 s registry parse.
# Importing every module just to build the ``aeat`` app object made
# ``aeat --version`` and ``aeat --help`` pay that cost even though they
# never dispatch into a subcommand. Modules are imported by their
# :class:`_LazySubcommand` loader only when an operator actually invokes
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
    cls=_AeatTyperGroup,
)


@app.callback()
def _root(
    ctx: typer.Context,
    language: str | None = typer.Option(
        None,
        "--language",
        "--lang",
        click_type=_TyperChoice(_SUPPORTED_OUTPUT_LANGUAGES),
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
    _apply_to_root_logger(_resolve_log_level(quiet=quiet, verbose=verbose, debug=debug))
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
            # The short `aeat --version` line is machine-format semver
            # (e.g. "aeat 1.2.3") consumed by CI tooling and package
            # managers. AEAT policy treats semver output as machine-format,
            # not operator text, so tr() wrapping is intentionally omitted.
            typer.echo(f"{report.package_name} {report.package_version}")
        raise typer.Exit()
    if help_:
        # The operator-surface import is deferred so the help-document
        # builder loads only on a help surface, not on every dispatch.
        from ...application.operator_surface import build_help_document, render_help_text

        document = build_help_document("root")
        typed_help = RootStatusResult.model_validate(document.model_dump(mode="json"))
        _emit_envelope(ctx, command="root.status", result=typed_help, lines=render_help_text(document).splitlines())
        raise typer.Exit()
    # Defer profile override and bucket-session activation to after the
    # version/help fast-paths (already exited above). Bare invocation
    # (ctx.invoked_subcommand is None) defers the full application-layer
    # imports (user_profile, wizard, workflow) into its own branch so
    # state-free dispatch avoids the registry load.
    if profile is not None:
        _activate_profile_override(ctx, profile)
    else:
        # No explicit --profile: the active profile comes from the
        # AEAT_ACTIVE_PROFILE env override / pointer. Normalize a display-name
        # value to its UUID so the core storage-route resolver (UUID-only)
        # resolves it — an operator only knows the label, never the UUID.
        # Bootstrap-exempt recovery verbs must not read bucket manifests here:
        # they are the surfaces operators use when those manifests are torn.
        from ._bootstrap_exempt import is_bootstrap_exempt

        verb_path = _full_invocation_verb_path() or _verb_path_from_context(ctx)
        if not is_bootstrap_exempt(verb_path):
            _normalize_active_profile_label_to_uuid(ctx)
    if ctx.invoked_subcommand is None:
        # The landing surface needs the application operator_surface
        # layer; deferring the import keeps it off the ``--version`` /
        # ``--help`` fast-paths above. Bare invocation without an active
        # profile does NOT import workflow or overview (which pull the
        # registry) — it only renders the profile-creation prompt.
        # Use the lightweight core resolver to avoid importing workflow.
        from ...adapters.persistence.storage import has_active_bucket_session
        from ...application.operator_surface import build_root_landing_report
        from ...core import resolve_active_bucket_id
        from ._root_landing import render_cli_root_landing_lines

        active = resolve_active_bucket_id()
        landing = build_root_landing_report(active)
        if active is None or not has_active_bucket_session():
            # Bare invocation with no active profile OR no open
            # session: render the landing card and exit. Per
            # `2026-06-03-bare-invocation-bucket-session-gate-adr`
            # bare invocation is a metadata-emitting introspection
            # surface analogous to --help/--version and MUST NOT
            # require an active bucket session. Reading
            # workflow_state would force session-open against the
            # encrypted bucket, breaking the cold-start /
            # session-closed-but-profile-exists path.
            typed_landing = RootStatusResult.model_validate(landing.model_dump(mode="json"))
            _emit_envelope(
                ctx,
                command="root.status",
                result=typed_landing,
                lines=render_cli_root_landing_lines(landing),
            )
            raise typer.Exit()
        # An active profile resolves AND a session is already open:
        # render the full overview. These imports pull the registry,
        # but are deferred until a verb that actually needs them is
        # invoked.
        from ...application.overview import build_overview_status_report
        from ...application.workflow import workflow_state_repository

        workflow_state = workflow_state_repository().load()
        overview_report = build_overview_status_report(state=workflow_state)
        typed_overview = RootStatusResult.model_validate(overview_report.model_dump(mode="json"))
        _emit_envelope(ctx, command="root.status", result=typed_overview, lines=render_cli_root_landing_lines(landing))
        raise typer.Exit()
    # A subcommand is being invoked. Activate the bucket session here
    # so verbs that need it have access to the active profile's
    # encrypted records. This is deferred after the bare-invocation
    # path to keep it out of the state-free surfaces (--version,
    # --help, bare invocation). Help and usage-error renderings are
    # introspection surfaces too: they must never require the master
    # key, or a newcomer without AEAT_SECRET_PASSPHRASE cannot browse
    # the command tree and an unknown-command typo is masked by a
    # master-key refusal instead of the usage error.
    if _is_introspection_only_invocation(ctx):
        return
    _activate_active_bucket_session(ctx)


def _activate_profile_override(ctx: typer.Context, profile: str) -> None:
    """Resolve ``--profile`` to a bucket id and set the active-profile override.

    Resolves through the single application-layer name-or-UUID resolver so a
    ``--profile`` value may be either the operator display label or the UUID
    bucket id, then pins the override to the resolved UUID.
    """
    from ...application.workflow import ProfileLabelAmbiguousError, resolve_profile_bucket
    from ...core.config import override_settings
    from ._errors import CliRefusedBoundaryError

    requested = profile.strip()
    if not requested:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": profile},
        )
    # The label fallback raises ProfileLabelAmbiguousError (a WorkflowError, NOT
    # a ValueError) when two live profiles share the name; refuse clearly rather
    # than arbitrarily picking a bucket.
    try:
        pointer = resolve_profile_bucket(requested)
    except ProfileLabelAmbiguousError as exc:
        # The label is AMBIGUOUS, not unknown: more than one live profile
        # carries it. Render the dedicated ambiguity refusal (which carries no
        # placeholder) rather than the generic unknown-profile message, matching
        # the _config-site precedent in commit c3509a5ee.
        raise CliRefusedBoundaryError(
            translated_message="errors.refused.refused_profile_label_ambiguous",
        ) from exc
    if pointer is None:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.profile.unknown_profile",
            context={"name": requested},
        )
    ctx.with_resource(override_settings(aeat_active_profile=pointer.bucket_id))


def _normalize_active_profile_label_to_uuid(ctx: typer.Context) -> None:
    """Normalize a display-name ``AEAT_ACTIVE_PROFILE`` to its UUID bucket id.

    An operator addresses a profile by the label they chose at ``profile
    create``; the immutable UUID bucket id is never surfaced to them. When no
    ``--profile`` flag is given, the active profile is resolved from the
    ``AEAT_ACTIVE_PROFILE`` env override (the highest-precedence rung): if that
    value is a display LABEL rather than a UUID bucket directory, the core
    storage-route resolver — which keys directly on ``buckets/<value>`` — would
    hard-miss with a "no registered bucket manifest" refusal on every
    profile-bound command. Resolve the label to its UUID through the single
    application-layer resolver and pin the override to the UUID, so the core
    route resolver (which stays UUID-only) receives the identifier it expects.

    No-ops when no active profile resolves, when the value already resolves as a
    UUID bucket directly (the fast path — zero change for UUID-valued input), or
    when the label does not match any live profile (the per-command active-profile
    guard surfaces that). An ambiguous label (more than one live match) raises a
    clear refusal rather than an arbitrary pick.
    """
    from ...application.workflow import (
        ProfileLabelAmbiguousError,
        read_profile_bucket_by_id,
        resolve_profile_bucket,
    )
    from ...core import resolve_active_bucket_id
    from ...core.config import override_settings
    from ...core.errors import AeatError
    from ._errors import CliRefusedBoundaryError

    active = resolve_active_bucket_id()
    if active is None:
        return
    try:
        active_bucket = read_profile_bucket_by_id(active)
    except AeatError:
        return
    if active_bucket is not None:
        # Already a UUID bucket directory — the canonical fast path. Leave the
        # active-profile value byte-identical so the UUID path is unchanged.
        return
    try:
        pointer = resolve_profile_bucket(active)
    except ProfileLabelAmbiguousError as exc:
        # Two live profiles share the label (ProfileLabelAmbiguousError is a
        # WorkflowError, NOT a ValueError); refuse clearly rather than picking
        # an arbitrary bucket — a wrong silent pick on a tax profile is a
        # data-integrity hazard. The label is AMBIGUOUS, not unknown: render the
        # dedicated ambiguity refusal (no placeholder) rather than the generic
        # unknown-profile message, matching the _config-site precedent in
        # commit c3509a5ee.
        raise CliRefusedBoundaryError(
            translated_message="errors.refused.refused_profile_label_ambiguous",
        ) from exc
    except AeatError:
        return
    if pointer is None:
        # Not a live label either; leave resolution to the per-command active
        # profile guard, which emits the canonical no-active-profile refusal.
        return
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
    runner invocations (``sys.argv[0]`` is not the ``aeat`` console
    script). In that case we fall back to
    :func:`_verb_path_from_context`, which reconstructs the verb chain
    from the typer/click context so the bootstrap-exemption gate sees
    the same verb path it would on a real ``aeat`` invocation — without
    this fallback an in-process invocation would be misclassified as
    bare and the session would never open.
    """
    from ...adapters.persistence.storage import get_master_key_provider, has_active_bucket_session
    from ...application.storage_write_policy import inspect_storage_write_policy
    from ...core import resolve_active_bucket_id
    from ._bootstrap_exempt import is_bootstrap_exempt
    from ._command_suggestions import INVOCATION_REMAINDER_META_KEY
    from ._errors import CliRefusedBoundaryError

    verb_path = _full_invocation_verb_path() or _verb_path_from_context(ctx)
    exempt = is_bootstrap_exempt(verb_path)
    argv_tokens = tuple(str(token) for token in ctx.meta.get(INVOCATION_REMAINDER_META_KEY, ()))
    write_policy = inspect_storage_write_policy(verb_path, bootstrap_exempt=exempt, argv_tokens=argv_tokens)
    if not write_policy.allowed:
        raise CliRefusedBoundaryError(write_policy.render_refusal_message())
    active_bucket_id = resolve_active_bucket_id()
    if active_bucket_id is None:
        # No active profile: each non-exempt verb refuses for itself
        # with a translated message (see the per-verb
        # ``resolve_active_bucket_id() is None`` guards). Returning here
        # avoids opening a session against an absent per-bucket
        # database and keeps the bare-invocation landing card path
        # (handled by the caller) intact. Bootstrap-exempt verbs also
        # return — they run cleanly with no profile by design.
        return
    if _is_unregistered_profile_status_probe(verb_path, active_bucket_id):
        return
    _register_wizard_catalogue_for_profile_keys()
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


def _is_unregistered_profile_status_probe(verb_path: str | None, active_bucket_id: str) -> bool:
    """Let ``config profile status`` diagnose a dangling active pointer."""
    if verb_path != "config profile status":
        return False
    from ...application.workflow import read_profile_bucket_by_id

    return read_profile_bucket_by_id(active_bucket_id) is None


def _register_wizard_catalogue_for_profile_keys() -> None:
    """Import wizard registration side effects before profile-key reads."""
    from ...application.wizard import _catalogue as _wizard_catalogue
    from ...application.wizard import _persistence as _wizard_persistence

    _ = (_wizard_catalogue, _wizard_persistence)


def _is_introspection_only_invocation(ctx: typer.Context) -> bool:
    """Return whether the invocation can only render help or a usage error.

    Two introspection shapes never execute a verb body and therefore must
    not open the encrypted bucket session (which demands the master key and,
    without ``AEAT_SECRET_PASSPHRASE`` on a non-interactive stdin, refuses):

    - A help request: a ``--help`` / ``-h`` token anywhere in the unparsed
      remainder. Click's eager help callback (or the curated subgroup help
      in the group callbacks) aborts before any verb body runs.
    - An unresolvable command chain: the leading non-option tokens do not
      name a registered command, so click can only emit the usage error.
      Opening the session first would mask that exit-2 usage error with a
      master-key refusal, hiding the typo from the operator.

    A literal ``--help`` passed as an option VALUE (``--note --help``) is
    indistinguishable from a help request at this stage; the skip is
    fail-closed — the verb body then refuses on the missing session rather
    than executing, and the canonical spelling ``--note=--help`` is
    unaffected.

    Click empties ``ctx.args`` / the protected list before the group
    callback runs, so the token stream is read from the ``ctx.meta``
    capture staged by :class:`AeatTyperGroup.invoke` (which works for both
    real-process and in-process invocations).
    """
    from ._command_suggestions import INVOCATION_REMAINDER_META_KEY

    remainder = list(ctx.meta.get(INVOCATION_REMAINDER_META_KEY, ()))
    if any(token in ("--help", "-h") for token in remainder):
        return True
    # Walk the LEADING non-option tokens through the real command tree;
    # the chain stops at the first option token (everything after it can
    # be an option value, not a subcommand name). ``list_commands`` is
    # the structural group marker (the vendored TyperGroup is not a
    # guaranteed upstream ``click.Group`` subclass).
    tokens: list[str] = []
    for token in remainder:
        if token.startswith("-"):
            break
        tokens.append(token)
    if not tokens:
        return False
    command: object = ctx.command
    for token in tokens:
        if not hasattr(command, "list_commands"):
            return False
        # CAST-RATIONALE-CLICK-GROUP: ``list_commands`` is the structural group
        # marker used above before calling the click group API.
        group = cast("click.Group", command)
        # CAST-RATIONALE-CLICK-CONTEXT: ``typer.Context`` is the vendored-fork
        # context; ty treats it as distinct from upstream ``click.core.Context``
        # that ``get_command`` annotates, though it is structurally identical.
        subcommand = group.get_command(cast("click.Context", ctx), token)
        if subcommand is None:
            return True
        command = subcommand
    return False


def _verb_path_from_context(ctx: typer.Context) -> str | None:
    """Recover the verb path from the typer/click context.

    Fallback for in-process invocations (e.g. ``CliRunner`` in tests)
    where ``sys.argv[0]`` is not the ``aeat`` entry-point and the
    argv-based :func:`_full_invocation_verb_path` returns ``None``.
    The bootstrap-exemption gate treats a ``None`` verb path as
    "bare invocation" (per the bare-invocation ADR), but the caller
    only reaches this helper when ``ctx.invoked_subcommand`` is set —
    i.e. a real subcommand IS being dispatched and the session must
    open. Reconstructs the verb chain from the root invoked
    subcommand plus the unparsed remainder so prefix matching against
    :data:`BOOTSTRAP_EXEMPT_VERB_PATHS` continues to work.
    """
    from ._command_suggestions import INVOCATION_REMAINDER_META_KEY

    captured = list(ctx.meta.get(INVOCATION_REMAINDER_META_KEY, ()))
    if captured:
        tokens: list[str] = []
        for token in captured:
            if token.startswith("-"):
                break
            tokens.append(token)
        return " ".join(tokens) if tokens else None

    invoked = ctx.invoked_subcommand
    if invoked is None:
        return None
    tokens = [invoked]
    # Click 9 exposes the unparsed remainder on ``ctx.args``. Click 8 still
    # stages the same data on the internal protected list during root-callback
    # execution; reading the deprecated public ``protected_args`` property emits
    # a warning, so use the internal storage only as a compatibility fallback.
    remainder = list(ctx.args)
    if not remainder:
        remainder = list(getattr(ctx, "_protected_args", ()))
    for token in remainder:
        if token.startswith("-"):
            # Stop at the first option flag; the verb chain is the
            # leading subcommand chain only.
            break
        tokens.append(token)
    return " ".join(tokens)


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
    _write_stderr(_startup_import_error_text(error))
    raise typer.Exit(code=1)


def _startup_import_error_text(error: ModuleNotFoundError) -> str:
    dependency = _redact_for_cli_output(_missing_dependency_name(error))
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
    cls=_AeatTyperGroup,
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
        typed_app = AppRootResult.model_validate(document.model_dump(mode="json"))
        _emit_envelope(ctx, command="root.app", result=typed_app, lines=render_help_text(document).splitlines())
        raise typer.Exit()


_LAZY_COMMAND_MODULES: frozenset[str] = frozenset(
    {
        "._app_live",
        "._config",
        "._ledger",
        "._modelo",
        "._overview",
        "._review",
        ".registry",
    },
)


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

        if module_name not in _LAZY_COMMAND_MODULES:
            raise RuntimeError(f"unregistered lazy CLI module: {module_name}")
        try:
            # Module names are constrained to `_LAZY_COMMAND_MODULES`.
            module = import_module(module_name, __name__)  # nosemgrep
        except ModuleNotFoundError as error:
            return _import_failure_surface(group_label, error)
        return module.app

    return _factory


def _lazy(group_name: str, name: str, module_name: str) -> None:
    """Register ``module_name`` as a lazily-loaded subcommand of ``group_name``."""
    _register_lazy_subcommand(
        group_name,
        _LazySubcommand(name, _lazy_loader(module_name, name), decorate=_decorate_typer_app),
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
_decorate_typer_app(app)


def main() -> None:
    """Console-script entry point.

    Pins ``prog_name`` so Typer's usage lines say ``aeat`` even when the
    launcher is ``aeat.EXE`` on Windows.

    An explicit ``--language`` / ``--lang`` flag is promoted to
    ``AEAT_OUTPUT_LANGUAGE`` here, before the lazily imported subcommand modules
    render their ``tr(...)``-bound help, so the flag genuinely localises help
    text per operator-surface ADR decision D6 (see :mod:`._language_argv`).
    """
    import sys

    _apply_language_argv_to_environment(sys.argv[1:])
    app(prog_name="aeat")


__all__ = ["AppRootResult", "RootStatusResult", "app", "main"]
