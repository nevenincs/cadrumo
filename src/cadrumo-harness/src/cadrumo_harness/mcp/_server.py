"""MCP server shell: the thin protocol wiring over the SDK-independent core.

The Model Context Protocol runtime is provided by the sibling
``cadrumo-harness`` distribution. :func:`serve` imports it lazily and, when it is absent,
refuses with the install hint and a non-zero exit instead of raising a raw
``ModuleNotFoundError`` - the same graceful-degradation contract the Google,
browser, and Anthropic integrations follow. The tool list, annotations, and the
forbidden-live-write block are sourced from the SDK-independent core in this
package; ``call_tool`` runs the deterministic CLI - warm in-process for local
verbs, a supervised subprocess for the AEAT-sede family (``_run_tool``) - and
returns its JSON envelope as structured content. Alongside the per-verb tools the server
advertises the ``search`` / ``execute`` meta-tools and the ``harness.load`` floor
tool (the universal operating-layer channel), and serves the operating
layer through real ``resources`` handlers - the concrete ``cadrumo://`` skill / rule
/ persona set, the three ``cadrumo://<kind>/{name}`` templates, and a ``read``
resolver - and through real ``prompts`` handlers: the guided-workflow catalogue
and each prompt's embedded skill / rules, derived from ``_prompts.py``.
:func:`build_server` owns that registration and is unit-tested against the real
SDK without the stdio transport.

The server also enforces the
persona-scoped tool boundary declared in ``_persona_scope.py``:
:func:`serve` resolves the active persona once, at startup, from the
``CADRUMO_MCP_PERSONA`` environment variable via
:func:`~cadrumo_harness.mcp._persona_scope.active_persona`. When a persona is
active, ``_list_tools`` advertises only that persona's in-scope tools
(:func:`filter_descriptors_for_persona`) and ``_call_tool`` refuses an
out-of-scope call (:func:`persona_scope_refusal`) before the global HITL
``confirmation_for_tool`` gate runs. An unset/blank env var preserves the
full, unscoped tool surface for any un-personified session. See
``_persona_scope.py``'s module docstring for the known
family-granularity limitation (the three modelo-lifecycle personas share one
manifest family and are not distinguished by this gate).
"""

from __future__ import annotations

import atexit
import contextlib
import json
import os
import sys
import time
import uuid
from functools import partial
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as distribution_version
from pathlib import Path
from typing import TYPE_CHECKING

from cadrumo.adapters.persistence.storage import close_all_live_bucket_sessions
from cadrumo.application.wizard.compiler import ensure_profile_keys_registered
from cadrumo.core import PRODUCT_IDENTITY, FormerProductStateError

from ._call_runtime import serving_capacity_limiter
from ._completions import complete_prompt_argument
from ._corpus_tools import (
    CORPUS_SEARCH_TOOL,
    build_corpus_search_payload,
    build_corpus_search_tool,
    render_corpus_search_text,
)
from ._dispatch import command_key_for_tool
from ._elicitation import (
    ConfirmDecision,
    ConfirmRoute,
    confirmation_request,
    decision_from_elicitation,
    refusal_message,
    resolve_confirm_route,
)
from ._faithfulness import SessionGroundingWindow, advisory_line, arguments_faithfulness
from ._harness_tools import (
    HARNESS_LOAD_TOOL,
    WHOAMI_TOOL,
    build_harness_floor_payload,
    build_harness_floor_tool,
    build_whoami_identity,
    build_whoami_tool,
    render_harness_floor_text,
    render_whoami_identity_text,
)
from ._hitl import (
    REQUIRES_USER_INTERACTION_META_KEY,
    confirmation_for_policy,
    is_handoff_command,
    requires_user_interaction,
)
from ._identity_gate import (
    IDENTITY_READ_CONSOLE_TOOLS,
    SessionIdentityState,
    identity_elicitation_echo,
    identity_gate_refusal,
)
from ._meta_tools import (
    ToolRunner,
    ToolRunOutcome,
    build_capability_manifest,
    build_command_search_index,
    describe_command,
    gate_refusal,
    manage_toolsets,
    meta_execute,
    search_commands_response,
)
from ._persona_scope import (
    AgentPersona,
    active_persona,
    is_handoff_denied,
    is_tool_in_persona_scope,
)
from ._prompts import PromptNotFoundError, build_prompt_catalogue, prompt_document
from ._resources import (
    BUCKET_SCOPED_RESOURCE_KINDS,
    HarnessResourceKind,
    HarnessResourceNotFoundError,
    list_harness_resource_templates,
    list_harness_resources,
    parse_resource_uri,
    read_harness_resource,
    resource_mime_type,
)
from ._result_thinning import BULK_RESOLUTION, ResourceLinkRef, thin_envelope
from ._stdio_lifetime import (
    arm_stdio_lifetime_watchdog,
    disarm_stdio_lifetime_watchdog,
    register_pre_exit_hook,
)
from ._surface import (
    SURFACE_ENV_VAR,
    SurfaceMode,
    advertised_descriptors,
    resolve_surface_mode,
)
from ._telemetry import SessionTelemetryWriter
from ._terminology_tools import (
    TERMINOLOGY_SEARCH_TOOL,
    build_terminology_search_payload,
    build_terminology_search_tool,
    render_terminology_search_text,
)
from ._tools import McpToolDescriptor, build_tool_descriptors
from ._toolsets import Toolset, command_keys_for_toolsets
from ._transport import (
    SubprocessToolOutcome,
    _run_subprocess_tool,
    _run_tool,
)

if TYPE_CHECKING:
    # Typing-only: the MCP SDK is supplied by the sibling harness distribution,
    # so every real import of it is deferred to inside a function body (see the
    # module docstring). These names are never evaluated at runtime (deferred
    # annotations, `from __future__ import annotations`); they exist solely so
    # the standalone (non-nested) functions below can declare their true SDK
    # return/parameter types instead of the placeholder ``object``.
    from collections.abc import Callable

    from mcp.server import Server
    from mcp.server.context import ServerRequestContext
    from mcp.server.models import InitializationOptions
    from mcp.types import ContentBlock, Tool

