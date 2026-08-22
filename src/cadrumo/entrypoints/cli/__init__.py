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
from typing import TYPE_CHECKING, cast

import typer
from typer._click.core import Command as _TyCommand

if TYPE_CHECKING:
    import click

    from ...core import OptionalExtra

    # Type-checking-only: gives static consumers of the lazy `command_schema_refs`
    # re-export (below, via `__getattr__`) its real signature without paying the
    # eager registry-parse import cost at runtime -- this line never executes.
    from ._command_schema import command_schema_refs as command_schema_refs
    from ._config._google import OAuthClientPayload as OAuthClientPayload
    from ._modelo_rendering import calculation_revision_lines, calculation_revision_payload
    from ._verb_input_schema import cli_path_for_command_key as cli_path_for_command_key
from typer._types import TyperChoice as _TyperChoice

from ._stdio import _disable_rich_cli_rendering as _disable_rich_cli_rendering
from ._stdio import configure_stdio_for_utf8 as _configure_stdio_for_utf8

# Force UTF-8 on stdout / stderr before any echo, log, or Rich console
# instantiation. Default Windows terminals expose cp1252; emoji,
# CJK, the U+2192 arrow used by the review queue, and the § sign
# in some IVA citations all crash typer.echo on cp1252. See
# :mod:`._stdio` for the rationale.
_configure_stdio_for_utf8()

# Disable Typer/Click's Rich-based help, error, and traceback rendering
# for every Typer() app in the command tree (module-level, read live by
# every render call — see :func:`._stdio._disable_rich_cli_rendering`).
# Plain text keeps option/argument tables readable regardless of the
# invoking terminal's real width.
_disable_rich_cli_rendering()

from ...core import PRODUCT_IDENTITY as _PRODUCT_IDENTITY
from ...core import ProfileSessionRefusalReason as _ProfileSessionRefusalReason
from ...core import StorageCategory as _StorageCategory
from ...core import storage_location as _storage_location
from ...core.cli_metadata import is_metadata_invocation as _is_metadata_invocation
from ...core.i18n import SUPPORTED_OUTPUT_LANGUAGES as _SUPPORTED_OUTPUT_LANGUAGES
from ...core.i18n import tr
from ...core.json_contract import strict_round_trip as _strict_round_trip
from ...core.output_rendering import OutputFormat as _OutputFormat
from ...core.redaction import redact_for_cli_output as _redact_for_cli_output
from ._app_execution_policies import CALCULATION_READ as _ROOT_STATUS_POLICY
from ._app_execution_policies import METADATA as _APP_HELP_POLICY
from ._command_policy import CommandExecutionPolicy as _CommandExecutionPolicy
from ._command_policy import command_execution_policy as _command_execution_policy
from ._command_suggestions import CadrumoTyperGroup as _CadrumoTyperGroup
from ._command_suggestions import (
    LazySubcommand as _LazySubcommand,
)
from ._command_suggestions import execution_policy_for_cli_path as _execution_policy_for_cli_path
from ._command_suggestions import (
    register_lazy_subcommand as _register_lazy_subcommand,
)
from ._common import (
    _emit_envelope,
    active_profile_label,
    attach_cli_policy_refusal_projection,
    attach_cli_policy_verdict,
    cli_policy_refusal_context,
    preserve_requested_cli_leaf,
    project_cli_policy_refusal,
    requested_cli_leaf,
    resolve_cli_precondition_action,
)
from ._errors import CliCommandGroupUnavailableError as _CliCommandGroupUnavailableError
from ._errors import CliRefusedBoundaryError as _CliRefusedBoundaryError
from ._errors import decorate_typer_app as _decorate_typer_app
from ._framework_localisation import (
    localise_help_section_headers as _localise_help_section_headers,
)
from ._framework_localisation import (
    localise_typer_parse_error_messages as _localise_typer_parse_error_messages,
)
from ._language_argv import apply_language_argv_to_environment as _apply_language_argv_to_environment
from ._log_levels import apply_to_root_logger as _apply_to_root_logger
from ._log_levels import resolve_log_level as _resolve_log_level
from ._root_payloads import AppRootResult, RootStatusResult

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
@_command_execution_policy(_ROOT_STATUS_POLICY)
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
    preserve_requested_cli_leaf(ctx)
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
    # A subcommand is being invoked, so the state tree is about to be written
    # to. Build it once here rather than leaving each consumer to create its
    # own corner on first write: that left a fresh machine holding whichever
    # directories had happened to be reached, and made "where does my data
    # live" unanswerable before the fact.
    #
    # Placed after every state-free fast path has already returned or exited.
    # --version, --help, bare invocation and introspection must not touch the
    # filesystem at all: someone browsing the command tree should not have a
    # storage tree created for them, and these surfaces are the ones a
    # newcomer meets first.
    _ensure_storage_tree_for_invocation()
    # Activate the bucket session here so verbs that need it have access to
    # the active profile's encrypted records. Deferred after the
    # bare-invocation path for the same reason as above. Help and usage-error
    # renderings are introspection surfaces too: they must never require the
    # master key, or a newcomer without CADRUMO_SECRET_PASSPHRASE cannot
    # browse the command tree and an unknown-command typo is masked by a
    # master-key refusal instead of the usage error.
    _activate_active_bucket_session(ctx)


