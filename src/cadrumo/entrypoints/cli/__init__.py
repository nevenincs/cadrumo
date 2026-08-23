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
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, cast

import typer
from typer._click.core import Command as _TyCommand

if TYPE_CHECKING:
    # Type-checking-only: gives static consumers of the lazy `command_schema_refs`
    # re-export (below, via `__getattr__`) its real signature without paying the
    # eager registry-parse import cost at runtime -- this line never executes.
    from ._command_schema import command_schema_refs as command_schema_refs
    from ._command_schema import command_schema_type as command_schema_type
    from ._command_schema import command_schema_types as command_schema_types
    from ._command_spec import CommandSpec
    from ._config._google import OAuthClientPayload as OAuthClientPayload
    from ._modelo_rendering import calculation_revision_lines, calculation_revision_payload
    from ._verb_input_schema import cli_path_for_command_key as cli_path_for_command_key
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
from ...core import StorageCategory as _StorageCategory
from ...core import storage_location as _storage_location
from ...core.cli_metadata import is_metadata_invocation as _is_metadata_invocation
from ...core.json_contract import strict_round_trip as _strict_round_trip
from ...core.output_rendering import OutputFormat as _OutputFormat
from ._command_policy import CommandExecutionPolicy as _CommandExecutionPolicy
from ._command_runtime import build_command_app as _build_command_app
from ._command_specs import COMMAND_GRAPH as _COMMAND_GRAPH
from ._common import (
    _emit_envelope,
    active_profile_label,
    attach_cli_policy_verdict,
    preserve_requested_cli_leaf,
    requested_cli_leaf,
    resolve_cli_precondition_action,
)
from ._errors import decorate_typer_app as _decorate_typer_app
from ._framework_localisation import (
    localise_help_section_headers as _localise_help_section_headers,
)
from ._framework_localisation import (
    localise_typer_parse_error_messages as _localise_typer_parse_error_messages,
)
from ._language_argv import apply_language_argv_to_environment as _apply_language_argv_to_environment
from ._log_levels import resolve_log_level as _resolve_log_level

CommandExecutionPolicy = _CommandExecutionPolicy

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


def root_command(
    ctx: typer.Context,
    language: str | None = None,
    profile: str | None = None,
    profile_secrets_stdin: bool = False,
    profile_secrets_fd: int | None = None,
    version: bool = False,
    detail: bool = False,
    help_: bool = False,
    format_: _OutputFormat = _OutputFormat.TEXT,
    quiet: bool = False,
    verbose: bool = False,
    debug: bool = False,
) -> None:
    """Capture root-level CLI flags into the Typer context."""
    if language is not None:
        from ...core.config import override_settings

        ctx.with_resource(override_settings(cadrumo_output_language=language))
    state = cast("dict[str, object]", ctx.ensure_object(dict))
    state["format"] = format_
    state["log_level"] = _resolve_log_level(quiet=quiet, verbose=verbose, debug=debug)
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
    state["profile_override"] = profile
    if ctx.invoked_subcommand is None:
        if profile is not None:
            _activate_profile_override(ctx, profile)
        else:
            _normalize_root_active_profile(ctx)
        _emit_bare_invocation_and_exit(ctx)
    from ._profile_authentication_contract import ProfileSecretSourceOptions

    state["profile_secret_source"] = ProfileSecretSourceOptions(
        stdin=profile_secrets_stdin,
        descriptor=profile_secrets_fd,
    )
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
    # Activate the bucket session here so verbs that need it have access to
    # the active profile's encrypted records. Deferred after the
    # bare-invocation path for the same reason as above. Help and usage-error
    # renderings are introspection surfaces too: they must never require the
    # profile session, or a newcomer without an explicit authentication act
    # cannot browse the command tree and an unknown-command typo is masked by a
    # master-key refusal instead of the usage error.
    # Session activation runs from the graph-generated leaf wrapper after the
    # complete command has parsed, so root and leaf secret sources can be
    # preflighted together before either is consumed.


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
    from ._root_payloads import RootStatusResult

    document = build_help_document("root")
    typed_help = _strict_round_trip(RootStatusResult, document)
    lines = render_help_text(document).splitlines()
    footer = lines.pop()
    lines.extend((*_root_profile_secret_help_lines(), "", footer))
    _emit_envelope(ctx, command="root.status", result=typed_help, lines=lines)
    raise typer.Exit()