_INSTALL_HINT = (
    "the MCP server is provided by the cadrumo-harness distribution: "
    "pip install cadrumo-harness; launch it with cadrumo-mcp"
)
_REQUIRED_VERSION_ENV = f"{PRODUCT_IDENTITY.environment_prefix}MCP_REQUIRED_VERSION"
_RUNTIME_COHORT = (PRODUCT_IDENTITY.distribution, *PRODUCT_IDENTITY.companion_distributions)

# The capability-manifest meta-tool: emits the operator-surface manifest - roots,
# mounted command families with their intent and mutability, lifecycle ordering,
# and registered result schemas - that the operator rules mandate reading first.
# It is MCP-native (composed from the application manifest builder and the CLI's
# schema refs), not a projection of any CLI verb, so it carries no command key and
# no mounted family of its own.
_META_CONTRACT_TOOL = "contract"
# The two meta-tools that reach the long-tail verb surface outside the curated
# toolsets. They are advertised alongside the per-verb tools and are never
# persona-scoped away (``execute`` applies the persona gate internally).
_META_SEARCH_TOOL = "search"
_META_EXECUTE_TOOL = "execute"
# The toolset-activation meta-tool: activating
# a domain toolset adds its per-verb tools to the advertised surface (within the
# active persona's scope) and emits tools/list_changed for clients that honour it.
_META_TOOLSETS_TOOL = "toolsets"
# The per-command descriptor meta-tool:
# returns one command's full shape by key - schema, annotations, confirmation
# tier, CommandSpec-owned policy, owning toolset, and reachable personas - so a model can
# inspect a verb fully before spending an ``execute`` round-trip on it.
_META_DESCRIBE_TOOL = "describe"


def emit_missing_sdk_refusal() -> None:
    """Write the harness-distribution install hint to stderr and exit non-zero.

    The graceful-degradation path taken when the MCP SDK is absent. Exposed so the
    refusal contract is unit-tested directly, in any environment, rather than
    relying on the SDK being absent at test time.
    """
    sys.stderr.write(_INSTALL_HINT + "\n")
    raise SystemExit(3)


def enforce_required_runtime_cohort() -> None:
    """Refuse when a plugin requires a different or incomplete installed cohort.

    Direct standalone use leaves ``CADRUMO_MCP_REQUIRED_VERSION`` unset and is
    unaffected. Distribution integrations set it to their own release version,
    binding the client surface to one complete installed root-plus-data cohort.
    """
    required = os.environ.get(_REQUIRED_VERSION_ENV, "").strip()
    if not required:
        return

    observed, missing = _observe_runtime_cohort()
    mismatched = {name: installed for name, installed in observed.items() if installed != required}
    if not missing and not mismatched:
        return

    details = _cohort_mismatch_details(missing, mismatched)
    sys.stderr.write(
        "Cadrumo MCP runtime cohort does not satisfy the installed integration: "
        f"required {required}; {'; '.join(details)}. "
        "Install the exact runtime cohort: "
        f"pip install cadrumo-harness=={required} cadrumo=={required} "
        f"cadrumo-data-manuals=={required} cadrumo-data-official=={required}\n",
    )
    raise SystemExit(4)


def _observe_runtime_cohort() -> tuple[dict[str, str], list[str]]:
    """Return the installed version per cohort member and the list of absent members."""
    observed: dict[str, str] = {}
    missing: list[str] = []
    for distribution in _RUNTIME_COHORT:
        try:
            observed[distribution] = distribution_version(distribution)
        except PackageNotFoundError:
            missing.append(distribution)
    return observed, missing


def _cohort_mismatch_details(missing: list[str], mismatched: dict[str, str]) -> list[str]:
    """Render the ``missing:`` / ``version mismatch:`` detail fragments for the refusal."""
    details: list[str] = []
    if missing:
        details.append(f"missing: {', '.join(missing)}")
    if mismatched:
        rendered = ", ".join(f"{name}={installed}" for name, installed in sorted(mismatched.items()))
        details.append(f"version mismatch: {rendered}")
    return details


def serve(*, profile_secrets_file: Path | None = None) -> None:
    """Run the ``cadrumo-mcp`` stdio server, or refuse if the SDK is not installed.

    Resolves the active persona from ``CADRUMO_MCP_PERSONA`` before touching the
    SDK, so an invalid persona value fails with the instructive
    :func:`~cadrumo_harness.mcp._persona_scope.active_persona` error
    regardless of whether the optional SDK is installed.
    """
    from ._profile_secret_channel import clear_profile_secret, load_profile_secret_file

    enforce_required_runtime_cohort()
    if profile_secrets_file is not None:
        load_profile_secret_file(profile_secrets_file)
    persona = active_persona()
    surface_mode = resolve_surface_mode(os.environ.get(SURFACE_ENV_VAR))
    try:
        import mcp.server  # noqa: F401
    except ModuleNotFoundError:
        emit_missing_sdk_refusal()
        return
    try:
        _run_server(build_tool_descriptors(), persona=persona, surface_mode=surface_mode)
    finally:
        clear_profile_secret()


def filter_descriptors_for_persona(
    descriptors: tuple[McpToolDescriptor, ...],
    *,
    persona: AgentPersona | None,
) -> tuple[McpToolDescriptor, ...]:
    """Narrow ``descriptors`` to the tools in ``persona``'s live-manifest scope.

    ``persona=None`` (no active persona) returns ``descriptors`` unchanged -
    the full, unscoped surface. This is the ``_list_tools``-side half of D1;
    it is SDK-independent and pure so it is unit-tested directly.

    Returns:
        The subset of :class:`McpToolDescriptor` entries in scope for
        *persona*.
    """
    if persona is None:
        return descriptors
    return tuple(
        descriptor
        for descriptor in descriptors
        if is_tool_in_persona_scope(persona=persona, command_key=descriptor.command_key)
    )


def persona_scope_refusal(*, persona: AgentPersona | None, command_key: str) -> str | None:
    """Return a refusal message when ``command_key`` is outside ``persona``'s scope.

    Returns ``None`` when the call may proceed to the global HITL gate: either
    no persona is active, or the command is in the active persona's declared
    scope. This is the ``_call_tool``-side half of D1; it runs BEFORE
    :func:`~cadrumo_harness.mcp._hitl.confirmation_for_tool` so an
    out-of-scope call is refused before HITL policy is even consulted.
    """
    if persona is None:
        return None
    if is_tool_in_persona_scope(persona=persona, command_key=command_key):
        return None
    return f"refused: {command_key!r} is outside the active persona {persona.value!r}'s tool scope"