def _ensure_storage_tree_for_invocation() -> None:
    """Materialise the state tree, translating a refusal into an operator error.

    The refusal carries the offending path, which is the whole of what the
    operator needs: a directory occupied by a file, or a root that cannot be
    created. Letting it escape as a traceback would bury that line under a
    stack the operator cannot act on.
    """
    from ...core.config import ensure_storage_tree
    from ...core.errors import CoreValidationError

    try:
        ensure_storage_tree()
    except CoreValidationError as refusal:
        raise typer.BadParameter(str(refusal)) from refusal


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
    typed_help = _strict_round_trip(RootStatusResult, document)
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

    verb_path = _resolve_invocation_verb_path(ctx)
    explicit_profile_target = _is_explicit_profile_target_invocation(ctx, verb_path)
    if not is_bootstrap_exempt(verb_path) and not explicit_profile_target:
        from ...application.profile_preconditions import (
            FormerProductDetectionScope,
            former_product_state_verdict,
        )
        from ...core import FormerProductStateError
        from ._errors import CliRefusedBoundaryError

        try:
            _normalize_active_profile_label_to_uuid(ctx)
        except FormerProductStateError as exc:
            raise attach_cli_policy_verdict(
                CliRefusedBoundaryError(str(exc)),
                verdict=former_product_state_verdict(
                    FormerProductDetectionScope.ROOT_PROFILE_NORMALISATION,
                ),
                requested_leaf=requested_cli_leaf(ctx),
            ) from exc


def _emit_bare_invocation_and_exit(ctx: typer.Context) -> None:
    """Render the bare-invocation landing or overview surface, then exit.

    The landing surface needs the application operator_surface layer; deferring
    the import keeps it off the ``--version`` / ``--help`` fast-paths. Bare
    invocation without an active profile does NOT import workflow or overview
    (which pull the registry) — it only renders the profile-creation prompt. Use
    the lightweight core resolver to avoid importing workflow.
    """
    from ...adapters.persistence.storage import active_bucket_session_serves
    from ...application.operator_surface import build_root_landing_report
    from ...application.workflow import list_profile_buckets
    from ...core import resolve_active_bucket_id
    from ._root_landing import render_cli_root_landing_lines

    active = resolve_active_bucket_id()
    landing = build_root_landing_report(
        active_profile_label(),
        profile_selected=active is not None,
        registered_profile_count=len(list_profile_buckets()) if active is None else 0,
    )
    if active is None or not active_bucket_session_serves(active):
        # Bare invocation with no active profile OR no open
        # session: render the landing card and exit. Bare
        # invocation is a metadata-emitting introspection
        # surface analogous to --help/--version and MUST NOT
        # require an active bucket session. Reading
        # workflow_state would force session-open against the
        # encrypted bucket, breaking the cold-start /
        # session-closed-but-profile-exists path.
        typed_landing = _strict_round_trip(RootStatusResult, landing)
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
    typed_overview = _strict_round_trip(RootStatusResult, overview_report)
    _emit_envelope(ctx, command="root.status", result=typed_overview, lines=render_cli_root_landing_lines(landing))
    raise typer.Exit()


