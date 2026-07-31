"""Cadrumo's command-line interface (CLI), provided by the ``aeat`` executable.

The command tree exposes two top-level namespaces:

- ``aeat config`` — local configuration, on-ramp wizard, diagnostics.
- ``aeat app`` — operational tax work: overview, ledger, modelo,
  registry, and review.

Every command in this package is a thin transport over the backend application
programming interface (API).
The handler bodies parse argv, call into
``cadrumo.application`` / ``cadrumo.domain``, and render the typed result.
No business logic lives in the CLI layer: validation, mutation,
schema-decision, and persistence all live behind the imported
application functions and pydantic records.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager, nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Protocol, cast

import typer

if TYPE_CHECKING:
    import click

    from ...core import OptionalExtra

    # Type-checking-only: gives static consumers of the lazy `command_schema_refs`
    # re-export (below, via `__getattr__`) its real signature without paying the
    # eager registry-parse import cost at runtime -- this line never executes.
    from ._app_contract import command_schema_refs as command_schema_refs
    from ._config._google import OAuthClientPayload as OAuthClientPayload
from typer._types import TyperChoice as _TyperChoice

from ._stdio import _ensure_help_render_width as _ensure_help_render_width
from ._stdio import configure_stdio_for_utf8 as _configure_stdio_for_utf8

# Force UTF-8 on stdout / stderr before any echo, log, or Rich console
# instantiation. Default Windows terminals expose cp1252; emoji,
# CJK, the U+2192 arrow used by the review queue, and the § sign
# in some IVA citations all crash typer.echo on cp1252. See
# :mod:`._stdio` for the rationale.
_configure_stdio_for_utf8()

from ...core import PRODUCT_IDENTITY as _PRODUCT_IDENTITY
from ...core import ProfileSessionRefusalReason as _ProfileSessionRefusalReason
from ...core.cli_metadata import is_metadata_invocation as _is_metadata_invocation
from ...core.i18n import SUPPORTED_OUTPUT_LANGUAGES as _SUPPORTED_OUTPUT_LANGUAGES
from ...core.i18n import tr
from ...core.output_rendering import OutputFormat as _OutputFormat
from ...core.redaction import redact_for_cli_output as _redact_for_cli_output
from ._command_suggestions import CadrumoTyperGroup as _CadrumoTyperGroup
from ._command_suggestions import (
    LazySubcommand as _LazySubcommand,
)
from ._command_suggestions import (
    register_lazy_subcommand as _register_lazy_subcommand,
)
from ._common import _emit_envelope
from ._errors import CliCommandGroupUnavailableError as _CliCommandGroupUnavailableError
from ._errors import decorate_typer_app as _decorate_typer_app
from ._language_argv import apply_language_argv_to_environment as _apply_language_argv_to_environment
from ._log_levels import apply_to_root_logger as _apply_to_root_logger
from ._log_levels import resolve_log_level as _resolve_log_level
from ._root_payloads import AppRootResult, RootStatusResult


class _TyperExceptionsState(Protocol):
    """Local marker for Cadrumo's idempotent Typer localisation state."""

    _cadrumo_parse_errors_localised: bool