def build_sdk_tools(descriptors: tuple[McpToolDescriptor, ...]) -> list[Tool]:
    """Adapt the SDK-independent descriptors into MCP SDK ``Tool`` objects.

    Lazily imports the SDK types so the module still imports (and ``serve`` still
    refuses gracefully) when the harness distribution's MCP runtime is absent. Exposed at module
    level so the adaptation - including the mutability-to-annotation projection -
    is unit-tested against the real SDK types when they are installed.
    """
    from mcp.types import Tool, ToolAnnotations

    tools: list[Tool] = []
    for descriptor in descriptors:
        annotations = descriptor.annotations
        # Advertise the CONFIRM tier to the client as the Anthropic-namespaced
        # ``_meta`` interaction flag, derived from the same confirmation gate the
        # server's PreToolUse path enforces, so a tool that would be confirmed
        # server-side also forces the client's permission prompt. Non-CONFIRM tools
        # carry no ``_meta`` (``None`` omits it from the wire descriptor).
        policy = confirmation_for_policy(descriptor.execution_policy)
        meta = {REQUIRES_USER_INTERACTION_META_KEY: True} if requires_user_interaction(policy) else None
        tools.append(
            Tool(
                name=descriptor.name,
                description=descriptor.description,
                input_schema=descriptor.input_schema,
                output_schema=descriptor.output_schema,
                annotations=ToolAnnotations(
                    title=annotations.title,
                    read_only_hint=annotations.read_only_hint,
                    destructive_hint=annotations.destructive_hint,
                    idempotent_hint=annotations.idempotent_hint,
                    open_world_hint=annotations.open_world_hint,
                ),
                _meta=meta,
            ),
        )
    return tools


def build_meta_sdk_tools() -> list[Tool]:
    """Build the SDK ``Tool`` objects for the core-surface meta-tools.

    Lazily imports the SDK ``Tool`` type so the module still imports when the
    harness distribution's MCP runtime is absent. Exposed at module level so the meta-tool
    surface is unit-tested against the real SDK types when they are installed.

    Returns:
        The ``contract``, ``search``, ``execute``, ``toolsets``, and ``describe``
        :class:`mcp.types.Tool` objects.
    """
    from mcp.types import Tool, ToolAnnotations

    return [
        Tool(
            name=_META_CONTRACT_TOOL,
            description=(
                "Return the Cadrumo capability manifest: the accepted command roots, every mounted "
                "command family with the operator question it answers and its mutability, the filing "
                "lifecycle ordering, and the registered per-command result schemas. Read this first to "
                "orient, then use search and describe to reach an individual verb."
            ),
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            annotations=ToolAnnotations(
                title="contract",
                read_only_hint=True,
                destructive_hint=False,
                idempotent_hint=True,
                open_world_hint=False,
            ),
        ),
        Tool(
            name=_META_SEARCH_TOOL,
            description=(
                "Search Cadrumo commands by keyword; returns matching command keys with mutability hints. "
                "Pass a hit to describe for its full schema before you run it, or activate a toolset to "
                "advertise a whole domain's verbs directly."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keywords to match against command names and descriptions.",
                    }
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        ),
        Tool(
            name=_META_EXECUTE_TOOL,
            description=(
                "Execute one Cadrumo command by key with named arguments, through the same safety gates. "
                "Call describe first to read the command's full input schema before you build the arguments."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "command_key": {
                        "type": "string",
                        "description": "The registry command key to run, e.g. modelo.work.calculate.",
                    },
                    "arguments": {"type": "object", "description": "The named arguments for the command."},
                },
                "required": ["command_key"],
                "additionalProperties": False,
            },
        ),
        Tool(
            name=_META_TOOLSETS_TOOL,
            description=(
                "Manage domain toolsets: list them, or activate/deactivate one to add or remove its "
                "per-verb tools from the advertised tool list (renta, iva, ledger, censo, modelo-lifecycle). "
                "Activate a toolset when you will do repeated work in that domain, so its verbs are advertised "
                "directly instead of reached one at a time through search and execute."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "activate", "deactivate"],
                        "description": "list the toolsets, or activate/deactivate one by name.",
                    },
                    "name": {
                        "type": "string",
                        "description": "The toolset to activate/deactivate (omit for list).",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        ),
        Tool(
            name=_META_DESCRIBE_TOOL,
            description=(
                "Return one Cadrumo command's full descriptor by key: schema, annotations, confirmation "
                "tier, risk, owning toolset, and which personas may call it."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "command_key": {
                        "type": "string",
                        "description": "The registry command key to describe, e.g. modelo.export.",
                    }
                },
                "required": ["command_key"],
                "additionalProperties": False,
            },
        ),
    ]


def _tool_arg_limit(value: object, default: int) -> int:
    """Coerce an MCP JSON-RPC ``limit`` argument to an ``int``, mirroring ``int(value or default)``.

    ``arguments`` is a ``dict[str, object]`` decoded from the client's JSON-RPC
    call, so a supplied ``limit`` is typed ``object`` even though JSON-RPC only
    ever carries an ``int``, ``float``, or ``str`` numeric literal here. Narrows
    to those shapes before calling :func:`int`; a falsy or unrecognised value
    falls back to ``default``, exactly as the prior ``int(value or default)``
    expression did.
    """
    if isinstance(value, int | float | str) and value:
        return int(value)
    return default


def _declined_message(*, command_key: str, decision: ConfirmDecision) -> str:
    """The client-relayed, localized text for a not-confirmed call."""
    from cadrumo.core.i18n import tr

    return tr(
        "mcp.elicitation.confirm.declined",
        command=command_key,
        outcome=decision.value,
        default="'{command}' was not confirmed by the user ({outcome}); nothing was run.",
    )


def _client_supports_elicitation(ctx: ServerRequestContext) -> bool:
    """Read the negotiated client capabilities for elicitation support (fail-closed).

    ``ctx.session.client_capabilities`` is ``None`` when the client declared no
    capabilities at all; a missing or absent elicitation entry both read as
    unsupported, so the degradation matrix falls back to the safe routes.
    """
    capabilities = ctx.session.client_capabilities
    return bool(capabilities is not None and capabilities.elicitation is not None)