def _activate_profile_override(ctx: typer.Context, profile: str) -> None:
    """Resolve ``--profile`` to a bucket id and set the active-profile override.

    Resolves through the single application-layer name-or-UUID resolver so a
    ``--profile`` value may be either the operator display label or the UUID
    bucket id, then pins the override to the resolved UUID.
    """
    from ...application.profile_preconditions import ProfileSelectionFailure, profile_selection_failure_verdict
    from ...application.workflow import ProfileLabelAmbiguousError, resolve_profile_bucket
    from ...core.config import override_settings
    from ._errors import CliRefusedBoundaryError

    requested = profile.strip()
    if not requested:
        raise attach_cli_policy_verdict(
            CliRefusedBoundaryError(
                translated_message="cli.config.profile.unknown_profile",
                context={"name": profile},
            ),
            verdict=profile_selection_failure_verdict(
                ProfileSelectionFailure.BLANK,
                requested_profile=profile,
            ),
            requested_leaf=requested_cli_leaf(ctx),
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
        raise attach_cli_policy_verdict(
            CliRefusedBoundaryError(
                translated_message="errors.refused.refused_profile_label_ambiguous",
            ),
            verdict=profile_selection_failure_verdict(
                ProfileSelectionFailure.AMBIGUOUS,
                requested_profile=requested,
            ),
            requested_leaf=requested_cli_leaf(ctx),
        ) from exc
    if pointer is None:
        raise attach_cli_policy_verdict(
            CliRefusedBoundaryError(
                translated_message="cli.config.profile.unknown_profile",
                context={"name": requested},
            ),
            verdict=profile_selection_failure_verdict(
                ProfileSelectionFailure.UNKNOWN,
                requested_profile=requested,
            ),
            requested_leaf=requested_cli_leaf(ctx),
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
    from ...application.profile_preconditions import ProfileSelectionFailure, profile_selection_failure_verdict
    from ...application.workflow import (
        ProfileLabelAmbiguousError,
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
        raise attach_cli_policy_verdict(
            CliRefusedBoundaryError(
                translated_message="errors.refused.refused_profile_label_ambiguous",
            ),
            verdict=profile_selection_failure_verdict(
                ProfileSelectionFailure.AMBIGUOUS,
                requested_profile=active,
            ),
            requested_leaf=requested_cli_leaf(ctx),
        ) from exc
    except CadrumoError:
        return
    if pointer is None:
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
    callback adds one fail-closed guard before the verb body: a callback whose
    attached execution policy declares ``profile-bound`` may not proceed when
    settings route the primary SQL store to the root fallback database. The
    selected live callback is resolved by canonical path; no parallel path
    catalogue or mutation-name heuristic participates.
    ``_full_invocation_verb_path`` returns ``None`` for in-process test
    runner invocations (``sys.argv[0]`` is not the ``aeat`` console
    script). In that case we fall back to
    :func:`_verb_path_from_context`, which reconstructs the verb chain
    from the typer/click context so the bootstrap-exemption gate sees
    the same verb path it would on a real ``aeat`` invocation — without
    this fallback an in-process invocation would be misclassified as
    bare and the session would never open.
    """
    from ...adapters.persistence.storage import active_bucket_session_serves
    from ...core import resolve_active_bucket_id
    from ._bootstrap_exempt import is_bootstrap_exempt

    verb_path = _resolve_invocation_verb_path(ctx)
    exempt = is_bootstrap_exempt(verb_path)
    explicit_profile_target = _is_explicit_profile_target_invocation(ctx, verb_path)
    leaf = requested_cli_leaf(ctx)
    if leaf is None:
        raise RuntimeError("root dispatch cannot resolve execution policy without a requested CLI leaf")
    execution_policy = _execution_policy_for_cli_path(app, leaf.canonical_cli_path)
    if execution_policy.write_route == "profile-bound":
        from ...application.storage_write_policy import inspect_storage_write_policy

        write_policy = inspect_storage_write_policy(execution_policy.write_route)
    else:
        write_policy = None
    if write_policy is not None and not write_policy.allowed:
        if write_policy.verdict is None:
            raise RuntimeError("root write-policy refusal is missing its requested leaf or verdict")
        projection = project_cli_policy_refusal(
            requested_leaf=leaf,
            verdict=write_policy.verdict,
        )
        raise attach_cli_policy_refusal_projection(
            _CliRefusedBoundaryError(
                write_policy.render_refusal_message(),
                context=cli_policy_refusal_context(projection),
            ),
            projection=projection,
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
    # Bootstrap verbs establish their own storage span after dispatch.  They
    # must leave before even the wizard-catalogue registration below: loading
    # that application path can resolve profile-bound runtime collaborators
    # while the selected bucket is deliberately locked.
    if exempt:
        return
    if explicit_profile_target:
        return
    if _is_unregistered_profile_status_probe(verb_path, active_bucket_id):
        return
    _register_wizard_catalogue_for_profile_keys()
    # A session bound to another bucket does not serve this verb's profile;
    # returning on its presence skips the resume and runs against the wrong one.
    if active_bucket_session_serves(active_bucket_id):
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

    An interactive operator logs in HERE, on the screen this callback
    offers, rather than being sent away to run ``login`` and then retype
    the invocation that was already parsed. Both shapes ask for the same
    single passphrase; only one of them costs two extra commands. Every
    caller that cannot be shown a screen — JSON, piped, CI, dumb terminal
    — and every operator who leaves the screen without unlocking falls
    through to the refusals below unchanged.
    """
    from ...adapters.persistence.storage.errors import KeyringUnavailableError
    from ...application.profile_preconditions import profile_session_failure_verdict
    from ...application.user_profile import bind_resumed_profile_session, login_profile
    from ._errors import CliRefusedBoundaryError

    refusal = bind_resumed_profile_session(bucket_id=bucket_id)
    if refusal is None:
        return
    if _headless_secret_channel_active():
        # This is an explicit current-profile password authentication, not a
        # provider or shared-master-key fallback for the session cache.
        #
        # Checked BEFORE the keyring branch below, and the order is the whole
        # point. A host with no usable OS keychain cannot PERSIST a session, so
        # every invocation there is its own process with no session to resume:
        # `config login` succeeds and then says so ("la sesion no se puede
        # guardar; este inicio de sesion solo vale para el comando actual").
        # With the keyring refusal first, that host could never reach this
        # branch, so the project's declared non-interactive channel authenticated
        # nothing and no profile-scoped verb could run at all -- which is how a
        # headless run of the calculate-to-export path was blocked outright.
        # Reaching it first revives nothing: this is the operator's own current-
        # profile password, the same factor a prompt would collect, not a
        # provider or shared-master-key route and not a discarded receipt.
        login_profile(name=bucket_id)
        return
    if refusal is _ProfileSessionRefusalReason.KEYRING_UNAVAILABLE:
        # A real process-scoped login is possible only when the explicit
        # password path is invoked by the operator.  Never treat a broken
        # acceleration keychain as permission to revive a provider/master-key
        # route or discard its receipt evidence.
        raise KeyringUnavailableError("OS keychain is unavailable for profile-session acceleration")
    if _authenticated_at_the_gate(ctx, bucket_id=bucket_id):
        return
    # Session state is keyed by the opaque bucket UUID, but the recovery
    # command is addressed by the operator-facing profile label.  Keep those
    # identities separate: projecting the storage UUID as ``config login``'s
    # argument makes the typed action both privacy-redacted and non-executable.
    verdict = profile_session_failure_verdict(
        refusal,
        profile_name=active_profile_label() or bucket_id,
    )
    if refusal in _LOGGED_OUT_REFUSALS:
        error = CliRefusedBoundaryError(
            translated_message="cli.config.errors.profile_session_absent",
            context={"reason": refusal.value},
        )
    else:
        error = CliRefusedBoundaryError(
            translated_message="cli.config.errors.profile_session_expired",
            context={"reason": refusal.value},
        )
    raise attach_cli_policy_verdict(
        error,
        verdict=verdict,
        requested_leaf=requested_cli_leaf(ctx),
    )


def _authenticated_at_the_gate(ctx: typer.Context, *, bucket_id: str) -> bool:
    """Offer the login screen to a gated verb; report whether a session is open.

    ``False`` means the verb must still refuse — no screen could be shown,
    the operator left without unlocking, or the session did not survive
    into this context. The caller then raises exactly the refusal it would
    have raised without this step, so the gate can only ever remove a
    round trip, never admit an unauthenticated verb.

    Two things have to happen after the screen closes, and neither is
    optional:

    The session is re-resumed rather than assumed. Textual runs the unlock
    in an asyncio task, and a ``ContextVar`` bound inside that child task
    does not flow back into this synchronous context — so the login is
    real and persisted, but the in-process session this callback is
    supposed to leave open is not yet bound here. Re-resuming through the
    same authority binds it. (``_manager_dispatch`` learned this on the
    registration screen and does the same thing for the same reason.)

    The active profile is re-pointed when the operator picked a different
    one. By the time this runs, ``_resolve_active_profile_pointer`` has
    already pinned ``cadrumo_active_profile`` to whoever was selected
    BEFORE the screen opened. Left alone, a verb would then run against
    the old profile holding the new profile's session — the wrong-taxpayer
    shape this whole surface exists to avoid. The override is re-applied
    to whatever was actually authenticated, so the verb and the session
    always name the same profile.
    """
    from ...application.user_profile import bind_resumed_profile_session
    from ._config import offer_login_to_a_gated_verb

    outcome = offer_login_to_a_gated_verb(ctx, bucket_id=bucket_id)
    if outcome is None:
        return False
    _bind_authenticated_profile_to_invocation(ctx, bucket_id=outcome.bucket_id)
    return bind_resumed_profile_session(bucket_id=outcome.bucket_id) is None


def _bind_authenticated_profile_to_invocation(ctx: typer.Context, *, bucket_id: str) -> None:
    """Make the authenticated profile the current invocation's storage route.

    The requested gate target is not the previous effective settings profile:
    ``profile edit B`` can request and authenticate B while the root callback
    still carries an override for A.  Binding only when the outcome differs
    from the requested target therefore leaves the exact stale route this
    helper exists to retire.  Authentication is the selection authority, so
    every successful outcome replaces the invocation override unconditionally.
    """
    from ...core.config import override_settings

    ctx.with_resource(override_settings(cadrumo_active_profile=bucket_id))


def resume_profile_session_for_target(ctx: typer.Context, *, bucket_id: str) -> None:
    """Authenticate a command-selected profile through the canonical CLI gate."""
    _resume_profile_session_or_refuse(ctx, bucket_id)


def bind_profile_target_to_invocation(ctx: typer.Context, *, bucket_id: str) -> None:
    """Bind an authenticated command-selected profile to this invocation."""
    _bind_authenticated_profile_to_invocation(ctx, bucket_id=bucket_id)


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


def _is_explicit_profile_target_invocation(ctx: typer.Context, verb_path: str | None) -> bool:
    """Return whether a self-scoped profile read has an explicit target.

    Explicit ``show``, ``validate``, and ``history`` reads resolve and unlock
    their own label/UUID target, so an unrelated active-profile pointer must not
    gate them first. Their no-argument forms still depend on the active profile
    and remain active-profile guarded.

    The unlocking half of that sentence was aspirational for a while, and the
    early return here is what made the gap invisible: those verbs resolved
    their target and then never resumed a session for it, so the same record
    read through the active-profile path and through an explicit target gave
    present-with-keys and missing respectively. The named path now resumes its
    own target through the shared resume authority, which is what makes this
    return safe rather than merely quiet.
    """
    from ._command_suggestions import INVOCATION_REMAINDER_META_KEY

    raw_tokens = _full_invocation_tokens() or tuple(
        str(token) for token in ctx.meta.get(INVOCATION_REMAINDER_META_KEY, ())
    )
    if raw_tokens:
        command_start = _explicit_profile_read_command_start(raw_tokens)
        if command_start is None:
            return False
        return _has_explicit_profile_read_target(raw_tokens[command_start + 3 :])

    if verb_path is None:
        return False
    verb_tokens = tuple(verb_path.split())
    if verb_tokens[:2] != ("config", "profile") or verb_tokens[2:3] not in (
        ("show",),
        ("validate",),
        ("history",),
    ):
        return False
    return _has_explicit_profile_read_target(verb_tokens[3:])


def _explicit_profile_read_command_start(tokens: tuple[str, ...]) -> int | None:
    for index in range(0, max(len(tokens) - 2, 0)):
        if tokens[index : index + 2] == ("config", "profile") and tokens[index + 2] in {
            "show",
            "validate",
            "history",
        }:
            return index
    return None


def _has_explicit_profile_read_target(tokens: tuple[str, ...]) -> bool:
    value_options = {
        "--actor",
        "--event-type",
        "--format",
        "--language",
        "--lang",
        "--object-id",
        "--output-language",
        "--profile",
        "--since",
        "--until",
    }
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


def _resolve_invocation_verb_path(ctx: typer.Context) -> str | None:
    """Return the most complete reliable verb path for root routing.

    Click can expose only an already-resolved group prefix while the root
    callback runs (``config profile``), even though the console argv still
    carries the leaf (``config profile create``). A prefix is not sufficient
    for the bootstrap registry: treating it as authoritative turns profile
    creation into a profile-bound command and raises the misleading login
    refusal before the registration TUI can open. Conversely, test runners
    have no console argv, so their reconstructed Click path remains the only
    source. When both describe one invocation, prefer the longer path; when
    they conflict, argv is the operator's literal command and wins.
    """
    preserved_leaf = requested_cli_leaf(ctx)
    if preserved_leaf is not None:
        return " ".join(preserved_leaf.canonical_cli_path)
    return _prefer_complete_verb_path(
        context_path=_verb_path_from_context(ctx),
        argv_path=_full_invocation_verb_path(),
    )


def _prefer_complete_verb_path(*, context_path: str | None, argv_path: str | None) -> str | None:
    """Choose the complete console path without losing test-runner support."""
    if context_path is None:
        return argv_path
    if argv_path is None:
        return context_path
    if argv_path.startswith(f"{context_path} "):
        return argv_path
    if context_path.startswith(f"{argv_path} "):
        return context_path
    return argv_path


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
@_command_execution_policy(_APP_HELP_POLICY)
def _app_root(
    ctx: typer.Context,
    help_: bool = typer.Option(False, "--help", "-h", help=tr("cli.root.app_help_help"), is_eager=True),
) -> None:
    """Render app-level workflow help when requested."""
    if help_ or ctx.invoked_subcommand is None:
        from ...application.operator_surface import build_help_document, render_help_text

        document = build_help_document("app")
        typed_app = _strict_round_trip(AppRootResult, document)
        _emit_envelope(ctx, command="root.app", result=typed_app, lines=render_help_text(document).splitlines())
        raise typer.Exit()


_LAZY_COMMAND_REGISTRATIONS: tuple[tuple[str, str, str], ...] = (
    ("app", "overview", "._overview"),
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
        # Read the attribute rather than fetching it by name. The two are the
        # same operation here, but only this spelling lets a static reader see
        # WHICH attribute a dynamically imported module can reach, which is
        # what proves nothing else escapes through this loader.
        try:
            app = module.app
        except AttributeError as error:
            raise RuntimeError(f"lazy CLI module {module_name!r} does not expose a Typer app") from error
        if not isinstance(app, typer.Typer):
            raise RuntimeError(f"lazy CLI module {module_name!r} does not expose a Typer app")
        return app

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


def full_command_tree() -> _TyCommand:
    """Materialise the whole CLI as one fully-loaded Click command tree.

    Drains every lazily-registered subtree reachable from :data:`app`, converts
    the root Typer application to its Click command, and pins the root name to
    the ``aeat`` executable token so a walker reports operator-facing paths.

    Callers outside this distribution — a conformance gate over the shipped
    operator harness, a reference generator, a capability projection — need the
    COMPLETE tree, and the lazy registry means the naively converted root is
    missing whole command families. This is the one supported way to obtain the
    complete tree; nothing outside this package reads the lazy registry.

    Returns:
        The root Click command with every subtree loaded.
    """
    from typer.main import get_command

    from ._command_suggestions import materialise_lazy_subcommands

    materialise_lazy_subcommands(app)
    root = get_command(app)
    root.name = app.info.name or _PRODUCT_IDENTITY.cli_executable
    return root


def command_execution_policy_for_cli_path(cli_path: tuple[str, ...]) -> _CommandExecutionPolicy:
    """Return callback-attached policy for one live path, loading only that path.

    The concrete policy type remains owned by the CLI metadata module.  This
    facade keeps cross-distribution consumers on the public entrypoint boundary
    without importing the complete command tree.
    """
    return _execution_policy_for_cli_path(app, cli_path)


#: The per-verb input-schema projection re-exported from this facade. The module
#: walks the live command tree and pulls in the operator-action catalogue, so it
#: stays off the eager import path with the other lazy re-exports below.
_VERB_INPUT_SCHEMA_EXPORTS: frozenset[str] = frozenset(
    {
        "DECLARED_UNIMPLEMENTED_SURFACES",
        "JsonType",
        "ResolvedVerbLeaf",
        "SchemaResolutionError",
        "VerbInputSchema",
        "VerbLeafKind",
        "VerbLeafResolutionFailure",
        "VerbParamKind",
        "VerbParameter",
        "assert_schema_coverage",
        "build_verb_input_schemas",
        "cli_argv_for",
        "cli_path_for_command_key",
        "is_exposable_command",
    }
)


def __getattr__(name: str) -> object:
    """Lazily resolve re-exported names without importing heavy submodules eagerly.

    ``_command_schema``, ``_config._google``, and ``_modelo_rendering`` are
    kept off the eager import path precisely so constructing the Cadrumo CLI
    app object never pulls the registry-dependent command tree; a
    top-level ``from ._command_schema import command_schema_refs`` (and
    siblings) would defeat that and reintroduce the startup cost
    :mod:`._stdio` / the lazy command-tree gate guard against.
    """
    if name == "command_schema_refs":
        from ._command_schema import command_schema_refs

        return command_schema_refs
    if name in _VERB_INPUT_SCHEMA_EXPORTS:
        from . import _verb_input_schema

        return getattr(_verb_input_schema, name)
    if name == "OAuthClientPayload":
        from ._config._google import OAuthClientPayload

        return OAuthClientPayload
    if name in ("calculation_revision_lines", "calculation_revision_payload"):
        from . import _modelo_rendering

        return getattr(_modelo_rendering, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
    if _apply_language_argv_to_environment(arguments) is not None:
        # load_settings() holds a process-wide Settings singleton cached by
        # the active-profile pointer, not by env var (core/config.py,
        # _constructed_settings), so the CADRUMO_OUTPUT_LANGUAGE write above is
        # invisible to it once that singleton already exists -- any tr() call
        # that resolved a language before this point (an eager Settings()
        # build during import, for instance) would otherwise keep serving
        # that stale language for the rest of the process, including to
        # _localise_help_section_headers() below. reset_settings_cache() is
        # the sanctioned way to make a process-environment change observed
        # (see its docstring); the same pairing already exists in
        # test_flow_tui_app.py for a language change mid-session.
        from ...core.config import reset_settings_cache

        reset_settings_cache()
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
    with _metadata_state_isolation(arguments), progress_sink:
        app(prog_name=_PRODUCT_IDENTITY.cli_executable)


def _refuse_former_product_state_at_startup() -> None:
    """Route a refused retired ``aeat`` state root through the typed CLI error boundary."""
    from ...application.profile_preconditions import (
        FormerProductDetectionScope,
        former_product_state_verdict,
    )
    from ...core import FormerProductStateError
    from ...core.config import Settings
    from ._errors import CliRefusedBoundaryError, _emit_error_and_exit

    try:
        Settings()
    except FormerProductStateError as error:
        _emit_error_and_exit(
            attach_cli_policy_verdict(
                CliRefusedBoundaryError(str(error)),
                verdict=former_product_state_verdict(
                    FormerProductDetectionScope.STARTUP,
                ),
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
    # Declared exception to the "every tempfile call passes dir=" storage
    # provenance discipline: there is no "destination" to anchor on here.
    # This scope exists so a --help/--version invocation runs against a
    # throwaway root instead of the operator's real one, which may be
    # retired or broken -- isolation FROM a root, not production NEAR one.
    # Anchoring dir= on anything derived from the real root (even a pure,
    # no-I/O computation like the platform user-data directory) reintroduces
    # the dependency this scope exists to sever, and could break --help on
    # exactly the broken-root case it is meant to survive. The OS-default
    # temp root is the correct home, not a gap. The FILENAME joined onto it
    # is a different axis: `storage_location` is a pure dict lookup with no
    # settings/I-O dependency, and `cadrumo.core` is already fully imported
    # above (`_PRODUCT_IDENTITY`), so reading the taxonomy's declared
    # root-fallback-database subpath here costs nothing extra and tracks a
    # future rename instead of drifting from it.
    with TemporaryDirectory(prefix="cadrumo-cli-metadata-") as temporary_root:
        root = Path(temporary_root)
        os.environ["CADRUMO_LOCAL_STORAGE_ROOT"] = str(root)
        database_filename = _storage_location(_StorageCategory.ROOT_FALLBACK_DATABASE).subpath
        os.environ["CADRUMO_DATABASE_URL"] = f"sqlite:///{(root / database_filename).as_posix()}"
        try:
            yield
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def _emit_operator_progress(progress: object) -> None:
    """Write an operator progress banner to stderr, keeping stdout pure."""
    from ...core import OperatorProgress

    if not isinstance(progress, OperatorProgress):
        raise TypeError(f"progress must be OperatorProgress, got {type(progress).__name__}")
    typer.echo(progress.render(), err=True)


__all__ = [
    "DECLARED_UNIMPLEMENTED_SURFACES",
    "AppRootResult",
    "JsonType",
    "OAuthClientPayload",
    "ResolvedVerbLeaf",
    "RootStatusResult",
    "SchemaResolutionError",
    "VerbInputSchema",
    "VerbLeafKind",
    "VerbLeafResolutionFailure",
    "VerbParamKind",
    "VerbParameter",
    "app",
    "assert_schema_coverage",
    "build_verb_input_schemas",
    "calculation_revision_lines",
    "calculation_revision_payload",
    "cli_argv_for",
    "cli_path_for_command_key",
    "command_execution_policy_for_cli_path",
    "command_schema_refs",
    "full_command_tree",
    "is_exposable_command",
    "main",
    "resolve_cli_precondition_action",
]