# The command tree is assembled lazily: each leaf command module pulls
# the application layer and, transitively, the ~0.6 s registry parse.
# Importing every module just to build the Cadrumo app object made
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
    name=_PRODUCT_IDENTITY.cli_executable,
    help=tr("cli.root.app_help"),
    no_args_is_help=False,
    invoke_without_command=True,
    add_help_option=False,
    add_completion=True,
    cls=_CadrumoTyperGroup,
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
    format_: _OutputFormat = typer.Option(
        _OutputFormat.TEXT,
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

        ctx.with_resource(override_settings(cadrumo_output_language=language))
    _apply_to_root_logger(_resolve_log_level(quiet=quiet, verbose=verbose, debug=debug))
    state = ctx.ensure_object(dict)
    state["format"] = format_
    if version:
        _emit_version_report_and_exit(detail=detail)
    if help_:
        _emit_root_help_and_exit(ctx)
    if ctx.invoked_subcommand is not None and _is_introspection_only_invocation(ctx):
        return
    # Defer profile override and bucket-session activation to after the
    # version/help fast-paths (already exited above). Bare invocation
    # (ctx.invoked_subcommand is None) defers the full application-layer
    # imports (user_profile, wizard, workflow) into its own branch so
    # state-free dispatch avoids the registry load.
    if profile is not None:
        _activate_profile_override(ctx, profile)
    else:
        _normalize_root_active_profile(ctx)
    if ctx.invoked_subcommand is None:
        _emit_bare_invocation_and_exit(ctx)
    # A subcommand is being invoked. Activate the bucket session here
    # so verbs that need it have access to the active profile's
    # encrypted records. This is deferred after the bare-invocation
    # path to keep it out of the state-free surfaces (--version,
    # --help, bare invocation). Help and usage-error renderings are
    # introspection surfaces too: they must never require the master
    # key, or a newcomer without CADRUMO_SECRET_PASSPHRASE cannot browse
    # the command tree and an unknown-command typo is masked by a
    # master-key refusal instead of the usage error.
    _activate_active_bucket_session(ctx)


def _emit_version_report_and_exit(*, detail: bool) -> None:
    """Render the ``--version`` surface and exit, skipping the registry load.

    Fast-path: bare ``aeat --version`` skips the registry load — registry
    validation must not run on the version surface. The ``--detail`` variant
    re-invokes with the registry summary populated. The diagnostics import is
    deferred here so it never loads on a non-version surface.
    """
    from ...application.diagnostics import build_cli_version_report, render_cli_version_text

    report = build_cli_version_report(with_registry=detail)
    if detail:
        typer.echo(render_cli_version_text(report))
    else:
        # The short `aeat --version` line is machine-format semver
        # (e.g. "Cadrumo 1.2.3") consumed by CI tooling and package
        # managers. Cadrumo policy treats semver output as machine-format,
        # not operator text, so tr() wrapping is intentionally omitted.
        typer.echo(f"{_PRODUCT_IDENTITY.display_name} {report.package_version}")
    raise typer.Exit()


def _emit_root_help_and_exit(ctx: typer.Context) -> None:
    """Render the root help document and exit.

    The operator-surface import is deferred so the help-document builder loads
    only on a help surface, not on every dispatch.
    """
    from ...application.operator_surface import build_help_document, render_help_text

    document = build_help_document("root")
    typed_help = RootStatusResult.model_validate(document.model_dump(mode="json"))
    _emit_envelope(ctx, command="root.status", result=typed_help, lines=render_help_text(document).splitlines())
    raise typer.Exit()


def _normalize_root_active_profile(ctx: typer.Context) -> None:
    """Normalize the ambient active-profile label to its UUID for storage routing.

    No explicit ``--profile``: the active profile comes from the
    ``active-profile`` pointer file. Normalize a display-name
    value to its UUID so the core storage-route resolver (UUID-only) resolves it
    — an operator only knows the label, never the UUID. Bootstrap-exempt recovery
    verbs must not read bucket manifests here: they are the surfaces operators use
    when those manifests are torn.
    """
    from ._bootstrap_exempt import is_bootstrap_exempt

    verb_path = _full_invocation_verb_path() or _verb_path_from_context(ctx)
    explicit_profile_show = _is_explicit_profile_show_invocation(ctx, verb_path)
    if not is_bootstrap_exempt(verb_path) and not explicit_profile_show:
        from ...core import FormerProductStateError
        from ._errors import CliRefusedBoundaryError

        try:
            _normalize_active_profile_label_to_uuid(ctx)
        except FormerProductStateError as exc:
            raise CliRefusedBoundaryError(
                str(exc),
                suggestion="aeat config repair --help",
            ) from exc


def _emit_bare_invocation_and_exit(ctx: typer.Context) -> None:
    """Render the bare-invocation landing or overview surface, then exit.

    The landing surface needs the application operator_surface layer; deferring
    the import keeps it off the ``--version`` / ``--help`` fast-paths. Bare
    invocation without an active profile does NOT import workflow or overview
    (which pull the registry) — it only renders the profile-creation prompt. Use
    the lightweight core resolver to avoid importing workflow.
    """
    from ...adapters.persistence.storage import has_active_bucket_session
    from ...application.operator_surface import build_root_landing_report
    from ...core import resolve_active_bucket_id
    from ._root_landing import render_cli_root_landing_lines

    active = resolve_active_bucket_id()
    landing = build_root_landing_report(active)
    if active is None or not has_active_bucket_session():
        # Bare invocation with no active profile OR no open
        # session: render the landing card and exit. Bare
        # invocation is a metadata-emitting introspection
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
    ctx.with_resource(override_settings(cadrumo_active_profile=pointer.bucket_id))


def _normalize_active_profile_label_to_uuid(ctx: typer.Context) -> None:
    """Normalize a display-name active-profile selection to its UUID bucket id.

    An operator addresses a profile by the label they chose at ``profile
    create``; the immutable UUID bucket id is never surfaced to them. When no
    ``--profile`` flag is given, the active profile is resolved from the
    ``active-profile`` pointer file: if that value is a display LABEL rather
    than a UUID bucket directory, the core
    storage-route resolver — which keys directly on ``buckets/<value>`` — would
    hard-miss with a "no registered bucket manifest" refusal on every
    profile-bound command. Resolve the label to its UUID through the single
    application-layer resolver and pin the override to the UUID, so the core
    route resolver (which stays UUID-only) receives the identifier it expects.

    No-ops when no active profile resolves or when the label does not match any
    live profile (the per-command active-profile guard surfaces that). A live
    UUID-valued input is pinned to the same UUID; a tombstoned UUID-valued input
    is refused instead of bypassing the label resolver's lifecycle filter. An
    ambiguous label (more than one live match) raises a clear refusal rather than
    an arbitrary pick.
    """
    from ...application.workflow import (
        ProfileLabelAmbiguousError,
        read_profile_bucket_by_id,
        resolve_profile_bucket,
    )
    from ...core import resolve_active_bucket_id
    from ...core.config import override_settings
    from ...core.errors import CadrumoError
    from ._errors import CliRefusedBoundaryError

    active = resolve_active_bucket_id()
    if active is None:
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
    except CadrumoError:
        return
    if pointer is None:
        try:
            inactive_bucket = read_profile_bucket_by_id(active)
        except CadrumoError:
            return
        if inactive_bucket is not None:
            raise CliRefusedBoundaryError(
                translated_message="cli.config.profile.unknown_profile",
                context={"name": active},
            )
        # Not a live label either; leave resolution to the per-command active
        # profile guard, which emits the canonical no-active-profile refusal.
        return
    ctx.with_resource(override_settings(cadrumo_active_profile=pointer.bucket_id))


def _activate_active_bucket_session(ctx: typer.Context) -> None:
    """Active-gate the CLI session against the bootstrap-exempt registry.

    Three outcomes:

    - Bootstrap-exempt verbs (``profile create``, ``profile import``,
      ``config login`` / ``config logout``, ``config repair`` family) run
      without a session — return early.
    - No active profile resolves — return without opening a session.
      Each non-exempt verb carries its own
      ``resolve_active_bucket_id() is None`` guard that refuses with a
      translated message; opening a session here against an absent
      per-bucket database would pre-empt that cleaner per-verb refusal
      and break the bare-invocation landing card.
    - An active profile resolves — RESUME its persisted login session so
      the verb body can decrypt stored records, or refuse instructively.

    The session is resumed, never implicitly unlocked. This callback used
    to enter the master-key provider directly, which on the file backend
    prompted for (or read) the passphrase on EVERY command and on the
    keyring backend unlocked silently with no authentication gate at all.
    Authentication is now a deliberate act — ``aeat config login`` — and
    every other verb either resumes that login's still-valid session or
    refuses, naming the verb that fixes it.

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
    from ...adapters.persistence.storage import has_active_bucket_session
    from ...application.storage_write_policy import inspect_storage_write_policy
    from ...core import resolve_active_bucket_id
    from ._bootstrap_exempt import is_bootstrap_exempt
    from ._command_suggestions import INVOCATION_REMAINDER_META_KEY
    from ._errors import CliRefusedBoundaryError

    verb_path = _full_invocation_verb_path() or _verb_path_from_context(ctx)
    exempt = is_bootstrap_exempt(verb_path)
    explicit_profile_show = _is_explicit_profile_show_invocation(ctx, verb_path)
    argv_tokens = _full_invocation_tokens() or tuple(
        str(token) for token in ctx.meta.get(INVOCATION_REMAINDER_META_KEY, ())
    )
    write_policy = inspect_storage_write_policy(verb_path, bootstrap_exempt=exempt, argv_tokens=argv_tokens)
    if not write_policy.allowed:
        raise CliRefusedBoundaryError(
            write_policy.render_refusal_message(),
            context=write_policy.refusal_context(),
        )
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
    if explicit_profile_show:
        return
    if _is_unregistered_profile_status_probe(verb_path, active_bucket_id):
        return
    _register_wizard_catalogue_for_profile_keys()
    if has_active_bucket_session():
        return
    if exempt:
        return
    _resume_profile_session_or_refuse(ctx, active_bucket_id)
    # The active profile's encrypted record is only decryptable once the
    # bucket session above is open. ``output_language()`` is cached, and
    # its cache key (env vars + `.env` mtime) does not vary when a
    # session opens — so any `tr()` fired during module import or the
    # root callback cached the settings-default language before the
    # profile preference was readable. Drop the cache here so the verb
    # body re-resolves through the now-readable profile preference.
    from ...core.i18n import clear_output_language_cache

    clear_output_language_cache()


#: Persisted-session refusal reasons that mean "this operator never logged
#: in", as opposed to "a login existed and has since lapsed". The two get
#: different operator copy: one is an instruction, the other is news.
#: Held as enum members rather than their string values so a future rename
#: cannot silently drop a reason out of this set and flip an operator from
#: "you are not logged in" to "your session expired".
_LOGGED_OUT_REFUSALS: frozenset[_ProfileSessionRefusalReason] = frozenset(
    {
        _ProfileSessionRefusalReason.ABSENT,
        _ProfileSessionRefusalReason.KEYCHAIN_ENTRY_MISSING,
    },
)


def _resume_profile_session_or_refuse(ctx: typer.Context, bucket_id: str) -> None:
    """Resume the persisted login session, or refuse naming ``aeat config login``.

    Fail-closed: the application resume authority deletes stale artefacts
    and reports a typed reason, and this callback opens nothing on any
    refusal branch. The refusal is a BLOCKING failure, so it raises and
    renders through the stderr error document (which shares the envelope
    spine and carries the next-verb ``suggestion``) rather than riding the
    non-blocking ``notices`` channel.

    One sanctioned escape hatch survives: a configured
    ``CADRUMO_SECRET_PASSPHRASE`` is the headless/CI channel and keeps
    working process-scoped, needing neither a pointer nor a persisted
    session — exactly today's file-backend behavior. That is not a bypass:
    the passphrase IS the authentication factor, supplied non-
    interactively instead of at a prompt. An operator who has not supplied
    it — every interactive operator, and every keyring-backend host — meets
    the gate and must log in.
    """
    from ...adapters.persistence.storage import get_master_key_provider
    from ...application.user_profile import resume_active_profile_session
    from ._errors import CliRefusedBoundaryError

    refusal = resume_active_profile_session(bucket_id=bucket_id)
    if refusal is None:
        return
    if _headless_secret_channel_active():
        ctx.with_resource(get_master_key_provider())
        return
    if refusal in _LOGGED_OUT_REFUSALS:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.errors.profile_session_absent",
            context={"reason": refusal.value},
            suggestion="aeat config login",
        )
    raise CliRefusedBoundaryError(
        translated_message="cli.config.errors.profile_session_expired",
        context={"reason": refusal.value},
        suggestion="aeat config login",
    )


def _headless_secret_channel_active() -> bool:
    """Return whether the sanctioned headless secret channel is configured.

    ``CADRUMO_SECRET_PASSPHRASE`` is the project's declared non-interactive
    secret channel (secrets, never selection — selection stays with
    ``--profile`` or the pointer). An environment that carries it has
    already supplied the authentication factor, so the file backend
    unlocks process-scoped exactly as it does today; an environment that
    does not meets the login gate.
    """
    from ...core.config import load_settings

    return load_settings().cadrumo_secret_passphrase is not None


def _is_unregistered_profile_status_probe(verb_path: str | None, active_bucket_id: str) -> bool:
    """Let ``config profile status`` diagnose a dangling active pointer."""
    if verb_path != "config profile status":
        return False
    from ...application.workflow import read_profile_bucket_by_id

    return read_profile_bucket_by_id(active_bucket_id) is None


def _is_explicit_profile_show_invocation(ctx: typer.Context, verb_path: str | None) -> bool:
    """Return whether the operator targeted ``config profile show <name>``.

    Explicit profile inspection resolves its own label/UUID target and must stay
    reachable when the unrelated active-profile pointer is stale. The no-arg
    ``config profile show`` form still depends on the active profile and remains
    active-profile guarded.
    """
    from ._command_suggestions import INVOCATION_REMAINDER_META_KEY

    raw_tokens = _full_invocation_tokens() or tuple(
        str(token) for token in ctx.meta.get(INVOCATION_REMAINDER_META_KEY, ())
    )
    if raw_tokens:
        command_start = _profile_show_command_start(raw_tokens)
        if command_start is None:
            return False
        return _has_explicit_profile_show_target(raw_tokens[command_start + 3 :])

    if verb_path is None:
        return False
    verb_tokens = tuple(verb_path.split())
    if verb_tokens[:3] != ("config", "profile", "show"):
        return False
    return _has_explicit_profile_show_target(verb_tokens[3:])


def _profile_show_command_start(tokens: tuple[str, ...]) -> int | None:
    for index in range(0, max(len(tokens) - 2, 0)):
        if tokens[index : index + 3] == ("config", "profile", "show"):
            return index
    return None


def _has_explicit_profile_show_target(tokens: tuple[str, ...]) -> bool:
    value_options = {"--format", "--language", "--lang", "--output-language", "--profile"}
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token.startswith("-"):
            option = token.split("=", 1)[0]
            if "=" not in token and option in value_options:
                skip_next = True
            continue
        return True
    return False


def _register_wizard_catalogue_for_profile_keys() -> None:
    """Import wizard registration side effects before profile-key reads."""
    from ...application.wizard import _catalogue as _wizard_catalogue
    from ...application.wizard import _persistence as _wizard_persistence

    _ = (_wizard_catalogue, _wizard_persistence)


def _is_introspection_only_invocation(ctx: typer.Context) -> bool:
    """Return whether the invocation can only render help or a usage error.

    Two introspection shapes never execute a verb body and therefore must
    not open the encrypted bucket session (which demands the master key and,
    without ``CADRUMO_SECRET_PASSPHRASE`` on a non-interactive stdin, refuses):

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
    capture staged by :class:`CadrumoTyperGroup.invoke` (which works for both
    real-process and in-process invocations).
    """
    from ._command_suggestions import INVOCATION_REMAINDER_META_KEY

    remainder = list(ctx.meta.get(INVOCATION_REMAINDER_META_KEY, ()))
    if _is_metadata_invocation(remainder):
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
    # A bare subgroup invocation (for example `aeat config profile`) can
    # only render that group's help/callback surface. Treat it like help so
    # discovery never asks for the encrypted profile passphrase first.
    return hasattr(command, "list_commands")


def _verb_path_from_context(ctx: typer.Context) -> str | None:
    """Recover the verb path from the typer/click context.

    Fallback for in-process invocations (e.g. ``CliRunner`` in tests)
    where ``sys.argv[0]`` is not the ``aeat`` entry-point and the
    argv-based :func:`_full_invocation_verb_path` returns ``None``.
    The bootstrap-exemption gate treats a ``None`` verb path as
    "bare invocation", but the caller
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
    # a warning, so use the internal storage only for supported Click 8 runtimes.
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
    tokens = list(_full_invocation_tokens())
    if not tokens:
        return None
    verb_tokens: list[str] = []
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token.startswith("-"):
            if token in ("--language", "--lang", "--format", "--profile", "--output-language") and "=" not in token:
                skip_next = True
            continue
        verb_tokens.append(token)
    if not verb_tokens:
        return None
    return " ".join(verb_tokens)


def _full_invocation_tokens() -> tuple[str, ...]:
    """Return raw operator argv tokens for real ``aeat`` entrypoint runs."""
    import sys
    from pathlib import Path

    executable = Path(sys.argv[0]).name.lower()
    canonical_executable = _PRODUCT_IDENTITY.cli_executable.lower()
    if executable not in {canonical_executable, f"{canonical_executable}.exe"}:
        return ()
    return tuple(sys.argv[1:])


def _surface_for_import_failure(name: str, error: ModuleNotFoundError) -> typer.Typer:
    """Classify ``error`` and either degrade gracefully or refuse loudly.

    A command group's module imports lazily, so its failure has to be
    classified before it can be reported. Exactly one class of failure may be
    presented as an unavailable command: the missing module belongs to a
    registered :data:`~core.OPTIONAL_EXTRAS` capability package, which a bare
    install legitimately omits. The group then answers with a placeholder whose
    help and refusal both name the extra and its install command.

    Every other missing module is a REQUIRED dependency (or a first-party
    module) whose absence means a broken installation, so it raises
    :exc:`CliCommandGroupUnavailableError` here — during command resolution,
    before any subcommand can be dispatched — rather than degrading. Presenting
    it as an unavailable command would convert a hard dependency failure into an
    invisible capability loss: the whole subtree would answer ``--help`` with a
    plausible placeholder and every subcommand with "no such command", naming no
    cause. Import failures that are not :exc:`ModuleNotFoundError` at all (a
    syntax error, a circular import, a module-level bug) never reach this
    helper; they propagate to the crash boundary unchanged.

    Args:
        name: The command-group name whose subtree failed to load.
        error: The import failure raised by the group's module.

    Returns:
        A placeholder Typer group, only for a registered optional extra.

    Raises:
        CliCommandGroupUnavailableError: If the missing module is not owned by
            a registered optional extra.
    """
    from ...core import optional_extra_for_module

    missing = _missing_dependency_name(error)
    extra = optional_extra_for_module(missing)
    if extra is None:
        # Redact only the operator-facing value: classification above must see
        # the real module name, but a module name can carry a profile id.
        raise _CliCommandGroupUnavailableError(group=name, module=_redact_for_cli_output(missing)) from error
    return _optional_extra_surface(name, extra)


def _optional_extra_surface(name: str, extra: OptionalExtra) -> typer.Typer:
    """Return the placeholder group for a legitimately-absent optional extra.

    The group's help names the feature and the extra that supplies it, and
    invoking it refuses through :exc:`~core.MissingOptionalExtraError` — the
    canonical optional-extra refusal, which carries the exact
    ``pip install cadrumo[<extra>]`` remedy — so neither surface is a bare
    "unavailable".

    The help deliberately names the extra rather than the bracketed install
    command: Typer renders group help through Rich, which parses ``[browser]``
    as a style tag and silently drops it. The refusal is plain-rendered, so it
    carries the literal command.
    """
    failed_app = typer.Typer(
        name=name,
        help=tr("cli.root.unavailable_optional_extra_help", feature=extra.feature, extra=extra.extra),
        no_args_is_help=False,
        invoke_without_command=True,
    )

    @failed_app.callback()
    def _failed() -> None:
        from ...core import MissingOptionalExtraError

        raise MissingOptionalExtraError(extra)

    return failed_app


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
    cls=_CadrumoTyperGroup,
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


_LAZY_COMMAND_REGISTRATIONS: tuple[tuple[str, str, str], ...] = (
    ("app", "overview", "._overview"),
    ("app", "contract", "._app_contract"),
    ("app", "agent", "._app_agent_workspace"),
    ("app", "diagnostics", "._app_diagnostics"),
    ("app", "ledger", "._ledger"),
    ("app", "live", "._app_live"),
    ("app", "maintenance", "._app_maintenance"),
    ("app", "modelo", "._modelo"),
    ("app", "quickfile", "._app_quickfile"),
    ("app", "registry", ".registry"),
    ("app", "review", "._review"),
    (_PRODUCT_IDENTITY.cli_executable, "config", "._config"),
)

# The dynamic-import guard is derived from the same registrations that wire
# the command tree, so adding a command cannot leave one security list stale.
_LAZY_COMMAND_MODULES: frozenset[str] = frozenset(module for _group, _name, module in _LAZY_COMMAND_REGISTRATIONS)


def _lazy_loader(module_name: str, group_label: str) -> Callable[[], typer.Typer]:
    """Build a deferred factory importing ``module_name``'s ``app`` Typer.

    A :exc:`ModuleNotFoundError` is handed to
    :func:`_surface_for_import_failure`, which degrades to a placeholder group
    only when the missing module belongs to a registered optional extra and
    otherwise refuses loudly. Every other import failure propagates untouched.
    """

    def _factory() -> typer.Typer:
        from importlib import import_module

        if module_name not in _LAZY_COMMAND_MODULES:
            raise RuntimeError(f"unregistered lazy CLI module: {module_name}")
        try:
            # Module names are constrained to `_LAZY_COMMAND_MODULES`.
            module = import_module(module_name, __name__)  # nosemgrep
        except ModuleNotFoundError as error:
            return _surface_for_import_failure(group_label, error)
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
# Cadrumo app object can be constructed without importing the command
# tree (and therefore without the registry parse).
# ---------------------------------------------------------------------


for _group_name, _command_name, _module_name in _LAZY_COMMAND_REGISTRATIONS:
    _lazy(_group_name, _command_name, _module_name)
app.add_typer(app_app, name="app")
_decorate_typer_app(app)


def __getattr__(name: str) -> object:
    """Lazily resolve re-exported names without importing heavy submodules eagerly.

    ``_app_contract``, ``_config._google``, and ``_modelo_rendering`` are
    kept off the eager import path precisely so constructing the Cadrumo CLI
    app object never pulls the registry-dependent command tree; a
    top-level ``from ._app_contract import command_schema_refs`` (and
    siblings) would defeat that and reintroduce the startup cost
    :mod:`._stdio` / the lazy command-tree gate guard against.
    """
    if name == "command_schema_refs":
        from ._app_contract import command_schema_refs

        return command_schema_refs
    if name == "OAuthClientPayload":
        from ._config._google import OAuthClientPayload

        return OAuthClientPayload
    if name in ("calculation_revision_lines", "calculation_revision_payload"):
        from . import _modelo_rendering

        return getattr(_modelo_rendering, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _localise_help_section_headers() -> None:
    """Localise Typer's Rich ``--help`` section headers to the resolved locale.

    Typer renders the ``Options`` / ``Commands`` / ``Arguments`` panel titles
    (the ``--help`` section headers) and the parse-error ``Try '... --help' for
    help.`` hint from module-level constants in :mod:`typer.rich_utils` that are
    frozen to English at import. The already-``tr()``-bound option *descriptions*
    localise via the :func:`_apply_language_argv_to_environment` env promotion,
    but the framework-owned section headers stayed English — the residual gap the
    operator-surface ``--language`` help-honesty contract leaves open.
    This rebinds those constants to the operator's resolved output language.

    Invocation-scoped, no cross-invocation leak: it runs once per console
    process from :func:`main` after the language flag has been promoted, always
    sets every header to *this* invocation's locale (never a partial/stale set),
    and is never reached by the in-process test runner (which does not call
    :func:`main`). Real ``aeat`` runs are one process per invocation, so the
    module-global rebind reflects only the current process's locale.
    """
    import typer.rich_utils as _rich_utils

    _rich_utils.OPTIONS_PANEL_TITLE = tr("cli.help.panel.options", default="Options")
    _rich_utils.COMMANDS_PANEL_TITLE = tr("cli.help.panel.commands", default="Commands")
    _rich_utils.ARGUMENTS_PANEL_TITLE = tr("cli.help.panel.arguments", default="Arguments")
    _rich_utils.ERRORS_PANEL_TITLE = tr("cli.help.panel.error", default="Error")
    # RICH_HELP keeps the ``[blue]…[/]`` Rich markup and the ``{command_path}`` /
    # ``{help_option}`` positional placeholders Typer ``.format()``s; tr() uses
    # ``%{name}`` interpolation so it passes these ``{…}`` tokens through intact.
    _rich_utils.RICH_HELP = tr(
        "cli.help.try_for_help",
        default="Try [blue]'{command_path} {help_option}'[/] for help.",
    )


def _localise_typer_parse_error_messages() -> None:
    """Bind Typer's vendored parser-error prefixes to the active locale.

    Typer vendors Click, so Click's gettext integration cannot reach the
    ``Missing option`` and ``Invalid value`` strings emitted during argument
    parsing.  Rebind only those presentation prefixes here, after the root
    language flag has been resolved and before the command tree is invoked.
    """
    from typer._click import exceptions as _typer_exceptions
    from typer._click import formatting as _typer_formatting

    if getattr(_typer_exceptions, "_cadrumo_parse_errors_localised", False):
        return

    missing_parameter_format_message = _typer_exceptions.MissingParameter.format_message
    bad_parameter_format_message = _typer_exceptions.BadParameter.format_message
    write_usage = _typer_formatting.HelpFormatter.write_usage

    def localised_missing_parameter_format_message(self) -> str:
        rendered = missing_parameter_format_message(self)
        if rendered.startswith("Missing argument"):
            missing = tr("cli.help.missing_argument", default="Missing argument")
            return f"{missing}{rendered.removeprefix('Missing argument')}"
        if rendered.startswith("Missing option"):
            missing = tr("cli.help.missing_option", default="Missing option")
            return f"{missing}{rendered.removeprefix('Missing option')}"
        if rendered.startswith("Missing parameter"):
            missing = tr("cli.help.missing_parameter", default="Missing parameter")
            return f"{missing}{rendered.removeprefix('Missing parameter')}"
        if rendered.startswith("Missing "):
            missing = tr("cli.help.missing_parameter", default="Missing parameter")
            return f"{missing}{rendered.removeprefix('Missing')}"
        return rendered

    def localised_bad_parameter_format_message(self) -> str:
        rendered = bad_parameter_format_message(self)
        if rendered.startswith("Invalid value for "):
            prefix, separator, detail = rendered.partition(": ")
            parameter = prefix.removeprefix("Invalid value for ")
            rendered = (
                f"{tr('cli.help.invalid_value_for', default='Invalid value for %{parameter}', parameter=parameter)}"
                f"{separator}{detail}"
            )
        elif rendered.startswith("Invalid value"):
            invalid_value = tr("cli.help.invalid_value", default="Invalid value")
            rendered = f"{invalid_value}{rendered.removeprefix('Invalid value')}"
        localised_integer = tr("cli.help.not_valid_integer", default="is not a valid integer.")
        # Typer vendors its own Click fork whose IntParamType.name is ``int``
        # (upstream Click uses ``integer``), so the conversion failure reads
        # "is not a valid int."; localise both spellings. The "int." form is
        # not a substring of the "integer." form, so the two replacements are
        # order-independent and non-overlapping.
        return rendered.replace(
            "is not a valid integer.",
            localised_integer,
        ).replace(
            "is not a valid int.",
            localised_integer,
        )

    def localised_write_usage(self, prog: str, args: str = "", prefix: str | None = None) -> None:
        return write_usage(
            self,
            prog,
            args,
            tr("cli.help.usage_prefix", default="Usage: ") if prefix is None else prefix,
        )

    _typer_exceptions.MissingParameter.format_message = localised_missing_parameter_format_message
    _typer_exceptions.BadParameter.format_message = localised_bad_parameter_format_message
    _typer_formatting.HelpFormatter.write_usage = localised_write_usage
    typer_exceptions_state = cast(  # CAST-RATIONALE-TYPER-EXCEPTIONS-STATE: module attribute is Cadrumo-owned.
        "_TyperExceptionsState", _typer_exceptions
    )
    typer_exceptions_state._cadrumo_parse_errors_localised = True


def main() -> None:
    """Console-script entry point.

    Pins ``prog_name`` so Typer's usage lines say ``aeat`` even when the
    launcher is ``aeat.EXE`` on Windows.

    An explicit ``--language`` / ``--lang`` flag is promoted to
    ``CADRUMO_OUTPUT_LANGUAGE`` here, before the lazily imported subcommand modules
    render their ``tr(...)``-bound help, so the flag genuinely localises help
    text (see :mod:`._language_argv`).
    The Rich ``--help`` section headers are then rebound to the same resolved
    locale (see :func:`_localise_help_section_headers`).
    """
    import sys

    arguments = sys.argv[1:]
    metadata_invocation = _is_metadata_invocation(arguments)
    _apply_language_argv_to_environment(arguments)
    _localise_help_section_headers()
    _localise_typer_parse_error_messages()
    # Route the Cl@ve auth-wait progress banner (which carries the AEAT
    # verification code the operator must confirm in their Cl@ve app) to
    # stderr, so a headless operator sees it during the wait instead of
    # having to read the runtime log. stderr keeps the stdout JSON envelope
    # pure; the code is non-secret operator guidance, not a credential.
    progress_sink = nullcontext()
    if not metadata_invocation:
        try:
            _refuse_former_product_state_at_startup()
        except typer.Exit as exit_request:
            raise SystemExit(exit_request.exit_code) from None
        from ...adapters.outbound.aeat import operator_progress_sink

        progress_sink = operator_progress_sink(_emit_operator_progress)
    with _metadata_state_isolation(arguments), _ensure_help_render_width(), progress_sink:
        app(prog_name=_PRODUCT_IDENTITY.cli_executable)


def _refuse_former_product_state_at_startup() -> None:
    """Route a refused retired ``aeat`` state root through the typed CLI error boundary."""
    from ...core import FormerProductStateError
    from ...core.config import Settings
    from ._errors import CliRefusedBoundaryError, _emit_error_and_exit

    try:
        Settings()
    except FormerProductStateError as error:
        _emit_error_and_exit(
            CliRefusedBoundaryError(
                str(error),
                suggestion="aeat config repair --help",
            )
        )


@contextmanager
def _metadata_state_isolation(arguments: list[str]) -> Iterator[None]:
    """Keep help and version imports off an operator's retired ``aeat`` state root.

    Lazy subgroup construction can import modules that instantiate Settings.
    Metadata invocations therefore run against a temporary Cadrumo root and
    database before those imports occur. Normal commands never enter this
    scope and continue to refuse a retired ``aeat`` state root in normal operation.
    """
    if not _is_metadata_invocation(arguments):
        yield
        return

    keys = ("CADRUMO_LOCAL_STORAGE_ROOT", "CADRUMO_DATABASE_URL")
    saved = {key: os.environ.get(key) for key in keys}
    with TemporaryDirectory(prefix="cadrumo-cli-metadata-") as temporary_root:
        root = Path(temporary_root)
        os.environ["CADRUMO_LOCAL_STORAGE_ROOT"] = str(root)
        os.environ["CADRUMO_DATABASE_URL"] = f"sqlite:///{(root / 'cadrumo.db').as_posix()}"
        try:
            yield
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def _emit_operator_progress(banner: str) -> None:
    """Write an operator progress banner to stderr, keeping stdout pure."""
    typer.echo(banner, err=True)


__all__ = [
    "AppRootResult",
    "OAuthClientPayload",
    "RootStatusResult",
    "app",
    "calculation_revision_lines",
    "calculation_revision_payload",
    "command_schema_refs",
    "main",
]