def _record_telemetry(
    telemetry: SessionTelemetryWriter | None,
    *,
    tool_name: str,
    command_key: str = "",
    route: str = "",
    transport: str = "",
    is_error: bool = False,
    duration_ms: int = 0,
    executable_text: str = "",
    arguments_text: str = "",
    result_text: str = "",
) -> None:
    """Forward to the optional telemetry sink, mirroring its signature exactly."""
    if telemetry is not None:
        telemetry.record(
            tool_name=tool_name,
            command_key=command_key,
            route=route,
            transport=transport,
            is_error=is_error,
            duration_ms=duration_ms,
            executable_text=executable_text,
            arguments_text=arguments_text,
            result_text=result_text,
        )


def _refused_tool_outcome(refusal: str) -> ToolRunOutcome:
    """Return the common typed error outcome for a refused dispatch."""
    return ToolRunOutcome(envelope={"status": "error", "refusal": refusal}, is_error=True)


def _meta_execute_call_outcome(
    arguments: dict[str, object],
    *,
    descriptors: tuple[McpToolDescriptor, ...],
    persona: AgentPersona | None,
    run: ToolRunner,
) -> tuple[str | None, dict[str, object], dict[str, object], tuple[ResourceLinkRef, ...], bool]:
    """Run and thin one meta-execute call without depending on MCP SDK result types."""
    raw_args = arguments.get("arguments", {})
    exec_args = dict(raw_args) if isinstance(raw_args, dict) else {}
    command_key = str(arguments.get("command_key", "") or "")
    outcome = meta_execute(command_key, exec_args, descriptors=descriptors, persona=persona, run=run)
    if outcome.refused is not None:
        return outcome.refused, {}, {}, (), True
    envelope = outcome.envelope or {}
    thinned_envelope, links = thin_envelope(command_key, envelope)
    return None, envelope, thinned_envelope, links, outcome.is_error


async def _run_offloop_with_progress[T](
    ctx: ServerRequestContext,
    work: Callable[[], T],
) -> T:
    """Run blocking subprocess work off the event loop, heart-beating progress.

    The supervised call blocks (Popen.communicate); a worker thread keeps
    pings, concurrent calls, and cancellation flowing on direct and ``execute``
    paths. When the client supplied a progress token, an elapsed-seconds
    heartbeat is sent every few seconds until the call completes, so a slow
    pull looks alive rather than hung; a client that sent no token still gets
    the off-loop run.
    """
    import anyio
    from anyio.to_thread import run_sync

    limiter = serving_capacity_limiter()
    progress_token = ctx.meta.get("progress_token") if ctx.meta is not None else None

    if progress_token is None:
        return await run_sync(work, limiter=limiter)

    holder: dict[str, T] = {}

    async def _work() -> None:
        holder["result"] = await run_sync(work, limiter=limiter)
        task_group.cancel_scope.cancel()

    async def _heartbeat() -> None:
        elapsed = 0
        while True:
            await anyio.sleep(5)
            elapsed += 5
            with contextlib.suppress(Exception):
                await ctx.session.send_progress_notification(
                    progress_token=progress_token,
                    progress=float(elapsed),
                    total=None,
                )

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(_heartbeat)
        task_group.start_soon(_work)
    return holder["result"]


