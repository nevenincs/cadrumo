"""Owned support for lazy executable-root CLI handlers."""

from __future__ import annotations

import typer

from ...core.product_identity import PRODUCT_IDENTITY as _PRODUCT_IDENTITY
from ...core.cli_metadata import is_metadata_invocation as _is_metadata_invocation
from ...core.json_contract import strict_round_trip as _strict_round_trip
from ._command_specs import COMMAND_GRAPH as _COMMAND_GRAPH
from ._common import (
    active_profile_label,
    attach_cli_policy_verdict,
    emit_envelope,
    requested_cli_leaf,
)


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
    from ...application.operator_surface.help import build_help_document, render_help_text
    from ._root_payloads import RootStatusResult

    document = build_help_document("root")
    typed_help = _strict_round_trip(RootStatusResult, document)
    lines = render_help_text(document).splitlines()
    footer = lines.pop()
    lines.extend((*_root_profile_secret_help_lines(), "", *_root_tui_help_lines(), "", footer))
    emit_envelope(ctx, command="root.status", result=typed_help, lines=lines)
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


def _root_tui_help_lines() -> tuple[str, ...]:
    """Project the graph-owned global TUI request into curated root help."""
    from ...core.i18n import tr
    from ._command_spec import OptionSpec

    root = _COMMAND_GRAPH.by_key()["root"]
    option = next(
        parameter for parameter in root.parameters if isinstance(parameter, OptionSpec) and parameter.name == "tui"
    )
    if option.help_key is None:
        raise RuntimeError("the root TUI option lacks localised help")
    return (
        tr("cli.operator_surface.help.root.section_frontend_options"),
        f"  --tui  {tr(option.help_key.value)}",
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
        from .errors import CliRefusedBoundaryError

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
    from ...application.operator_surface.help import build_root_landing_report
    from ...application.workflow.profile_bucket_scan import list_profile_buckets
    from ...core.bucket_pointer import resolve_active_bucket_id
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
        emit_envelope(
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
    from ...application.overview.status_report import build_overview_status_report
    from ...application.workflow.persistence import workflow_state_repository

    workflow_state = workflow_state_repository().load()
    overview_report = build_overview_status_report(state=workflow_state)
    typed_overview = _strict_round_trip(RootStatusResult, overview_report)
    emit_envelope(ctx, command="root.status", result=typed_overview, lines=render_cli_root_landing_lines(landing))
    raise typer.Exit()


def _activate_profile_override(ctx: typer.Context, profile: str) -> None:
    """Resolve ``--profile`` to a bucket id and set the active-profile override.

    Resolves through the single application-layer name-or-UUID resolver so a
    ``--profile`` value may be either the operator display label or the UUID
    bucket id, then pins the override to the resolved UUID.
    """
    from ...application.profile_preconditions import ProfileSelectionFailure, profile_selection_failure_verdict
    from ...application.workflow.errors import ProfileLabelAmbiguousError
    from ...application.workflow.profile_bucket_scan import resolve_profile_bucket
    from ...core.config import override_settings
    from .errors import CliRefusedBoundaryError

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
    from ...application.workflow.errors import ProfileLabelAmbiguousError
    from ...application.workflow.profile_bucket_scan import resolve_profile_bucket
    from ...core.bucket_pointer import resolve_active_bucket_id
    from ...core.config import override_settings
    from ...core.errors.hierarchy import CadrumoError
    from .errors import CliRefusedBoundaryError

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