def _root_profile_secret_help_lines() -> tuple[str, ...]:
    """Project graph-owned root profile-secret options into curated help."""
    from ...core.i18n import tr
    from ._command_spec import OptionSpec

    root = _COMMAND_GRAPH.by_key()["root"]
    options = tuple(
        parameter
        for parameter in root.parameters
        if isinstance(parameter, OptionSpec) and parameter.profile_secret_channel is not None
    )
    if len(options) != 2:
        raise RuntimeError("root help requires exactly two profile-secret channel options")
    rendered: list[tuple[str, str]] = []
    for option in options:
        declaration = option.declarations[0]
        if not option.is_flag:
            declaration = f"{declaration} FD"
        if option.help_key is None:
            raise RuntimeError("a root profile-secret option lacks localised help")
        rendered.append((declaration, tr(option.help_key.value)))
    width = max(len(declaration) for declaration, _ in rendered)
    return (
        tr(
            "cli.operator_surface.help.root.section_profile_authentication_options",
            default="Profile authentication options",
        ),
        *(f"  {declaration.ljust(width)}  {description}" for declaration, description in rendered),
    )


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
    if not is_bootstrap_exempt(verb_path):
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
    from ._root_payloads import RootStatusResult

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








def _is_introspection_only_invocation(ctx: typer.Context) -> bool:
    """Return whether the invocation can only render help or a usage error.

    Two introspection shapes never execute a verb body and therefore must
    not open the encrypted bucket session (which demands the master key and,
    without an explicit root profile-authentication source on non-interactive
    stdin, refuses):

    - A help request: a ``--help`` / ``-h`` token anywhere in the unparsed
      remainder. Click's eager help callback (or the curated subgroup help
      in the group callbacks) aborts before any verb body runs.
    - An unresolvable command chain: the leading non-option tokens do not
      name a graph-materialized command, so click can only emit the usage error.
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
    # Walk leading command tokens through the sealed graph. The graph's typed
    # terminal behavior—not Click group shape—decides whether a bare group is
    # state-free; executable groups must continue into parsed preflight.
    tokens: list[str] = []
    for token in remainder:
        if token.startswith("-"):
            break
        tokens.append(token)
    if not tokens:
        return False
    path = ["aeat"]
    spec = _COMMAND_GRAPH.resolve_path(tuple(path))
    for token in tokens:
        if spec.kind == "leaf" or spec.invocation.terminal_behavior == "executable":
            # Remaining non-option tokens are parsed positional arguments, not
            # command identities. The executable node owns their validation.
            return False
        path.append(token)
        try:
            spec = _COMMAND_GRAPH.resolve_path(tuple(path))
        except LookupError:
            return True
    return spec.kind == "group" and spec.invocation.terminal_behavior == "introspection"


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


def app_root(ctx: typer.Context, help_: bool = False) -> None:
    """Render app-level workflow help when requested."""
    if help_ or ctx.invoked_subcommand is None:
        from ...application.operator_surface import build_help_document, render_help_text
        from ._root_payloads import AppRootResult

        document = build_help_document("app")
        typed_app = _strict_round_trip(AppRootResult, document)
        _emit_envelope(ctx, command="root.app", result=typed_app, lines=render_help_text(document).splitlines())
        raise typer.Exit()


app = _build_command_app(_COMMAND_GRAPH)
_decorate_typer_app(app)


def full_command_tree() -> _TyCommand:
    """Materialise the immutable production command graph as a Click tree."""
    from typer.main import get_command

    root = get_command(app)
    root.name = app.info.name or _PRODUCT_IDENTITY.cli_executable
    return root


def _declared_execution_policy_for_cli_path(
    cli_path: tuple[str, ...],
) -> _CommandExecutionPolicy:
    declared = _COMMAND_GRAPH.resolve_path((_PRODUCT_IDENTITY.cli_executable, *cli_path))
    return _execution_policy_from_spec(declared)


def _execution_policy_from_spec(spec: CommandSpec) -> _CommandExecutionPolicy:
    from ._command_schema import CommandCapabilityClass

    declared = spec.policy
    return _CommandExecutionPolicy(
        classification=CommandCapabilityClass(
            declared.capabilities,
            declared.side_effects,
            declared.performance,
        ),
        write_route=declared.write_route,
        destructive=declared.destructive,
        handoff=declared.handoff,
        live_write=declared.live_write,
    )


def command_execution_policy_for_cli_path(
    cli_path: tuple[str, ...],
) -> _CommandExecutionPolicy:
    """Return CommandSpec-owned policy for one live path.

    The concrete policy type remains owned by the CLI command graph. This
    facade keeps cross-distribution consumers on the public entrypoint boundary
    without importing the complete command tree.
    """
    return _declared_execution_policy_for_cli_path(cli_path)


def command_search_terms(command_key: str) -> tuple[str, ...]:
    """Return spec-authored semantic search terms for one command key."""
    spec = _COMMAND_GRAPH.by_schema_identity().get(command_key) or _COMMAND_GRAPH.by_key().get(command_key)
    if spec is None:
        raise LookupError(f"unknown command key: {command_key!r}")
    return spec.search_terms


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
    if name in {"command_schema_refs", "command_schema_type", "command_schema_types"}:
        from . import _command_schema

        return getattr(_command_schema, name)
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
    "CommandExecutionPolicy",
    "JsonType",
    "OAuthClientPayload",
    "ResolvedVerbLeaf",
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
    "command_schema_type",
    "command_schema_types",
    "command_search_terms",
    "is_exposable_command",
    "main",
    "resolve_cli_precondition_action",
]