def build_server(
    descriptors: tuple[McpToolDescriptor, ...],
    *,
    persona: AgentPersona | None = None,
    telemetry: SessionTelemetryWriter | None = None,
    surface_mode: SurfaceMode = SurfaceMode.CORE,
) -> Server:
    """Build the MCP ``Server`` with the tool, prompt, and resource handlers.

    Registers the persona-scoped per-verb tools plus the ``search`` / ``execute``
    meta-tools and the ``harness.load`` floor tool, and the operating-layer
    ``prompts`` and ``resources`` handlers so the server advertises those
    capabilities during negotiation. Extracted from the stdio runner so the
    handler registration and capability negotiation are unit-tested against the
    real SDK. ``persona`` scopes the per-verb tool list and the direct call-tool
    refusal per D1; the meta-tools and the floor tool are always advertised and
    ``execute`` applies the persona gate internally.

    Seeds the process-global profile-key registry through
    :func:`~application.wizard.compiler.ensure_profile_keys_registered` before any
    handler is registered. This is the server's initialisation point, the
    counterpart of the CLI root callback's own registration step: the domain
    registry cannot seed itself and every production reader of it sits
    behind a handler built here, so a host that never seeded it answered every
    identity call with a registration error.

    Returns:
        The configured :class:`mcp.server.Server`.
    """
    ensure_profile_keys_registered()

    from mcp.server import Server
    from mcp.types import (
        CallToolRequestParams,
        CallToolResult,
        CompleteRequestParams,
        CompleteResult,
        Completion,
        EmbeddedResource,
        GetPromptRequestParams,
        GetPromptResult,
        ListPromptsResult,
        ListResourcesResult,
        ListResourceTemplatesResult,
        ListToolsResult,
        PaginatedRequestParams,
        Prompt,
        PromptArgument,
        PromptMessage,
        PromptReference,
        ReadResourceRequestParams,
        ReadResourceResult,
        Resource,
        ResourceLink,
        ResourceTemplate,
        TextContent,
        TextResourceContents,
    )

    def _resource_links(refs: tuple[ResourceLinkRef, ...]) -> list[ResourceLink]:
        """Adapt the thinning ``ResourceLinkRef`` set onto SDK ``resource_link`` items."""
        return [
            ResourceLink(
                type="resource_link",
                uri=ref.uri,
                name=ref.name,
                description=ref.description,
                mime_type=ref.mime_type,
            )
            for ref in refs
        ]

    scoped_descriptors = tuple(
        descriptor
        for descriptor in filter_descriptors_for_persona(descriptors, persona=persona)
        if persona is None
        or not is_handoff_denied(
            persona=persona,
            command_key=descriptor.command_key,
            execution_policy=descriptor.execution_policy,
        )
    )
    by_name = {descriptor.name: descriptor for descriptor in descriptors}
    # command-key -> descriptor: the resource read handler resolves a bulk
    # resource by re-running its owning read verb's descriptor as a
    # supervised subprocess (which carries the active bucket session the server
    # process lacks), then returns that verb's bulk field.
    by_command_key = {descriptor.command_key: descriptor for descriptor in descriptors}
    # The advertised per-verb surface: CORE (default) advertises only the
    # persona-scoped orientation slice up front; FULL advertises the whole
    # persona-scoped set (the previous flat surface). ``by_name`` above still
    # spans EVERY descriptor, so a verb outside the advertised surface stays
    # reachable through the ``execute`` meta-tool and a direct call by name -
    # it is discovered, not listed.
    meta_tools = build_meta_sdk_tools()
    # The lexical command-search index backing the ``search`` meta-tool, built
    # once over the FULL descriptor set so discovery reaches every verb, not
    # only the advertised surface.
    command_index = build_command_search_index(descriptors)
    # Per-session toolset activation state. The advertised surface is the
    # orientation core PLUS the persona-scoped verbs of any active toolset;
    # activating a toolset emits ``tools/list_changed``.
    active_toolsets: set[Toolset] = set()

    def _advertised_tools() -> list[Tool]:
        advertised = advertised_descriptors(scoped_descriptors, mode=surface_mode)
        advertised_keys = {descriptor.command_key for descriptor in advertised}
        active_keys = command_keys_for_toolsets(frozenset(active_toolsets))
        activated = tuple(
            descriptor
            for descriptor in scoped_descriptors
            if descriptor.command_key in active_keys and descriptor.command_key not in advertised_keys
        )
        return build_sdk_tools((*advertised, *activated))

    floor_tool = build_harness_floor_tool()
    # Identity tool: the always-on read-only ``whoami`` that reports the
    # active taxpayer. Like the floor and grounding tools it is a console tool,
    # advertised on every session and never persona-scoped away, so an agent can
    # always confirm WHO is active before a mutating command.
    whoami_tool = build_whoami_tool()
    # Grounding tools: read-only search over the bundled legal corpus
    # and the taxpayer-facing terminology handbook. Always advertised (never
    # persona-scoped away) — every persona benefits from grounding its narration
    # in authoritative text, and neither tool mutates state.
    grounding_tools = [build_corpus_search_tool(), build_terminology_search_tool()]

    # Per-session serving-path gates and telemetry accumulate tool-result JSON in memory
    # only; the telemetry writer (injected by the stdio runner; None in unit
    # builds) records payload-free per-call rows.
    window = SessionGroundingWindow()
    # Per-session identity-read state: armed until an identity read has
    # occurred, re-armed on a profile switch. Shared by the direct and execute
    # paths below so the block-first-mutation gate is byte-identical on both.
    identity_state = SessionIdentityState()

    def _gated_subprocess_run(
        descriptor: McpToolDescriptor,
        arguments: dict[str, object],
    ) -> ToolRunOutcome:
        """The sync gate suite shared by the meta-execute path.

        A sync callable cannot elicit, so the degradation matrix runs with
        ``client_supports_elicitation=False``: handoff-tier CONFIRM refuses
        (fail-closed), non-handoff CONFIRM proceeds under the client's
        annotation-driven confirmation. Faithfulness and telemetry match the
        direct path. The dispatch transport - warm in-process for local verbs,
        supervised subprocess for the AEAT-sede family - is chosen by
        :func:`_run_tool`, so meta-execute and the direct path share it.
        """
        key = descriptor.command_key
        identity_refusal = identity_gate_refusal(
            key, execution_policy=descriptor.execution_policy, state=identity_state
        )
        if identity_refusal is not None:
            _record_telemetry(
                telemetry, tool_name=descriptor.name, command_key=key, route="identity_block", is_error=True
            )
            return _refused_tool_outcome(identity_refusal)
        policy = confirmation_for_policy(descriptor.execution_policy)
        route = resolve_confirm_route(
            policy=policy,
            command_key=key,
            execution_policy=descriptor.execution_policy,
            client_supports_elicitation=False,
        )
        if route in (ConfirmRoute.REFUSE_BLOCKED, ConfirmRoute.REFUSE_NO_CHANNEL):
            _record_telemetry(telemetry, tool_name=descriptor.name, command_key=key, route=route.value, is_error=True)
            return _refused_tool_outcome(refusal_message(route, command_key=key))
        arguments_json = json.dumps(arguments, ensure_ascii=False, sort_keys=True)
        faith = arguments_faithfulness(
            arguments_json=arguments_json,
            window=window,
            blocking=is_handoff_command(descriptor.execution_policy),
        )
        if faith.blocks:
            _record_telemetry(
                telemetry,
                tool_name=descriptor.name,
                command_key=key,
                route="faithfulness_block",
                is_error=True,
                arguments_text=arguments_json,
            )
            return _refused_tool_outcome(advisory_line(faith))
        started = time.monotonic()
        outcome = _run_tool(descriptor, arguments)
        envelope = outcome.envelope
        is_error = outcome.is_error
        envelope_json = json.dumps(envelope, ensure_ascii=False, sort_keys=True)
        window.record(envelope_json)
        _record_telemetry(
            telemetry,
            tool_name=descriptor.name,
            command_key=key,
            route=route.value,
            transport=outcome.transport.value,
            is_error=is_error,
            duration_ms=int((time.monotonic() - started) * 1000),
            executable_text=outcome.executable,
            arguments_text=arguments_json,
            result_text=envelope_json,
        )
        return ToolRunOutcome(envelope=envelope, is_error=is_error)

    async def _run_tool_with_progress(
        ctx: ServerRequestContext,
        descriptor: McpToolDescriptor,
        arguments: dict[str, object],
    ) -> SubprocessToolOutcome:
        """Run one direct per-verb call through the shared off-loop wrapper.

        The transport (warm in-process for local verbs, supervised subprocess for
        the AEAT-sede family) is chosen by :func:`_run_tool`; either way the
        blocking work runs off the event loop so the session keeps serving.
        """
        return await _run_offloop_with_progress(
            ctx,
            partial(_run_tool, descriptor, arguments),
        )

    async def _on_list_tools(_ctx: ServerRequestContext, _params: PaginatedRequestParams | None) -> ListToolsResult:
        # The harness.load floor tool is advertised first and is never persona-scoped
        # away: it is the universal operating-layer channel that must reach
        # any client, including a minimal tools-only one. The whoami identity tool and
        # the grounding tools follow for the same always-available reason:
        # an agent must always be able to confirm the active taxpayer and ground its
        # narration, whatever the persona. The per-verb surface is the orientation core
        # plus any active toolset (rebuilt per call so a toolset activation is
        # reflected).
        return ListToolsResult(tools=[floor_tool, whoami_tool, *grounding_tools, *_advertised_tools(), *meta_tools])

    async def _on_call_tool(ctx: ServerRequestContext, params: CallToolRequestParams) -> CallToolResult:
        name = params.name
        arguments = dict(params.arguments) if params.arguments else {}
        # A console identity read (whoami / harness.load) clears the gate:
        # both surface the active-identity block, so either proves the agent has
        # seen who is active. These carry no registry command key, so record here
        # rather than in identity_gate_refusal (which keys off command keys).
        if name in IDENTITY_READ_CONSOLE_TOOLS:
            identity_state.record_identity_read()
        if name == HARNESS_LOAD_TOOL:
            # Resolve the active-taxpayer identity at the server boundary (it reads
            # storage) and inject it into the otherwise-pure floor payload, so the
            # floor response carries WHO is active alongside the operating rules.
            floor_payload = build_harness_floor_payload(persona=persona, identity=build_whoami_identity())
            return CallToolResult(
                content=[TextContent(type="text", text=render_harness_floor_text(floor_payload))],
                structured_content=floor_payload.model_dump(mode="json"),
                is_error=False,
            )
        if name == WHOAMI_TOOL:
            identity = build_whoami_identity()
            return CallToolResult(
                content=[TextContent(type="text", text=render_whoami_identity_text(identity))],
                structured_content=identity.model_dump(mode="json"),
                is_error=False,
            )
        if name == CORPUS_SEARCH_TOOL:
            try:
                corpus_payload = build_corpus_search_payload(
                    str(arguments.get("query", "") or ""),
                    limit=_tool_arg_limit(arguments.get("limit", 8), 8),
                )
            except Exception as exc:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"corpus search unavailable: {exc}")],
                    is_error=True,
                )
            return CallToolResult(
                content=[TextContent(type="text", text=render_corpus_search_text(corpus_payload))],
                structured_content=corpus_payload.model_dump(mode="json"),
                is_error=False,
            )
        if name == TERMINOLOGY_SEARCH_TOOL:
            try:
                term_payload = build_terminology_search_payload(
                    str(arguments.get("query", "") or ""),
                    limit=_tool_arg_limit(arguments.get("limit", 8), 8),
                )
            except Exception as exc:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"terminology search unavailable: {exc}")],
                    is_error=True,
                )
            return CallToolResult(
                content=[TextContent(type="text", text=render_terminology_search_text(term_payload))],
                structured_content=term_payload.model_dump(mode="json"),
                is_error=False,
            )
        if name == _META_CONTRACT_TOOL:
            manifest_payload = build_capability_manifest().model_dump(mode="json")
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(manifest_payload, indent=2))],
                structured_content=manifest_payload,
                is_error=False,
            )
        if name == _META_SEARCH_TOOL:
            response = search_commands_response(
                str(arguments.get("query", "") or ""),
                descriptors=descriptors,
                index=command_index,
            )
            search_payload = response.model_dump(mode="json")
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(search_payload, indent=2))],
                structured_content=search_payload,
                is_error=False,
            )
        if name == _META_DESCRIBE_TOOL:
            describe_key = str(arguments.get("command_key", "") or "")
            described = describe_command(describe_key, descriptors=descriptors)
            if described is None:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"unknown command: {describe_key}")],
                    is_error=True,
                )
            describe_payload = described.model_dump(mode="json")
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(describe_payload, indent=2))],
                structured_content=describe_payload,
                is_error=False,
            )
        if name == _META_TOOLSETS_TOOL:
            outcome = manage_toolsets(
                str(arguments.get("action", "list") or "list"),
                (str(arguments["name"]) if arguments.get("name") is not None else None),
                active=active_toolsets,
            )
            if outcome.changed:
                # Best-effort per the floor/enhancement rule: a client that does not
                # honour list-changed still sees the widened surface on its next
                # tools/list, so a send failure must not break the call.
                with contextlib.suppress(Exception):
                    await ctx.session.send_tool_list_changed()
            payload = outcome.model_dump(mode="json")
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(payload, indent=2))],
                structured_content=payload,
                is_error=outcome.refused is not None,
            )
        if name == _META_EXECUTE_TOOL:
            refusal, envelope, thinned_envelope, links, is_error = await _run_offloop_with_progress(
                ctx,
                partial(
                    _meta_execute_call_outcome,
                    arguments,
                    descriptors=descriptors,
                    persona=persona,
                    run=_gated_subprocess_run,
                ),
            )
            if refusal is not None:
                return CallToolResult(content=[TextContent(type="text", text=refusal)], is_error=True)
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(envelope, indent=2)), *_resource_links(links)],
                structured_content=thinned_envelope,
                is_error=is_error,
            )
        descriptor = by_name.get(name)
        if descriptor is None:
            return CallToolResult(content=[TextContent(type="text", text=f"unknown tool: {name}")], is_error=True)
        key = command_key_for_tool(name, command_keys=[d.command_key for d in descriptors])
        if key is None:
            return CallToolResult(content=[TextContent(type="text", text=f"unmapped tool: {name}")], is_error=True)
        # The persona-scope, handoff-denial, and permanent live-write gate is
        # composed EXACTLY ONCE, by the single shared :func:`gate_refusal` the
        # ``execute`` meta-path also runs, so a refused call carries one refusal
        # and the two entry points cannot compose divergent (or doubled) refusals.
        gate = gate_refusal(persona=persona, descriptor=descriptor)
        if gate is not None:
            return CallToolResult(content=[TextContent(type="text", text=gate)], is_error=True)
        identity_refusal = identity_gate_refusal(
            key, execution_policy=descriptor.execution_policy, state=identity_state
        )
        if identity_refusal is not None:
            _record_telemetry(telemetry, tool_name=name, command_key=key, route="identity_block", is_error=True)
            return CallToolResult(content=[TextContent(type="text", text=identity_refusal)], is_error=True)
        policy = confirmation_for_policy(descriptor.execution_policy)
        route = resolve_confirm_route(
            policy=policy,
            command_key=key,
            execution_policy=descriptor.execution_policy,
            client_supports_elicitation=_client_supports_elicitation(ctx),
        )
        if route in (ConfirmRoute.REFUSE_BLOCKED, ConfirmRoute.REFUSE_NO_CHANNEL):
            _record_telemetry(telemetry, tool_name=name, command_key=key, route=route.value, is_error=True)
            return CallToolResult(
                content=[TextContent(type="text", text=refusal_message(route, command_key=key))],
                is_error=True,
            )
        route_label = route.value
        if route is ConfirmRoute.ELICIT:
            request = confirmation_request(command_key=key, execution_policy=descriptor.execution_policy)
            # Name the active-taxpayer LABEL in the human-facing prompt
            # so the person approving a destructive/handoff verb sees whose data
            # it touches and can catch an Erik/Erika mismatch at the gate.
            echo = identity_elicitation_echo(active_profile_label=build_whoami_identity().active_profile)
            result = await ctx.session.elicit(
                message=f"{echo}\n\n{request.message}",
                requested_schema=request.requested_schema,
            )
            decision = decision_from_elicitation(
                action=str(result.action),
                content=dict(result.content) if result.content else None,
            )
            route_label = f"{route.value}:{decision.value}"
            if decision is not ConfirmDecision.PROCEED:
                _record_telemetry(telemetry, tool_name=name, command_key=key, route=route_label, is_error=True)
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=_declined_message(command_key=key, decision=decision),
                        ),
                    ],
                    is_error=True,
                )
        arguments_json = json.dumps(arguments, ensure_ascii=False, sort_keys=True)
        faith = arguments_faithfulness(
            arguments_json=arguments_json,
            window=window,
            blocking=is_handoff_command(descriptor.execution_policy),
        )
        if faith.blocks:
            _record_telemetry(
                telemetry,
                tool_name=name,
                command_key=key,
                route="faithfulness_block",
                is_error=True,
                arguments_text=arguments_json,
            )
            return CallToolResult(
                content=[TextContent(type="text", text=advisory_line(faith))],
                is_error=True,
            )
        started = time.monotonic()
        outcome = await _run_tool_with_progress(ctx, descriptor, arguments)
        envelope = outcome.envelope
        is_error = outcome.is_error
        envelope_json = json.dumps(envelope, ensure_ascii=False, sort_keys=True)
        window.record(envelope_json)
        _record_telemetry(
            telemetry,
            tool_name=name,
            command_key=key,
            route=route_label,
            transport=outcome.transport.value,
            is_error=is_error,
            duration_ms=int((time.monotonic() - started) * 1000),
            executable_text=outcome.executable,
            arguments_text=arguments_json,
            result_text=envelope_json,
        )
        # Move the verb's declared bulk arrays out of structured_content to
        # resource_link URIs a resources-capable client fetches on demand; the text
        # content still carries the full envelope for a client without resources.
        thinned_envelope, links = thin_envelope(key, envelope)
        content: list[ContentBlock] = []
        if not faith.faithful:
            content.append(TextContent(type="text", text=advisory_line(faith)))
        content.append(TextContent(type="text", text=json.dumps(envelope, indent=2)))
        content.extend(_resource_links(links))
        return CallToolResult(content=content, structured_content=thinned_envelope, is_error=is_error)

    # Guided-workflow prompt channel: the slash-command surface a client
    # renders for the USER. The catalogue and each prompt's embedded skill (plus
    # the operating rules for orientation) are derived from the shipped harness in
    # ``_prompts.py``; ``get`` returns the operating brief as a user message
    # followed by each embedded document as an ``EmbeddedResource``.
    async def _on_list_prompts(_ctx: ServerRequestContext, _params: PaginatedRequestParams | None) -> ListPromptsResult:
        return ListPromptsResult(
            prompts=[
                Prompt(
                    name=entry.name,
                    title=entry.title,
                    description=entry.description,
                    arguments=[
                        PromptArgument(name=argument.name, description=argument.description, required=argument.required)
                        for argument in entry.arguments
                    ],
                )
                for entry in build_prompt_catalogue()
            ],
        )

    async def _on_get_prompt(_ctx: ServerRequestContext, params: GetPromptRequestParams) -> GetPromptResult:
        try:
            document = prompt_document(params.name, params.arguments)
        except PromptNotFoundError as exc:
            raise ValueError(str(exc)) from exc
        messages: list[PromptMessage] = [
            PromptMessage(role="user", content=TextContent(type="text", text=document.brief_text)),
        ]
        messages.extend(
            PromptMessage(
                role="user",
                content=EmbeddedResource(
                    type="resource",
                    resource=TextResourceContents(
                        uri=embedded.uri,
                        mime_type=embedded.mime_type,
                        text=embedded.text,
                    ),
                ),
            )
            for embedded in document.embedded
        )
        return GetPromptResult(description=document.prompt.description, messages=messages)

    # Operating-layer resource channel: the concrete ``cadrumo://`` resource
    # set and the three ``cadrumo://<kind>/{name}`` templates are derived from the
    # shipped harness tree in ``_resources.py``; ``read`` resolves a URI to the
    # document text as ``text/markdown``.
    async def _on_list_resources(
        _ctx: ServerRequestContext, _params: PaginatedRequestParams | None
    ) -> ListResourcesResult:
        return ListResourcesResult(
            resources=[
                Resource(
                    uri=ref.uri,
                    name=ref.name,
                    description=ref.description,
                    mime_type=ref.mime_type,
                )
                for ref in list_harness_resources()
            ],
        )

    async def _on_list_resource_templates(
        _ctx: ServerRequestContext, _params: PaginatedRequestParams | None
    ) -> ListResourceTemplatesResult:
        return ListResourceTemplatesResult(
            resource_templates=[
                ResourceTemplate(
                    uri_template=template.uri_template,
                    name=template.name,
                    description=template.description,
                    mime_type=template.mime_type,
                )
                for template in list_harness_resource_templates()
            ],
        )

    async def _resolve_bulk_resource(kind: HarnessResourceKind, identity: str, uri: str) -> str:
        """Resolve a bucket-scoped resource by re-running its owning read verb.

        The bulk arrays a verb thins (calculation observations, evidence rows) live
        in ENCRYPTED bucket state the session-less server process cannot read, so
        resolution re-runs the declared resolver verb as a supervised subprocess -
        the same path a tool call uses - and returns its bulk field as a JSON array.
        For an active-bucket resolver (no id argument) the URI's identity is
        cross-checked against the resolved ``result`` so a link cannot silently
        resolve a different bucket's rows.
        """
        from anyio.to_thread import run_sync

        resolution = BULK_RESOLUTION[kind]
        descriptor = by_command_key.get(resolution.resolver_command_key)
        if descriptor is None:
            raise ValueError(f"no resolver verb for resource {uri}")
        resolver_args: dict[str, object] = {}
        if resolution.id_arg is not None:
            resolver_args[resolution.id_arg] = identity
        outcome = await run_sync(_run_subprocess_tool, descriptor, resolver_args, limiter=serving_capacity_limiter())
        envelope = outcome.envelope
        is_error = outcome.is_error
        result = envelope.get("result")
        if is_error or not isinstance(result, dict):
            raise ValueError(f"could not resolve resource {uri}")
        if resolution.id_arg is None and result.get("bucket_id") != identity:
            raise ValueError(f"resource {uri} does not match the active bucket")
        rows = result.get(resolution.result_field)
        if not isinstance(rows, list):
            raise ValueError(f"resource {uri} resolved no {resolution.result_field} rows")
        return json.dumps(rows, ensure_ascii=False, indent=2)

    async def _on_read_resource(_ctx: ServerRequestContext, params: ReadResourceRequestParams) -> ReadResourceResult:
        uri = params.uri
        try:
            kind, name = parse_resource_uri(uri)
        except HarnessResourceNotFoundError as exc:
            raise ValueError(str(exc)) from exc
        if kind in BUCKET_SCOPED_RESOURCE_KINDS:
            text = await _resolve_bulk_resource(kind, name, uri)
            return ReadResourceResult(
                contents=[TextResourceContents(uri=uri, mime_type=resource_mime_type(kind), text=text)],
            )
        try:
            content = read_harness_resource(uri)
        except HarnessResourceNotFoundError as exc:
            raise ValueError(str(exc)) from exc
        return ReadResourceResult(
            contents=[TextResourceContents(uri=uri, mime_type=content.ref.mime_type, text=content.text)],
        )

    # Argument autocompletion for the guided-workflow prompts: a client
    # completing a prompt argument (filing year, period) gets the accepted
    # values from the typed axes.
    async def _on_completion(_ctx: ServerRequestContext, params: CompleteRequestParams) -> CompleteResult:
        if not isinstance(params.ref, PromptReference):
            return CompleteResult(completion=Completion(values=[], total=0, has_more=False))
        values = complete_prompt_argument(params.argument.name, params.argument.value)
        return CompleteResult(completion=Completion(values=list(values), total=len(values), has_more=False))

    return Server(
        "cadrumo",
        on_list_tools=_on_list_tools,
        on_call_tool=_on_call_tool,
        on_list_prompts=_on_list_prompts,
        on_get_prompt=_on_get_prompt,
        on_list_resources=_on_list_resources,
        on_list_resource_templates=_on_list_resource_templates,
        on_read_resource=_on_read_resource,
        on_completion=_on_completion,
    )


def server_initialization_options(server: Server) -> InitializationOptions:
    """Build the negotiated initialization options for ``server``.

    Declares ``tools.listChanged`` because the console emits
    ``tools/list_changed`` when a toolset is activated. Centralised so production
    (:func:`_run_server`) and the capability-posture conformance test negotiate
    the SAME capability set and cannot drift.
    """
    from mcp.server.lowlevel import NotificationOptions

    return server.create_initialization_options(NotificationOptions(tools_changed=True))


def _run_server(
    descriptors: tuple[McpToolDescriptor, ...],
    *,
    persona: AgentPersona | None = None,
    surface_mode: SurfaceMode = SurfaceMode.CORE,
) -> None:  # pragma: no cover - requires the SDK runtime
    """Build and run the MCP stdio server from the tool descriptors.

    Exercised only when the ``cadrumo-harness`` MCP runtime is installed; the descriptor,
    annotation, dispatch, block, and capability-registration logic it composes are
    unit-tested without the stdio transport via :func:`build_server`.
    """
    import anyio
    from mcp.server.stdio import stdio_server

    # Telemetry is diagnostics, never a startup dependency: resolving its
    # directory needs the storage root, and on a machine carrying retired
    # former-product state that resolution REFUSES. The refusal must surface
    # instructively on the tool calls that actually need storage - not kill
    # the server before it can speak the protocol. Serve without telemetry
    # and put one line on stderr (the client's MCP log) naming why.
    telemetry: SessionTelemetryWriter | None
    try:
        telemetry = SessionTelemetryWriter(session_id=f"mcp-{uuid.uuid4().hex[:12]}")
    except FormerProductStateError as error:
        telemetry = None
        sys.stderr.write(f"cadrumo MCP serving without telemetry (storage root unavailable): {error}\n")
    server: Server = build_server(descriptors, persona=persona, telemetry=telemetry, surface_mode=surface_mode)

    # Anchor the server's lifetime to its client BEFORE the transport starts.
    # The stdio contract is "exit on stdin EOF", but on Windows an inherited
    # pipe handle can keep stdin open after the spawning client is gone, so EOF
    # never arrives and this process - warm caches, registry, and all - runs
    # forever. Arming must happen here, on the main thread, because resolving
    # the stdin pipe creator is only safe before the reader has a read pending.
    # Fails open to EOF-only shutdown when it cannot arm.
    #
    # A watchdog reap is an os._exit, which bypasses atexit, so the pre-exit
    # hooks give the process a bounded window to do what a normal shutdown
    # would. Two distinct jobs, in the order that matters most first:
    #
    # Zeroise every live bucket session. The watchdog runs on its own daemon
    # thread, so the ContextVar-scoped close reaches nothing a warm worker
    # bound - and an in-flight worker is exactly where decrypted key material
    # lives when a reap fires. The registry sweep is cross-context and is the
    # only thing that covers it.
    #
    # Then run the ordinary exit functions, which release process-global state
    # such as the bucket lockfiles that would otherwise be stranded and block
    # the operator's next session.
    def _close_live_sessions_before_exit() -> None:
        close_all_live_bucket_sessions()

    register_pre_exit_hook(_close_live_sessions_before_exit)
    register_pre_exit_hook(atexit._run_exitfuncs)
    arm_stdio_lifetime_watchdog()

    async def _amain() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server_initialization_options(server))

    try:
        anyio.run(_amain)
    finally:
        disarm_stdio_lifetime_watchdog()
