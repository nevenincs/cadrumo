"""MCP server shell: the thin protocol wiring over the SDK-independent core.

The Model Context Protocol runtime is an optional dependency behind the
``cadrumo[agent]`` extra. :func:`serve` imports it lazily and, when it is absent,
refuses with the install hint and a non-zero exit instead of raising a raw
``ModuleNotFoundError`` - the same graceful-degradation contract the Google,
browser, and Anthropic integrations follow. The tool list, annotations, and the
forbidden-live-write block are sourced from the SDK-independent core in this
package; ``call_tool`` runs the deterministic CLI in a subprocess and returns its
JSON envelope as structured content. Alongside the per-verb tools the server
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
:func:`~entrypoints.mcp._persona_scope.active_persona`. When a persona is
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

import contextlib
import json
import os
import sys
import sysconfig
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from ...core import PRODUCT_IDENTITY
from ...core.external_constants import UTF_8_ENCODING
from ._call_runtime import CallTier, run_supervised, tier_for, timeout_seconds
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
    confirmation_for_tool,
    is_handoff_command,
    requires_user_interaction,
)
from ._identity_gate import (
    IDENTITY_READ_CONSOLE_TOOLS,
    SessionIdentityState,
    identity_elicitation_echo,
    identity_gate_refusal,
)
from ._input_schema import cli_argv_for
from ._meta_tools import (
    build_command_search_index,
    describe_command,
    manage_toolsets,
    meta_execute,
    search_commands_response,
)
from ._persona_scope import (
    AgentPersona,
    active_persona,
    handoff_denial_message,
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
)
from ._result_thinning import BULK_RESOLUTION, ResourceLinkRef, thin_envelope
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

if TYPE_CHECKING:
    # Typing-only: the MCP SDK is an optional runtime dependency (``cadrumo[agent]``),
    # so every real import of it is deferred to inside a function body (see the
    # module docstring). These names are never evaluated at runtime (deferred
    # annotations, `from __future__ import annotations`); they exist solely so
    # the standalone (non-nested) functions below can declare their true SDK
    # return/parameter types instead of the placeholder ``object``.
    from mcp.server import Server
    from mcp.server.models import InitializationOptions
    from mcp.types import ContentBlock, Tool

_INSTALL_HINT = "the MCP server requires the agent extra: pip install 'cadrumo[agent]'"

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
# tier, declared risk, owning toolset, and reachable personas - so a model can
# inspect a verb fully before spending an ``execute`` round-trip on it.
_META_DESCRIBE_TOOL = "describe"


def emit_missing_sdk_refusal() -> None:
    """Write the agent-extra install hint to stderr and exit non-zero.

    The graceful-degradation path taken when the MCP SDK is absent. Exposed so the
    refusal contract is unit-tested directly, in any environment, rather than
    relying on the SDK being absent at test time.
    """
    sys.stderr.write(_INSTALL_HINT + "\n")
    raise SystemExit(3)


def serve() -> None:
    """Run the ``cadrumo-mcp`` stdio server, or refuse if the SDK is not installed.

    Resolves the active persona from ``CADRUMO_MCP_PERSONA`` before touching the
    SDK, so an invalid persona value fails with the instructive
    :func:`~entrypoints.mcp._persona_scope.active_persona` error
    regardless of whether the optional SDK is installed.
    """
    persona = active_persona()
    surface_mode = resolve_surface_mode(os.environ.get(SURFACE_ENV_VAR))
    try:
        import mcp.server  # noqa: F401
    except ModuleNotFoundError:
        emit_missing_sdk_refusal()
        return
    _run_server(build_tool_descriptors(), persona=persona, surface_mode=surface_mode)


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
    :func:`~entrypoints.mcp._hitl.confirmation_for_tool` so an
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
    refuses gracefully) when the ``cadrumo[agent]`` extra is absent. Exposed at module
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
        policy = confirmation_for_tool(command_key=descriptor.command_key)
        meta = {REQUIRES_USER_INTERACTION_META_KEY: True} if requires_user_interaction(policy) else None
        tools.append(
            Tool(
                name=descriptor.name,
                description=descriptor.description,
                inputSchema=descriptor.input_schema,
                outputSchema=descriptor.output_schema,
                annotations=ToolAnnotations(
                    title=annotations.title,
                    readOnlyHint=annotations.read_only_hint,
                    destructiveHint=annotations.destructive_hint,
                    idempotentHint=annotations.idempotent_hint,
                    openWorldHint=annotations.open_world_hint,
                ),
                _meta=meta,
            ),
        )
    return tools


def _timeout_refusal_envelope(*, command_key: str, tier: CallTier, timeout_s: float) -> dict[str, object]:
    """Build the localized timed-out refusal envelope for a hung CLI call."""
    from ...core.i18n import tr

    message = tr(
        "mcp.call.timeout",
        command=command_key,
        tier=tier.value,
        seconds=int(timeout_s),
        default=(
            "'{command}' exceeded the {tier}-tier time limit ({seconds}s) and was cancelled. "
            "Retry, or run the equivalent Cadrumo command directly in a terminal for a long operation."
        ),
    )
    return {"status": "error", "refusal": message, "timed_out": True}


def _installed_cli_executable() -> str:
    """Resolve the sibling CLI installed in the server's Python environment.

    The MCP server and CLI are console scripts from one distribution cohort.
    Resolving the interpreter's scripts directory preserves that relationship
    even when ``PATH`` is empty, points at another environment, or contains a
    checkout shim. Missing installation state fails closed instead of falling
    back to an unrelated executable.
    """
    scripts_dir = Path(sysconfig.get_path("scripts")).resolve()
    executable_name = PRODUCT_IDENTITY.cli_executable
    if sys.platform == "win32":
        executable_name = f"{executable_name}.exe"
    executable = (scripts_dir / executable_name).resolve()
    if not executable.is_file():
        message = (
            f"Installed Cadrumo CLI executable is missing from the MCP server environment: {executable}"
        )
        raise FileNotFoundError(message)
    return str(executable)


def _cli_resolution_refusal_envelope(error: OSError) -> dict[str, object]:
    """Build a structured refusal for an incomplete MCP installation."""
    return {
        "status": "error",
        "refusal": str(error),
        "installation_incomplete": True,
    }


def _run_subprocess_tool(
    descriptor: McpToolDescriptor,
    arguments: dict[str, object],
) -> tuple[dict[str, object], bool]:
    """Run one tool's CLI command under the supervised runtime and return (envelope, is_error).

    The argv is reconstructed from the descriptor's per-verb input schema and the
    named ``arguments`` the client supplied - positional arguments in CLI order,
    then options - so the retired ``{args: [string]}`` bag has no path back in.

    The call runs through :func:`~entrypoints.mcp._call_runtime.run_supervised`
    with a per-tier wall-clock ceiling derived from the command's annotations:
    a hung call is terminated together with
    its whole process tree (a live pull spawns a browser child) and returns an
    instructive, localized timed-out refusal rather than hanging the MCP call.

    ``stdin`` is isolated to ``DEVNULL`` inside the runtime. Over the stdio
    transport the server's own stdin IS the MCP client pipe; without this
    isolation the spawned CLI child inherits that pipe and any read from it
    blocks forever. Output is decoded as UTF-8 explicitly (the CLI always emits
    UTF-8; the platform default is cp1252 on Windows, which would mojibake every
    accented character for the LLM client), with ``errors="replace"`` matching the
    CLI's own emit-side fallback.
    """
    tier = tier_for(
        read_only=descriptor.annotations.read_only_hint,
        open_world=descriptor.annotations.open_world_hint,
    )
    timeout_s = timeout_seconds(tier)
    try:
        executable = _installed_cli_executable()
        argv = [executable, *cli_argv_for(descriptor.verb_schema, arguments)]
        result = run_supervised(argv, timeout_s=timeout_s, encoding=UTF_8_ENCODING)
    except OSError as error:
        return (_cli_resolution_refusal_envelope(error), True)
    if result.timed_out:
        return (_timeout_refusal_envelope(command_key=descriptor.command_key, tier=tier, timeout_s=timeout_s), True)
    raw = result.stdout.strip() or result.stderr.strip()
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        return ({"status": "error", "raw": raw}, True)
    is_error = envelope.get("status") == "error" or result.returncode != 0
    return (envelope, is_error)


def build_meta_sdk_tools() -> list[Tool]:
    """Build the SDK ``Tool`` objects for the core-surface meta-tools.

    Lazily imports the SDK ``Tool`` type so the module still imports when the
    ``cadrumo[agent]`` extra is absent. Exposed at module level so the meta-tool
    surface is unit-tested against the real SDK types when they are installed.

    Returns:
        The ``search``, ``execute``, ``toolsets``, and ``describe``
        :class:`mcp.types.Tool` objects.
    """
    from mcp.types import Tool

    return [
        Tool(
            name=_META_SEARCH_TOOL,
            description=(
                "Search Cadrumo commands by keyword; returns matching command keys with mutability hints. "
                "Pass a hit to describe for its full schema before you run it, or activate a toolset to "
                "advertise a whole domain's verbs directly."
            ),
            inputSchema={
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
            inputSchema={
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
            inputSchema={
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
            inputSchema={
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
    from ...core.i18n import tr

    return tr(
        "mcp.elicitation.confirm.declined",
        command=command_key,
        outcome=decision.value,
        default="'{command}' was not confirmed by the user ({outcome}); nothing was run.",
    )


def _client_supports_elicitation(server: Server) -> bool:
    """Read the negotiated client capabilities for elicitation support (fail-closed).

    Inside a request handler the lowlevel server exposes the session through
    ``request_context``; a missing context, missing params, or missing
    capability all read as unsupported, so the degradation matrix falls back
    to the safe routes.
    """
    try:
        context = server.request_context
        params = context.session.client_params
    except (LookupError, AttributeError):
        return False
    capabilities = getattr(params, "capabilities", None)
    return bool(capabilities is not None and getattr(capabilities, "elicitation", None) is not None)


def _record_telemetry(
    telemetry: SessionTelemetryWriter | None,
    *,
    tool_name: str,
    command_key: str = "",
    route: str = "",
    is_error: bool = False,
    duration_ms: int = 0,
    arguments_text: str = "",
    result_text: str = "",
) -> None:
    """Forward to the optional telemetry sink, mirroring its signature exactly."""
    if telemetry is not None:
        telemetry.record(
            tool_name=tool_name,
            command_key=command_key,
            route=route,
            is_error=is_error,
            duration_ms=duration_ms,
            arguments_text=arguments_text,
            result_text=result_text,
        )


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

    Returns:
        The configured :class:`mcp.server.Server`.
    """
    from mcp.server import Server
    from mcp.server.lowlevel.helper_types import ReadResourceContents
    from mcp.types import (
        CallToolResult,
        Completion,
        CompletionArgument,
        EmbeddedResource,
        GetPromptResult,
        Prompt,
        PromptArgument,
        PromptMessage,
        Resource,
        ResourceLink,
        ResourceTemplate,
        TextContent,
        TextResourceContents,
    )
    from pydantic import AnyUrl

    def _resource_links(refs: tuple[ResourceLinkRef, ...]) -> list[ResourceLink]:
        """Adapt the thinning ``ResourceLinkRef`` set onto SDK ``resource_link`` items."""
        return [
            ResourceLink(
                type="resource_link",
                uri=AnyUrl(ref.uri),
                name=ref.name,
                description=ref.description,
                mimeType=ref.mime_type,
            )
            for ref in refs
        ]

    scoped_descriptors = tuple(
        descriptor
        for descriptor in filter_descriptors_for_persona(descriptors, persona=persona)
        if persona is None or not is_handoff_denied(persona=persona, command_key=descriptor.command_key)
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
    # The hybrid command-search index backing the ``search`` meta-tool, built
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

    # Per-session serving-path gates and telemetry: the
    # grounding window accumulates this session's tool-result JSON in memory
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
    ) -> tuple[dict[str, object], bool]:
        """The sync gate suite shared by the meta-execute path.

        A sync callable cannot elicit, so the degradation matrix runs with
        ``client_supports_elicitation=False``: handoff-tier CONFIRM refuses
        (fail-closed), non-handoff CONFIRM proceeds under the client's
        annotation-driven confirmation. Faithfulness and telemetry match the
        direct path.
        """
        key = descriptor.command_key
        identity_refusal = identity_gate_refusal(key, state=identity_state)
        if identity_refusal is not None:
            _record_telemetry(
                telemetry, tool_name=descriptor.name, command_key=key, route="identity_block", is_error=True
            )
            return ({"status": "error", "refusal": identity_refusal}, True)
        policy = confirmation_for_tool(command_key=key)
        route = resolve_confirm_route(policy=policy, command_key=key, client_supports_elicitation=False)
        if route in (ConfirmRoute.REFUSE_BLOCKED, ConfirmRoute.REFUSE_NO_CHANNEL):
            _record_telemetry(telemetry, tool_name=descriptor.name, command_key=key, route=route.value, is_error=True)
            return ({"status": "error", "refusal": refusal_message(route, command_key=key)}, True)
        arguments_json = json.dumps(arguments, ensure_ascii=False, sort_keys=True)
        faith = arguments_faithfulness(arguments_json=arguments_json, window=window, blocking=is_handoff_command(key))
        if faith.blocks:
            _record_telemetry(
                telemetry,
                tool_name=descriptor.name,
                command_key=key,
                route="faithfulness_block",
                is_error=True,
                arguments_text=arguments_json,
            )
            return ({"status": "error", "refusal": advisory_line(faith)}, True)
        started = time.monotonic()
        envelope, is_error = _run_subprocess_tool(descriptor, arguments)
        envelope_json = json.dumps(envelope, ensure_ascii=False, sort_keys=True)
        window.record(envelope_json)
        _record_telemetry(
            telemetry,
            tool_name=descriptor.name,
            command_key=key,
            route=route.value,
            is_error=is_error,
            duration_ms=int((time.monotonic() - started) * 1000),
            arguments_text=arguments_json,
            result_text=envelope_json,
        )
        return (envelope, is_error)

    server: Server = Server(PRODUCT_IDENTITY.mcp_server)

    async def _run_tool_with_progress(
        descriptor: McpToolDescriptor,
        arguments: dict[str, object],
    ) -> tuple[dict[str, object], bool]:
        """Run the CLI subprocess off the event loop, heart-beating progress.

        The supervised call blocks (Popen.communicate); running it in a worker
        thread keeps the event loop responsive for the whole - possibly
        minutes-long - live pull. When the client supplied a progress token, an
        elapsed-seconds heartbeat is sent every few seconds until the call
        completes, so a slow pull looks alive
        rather than hung; a client that sent no token still gets the off-loop run.
        """
        import anyio
        from anyio.to_thread import run_sync

        progress_token = None
        with contextlib.suppress(LookupError, AttributeError):
            meta = server.request_context.meta
            progress_token = getattr(meta, "progressToken", None) if meta is not None else None

        if progress_token is None:
            return await run_sync(_run_subprocess_tool, descriptor, arguments)

        holder: dict[str, tuple[dict[str, object], bool]] = {}

        async def _work() -> None:
            holder["result"] = await run_sync(_run_subprocess_tool, descriptor, arguments)
            task_group.cancel_scope.cancel()

        async def _heartbeat() -> None:
            elapsed = 0
            while True:
                await anyio.sleep(5)
                elapsed += 5
                with contextlib.suppress(Exception):
                    await server.request_context.session.send_progress_notification(
                        progress_token=progress_token,
                        progress=float(elapsed),
                        total=None,
                    )

        async with anyio.create_task_group() as task_group:
            task_group.start_soon(_heartbeat)
            task_group.start_soon(_work)
        return holder["result"]

    @server.list_tools()
    async def _list_tools() -> list[Tool]:
        # The harness.load floor tool is advertised first and is never persona-scoped
        # away: it is the universal operating-layer channel that must reach
        # any client, including a minimal tools-only one. The whoami identity tool and
        # the grounding tools follow for the same always-available reason:
        # an agent must always be able to confirm the active taxpayer and ground its
        # narration, whatever the persona. The per-verb surface is the orientation core
        # plus any active toolset (rebuilt per call so a toolset activation is
        # reflected).
        return [floor_tool, whoami_tool, *grounding_tools, *_advertised_tools(), *meta_tools]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, object]) -> CallToolResult:
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
                structuredContent=floor_payload.model_dump(mode="json"),
                isError=False,
            )
        if name == WHOAMI_TOOL:
            identity = build_whoami_identity()
            return CallToolResult(
                content=[TextContent(type="text", text=render_whoami_identity_text(identity))],
                structuredContent=identity.model_dump(mode="json"),
                isError=False,
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
                    isError=True,
                )
            return CallToolResult(
                content=[TextContent(type="text", text=render_corpus_search_text(corpus_payload))],
                structuredContent=corpus_payload.model_dump(mode="json"),
                isError=False,
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
                    isError=True,
                )
            return CallToolResult(
                content=[TextContent(type="text", text=render_terminology_search_text(term_payload))],
                structuredContent=term_payload.model_dump(mode="json"),
                isError=False,
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
                structuredContent=search_payload,
                isError=False,
            )
        if name == _META_DESCRIBE_TOOL:
            describe_key = str(arguments.get("command_key", "") or "")
            described = describe_command(describe_key, descriptors=descriptors)
            if described is None:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"unknown command: {describe_key}")],
                    isError=True,
                )
            describe_payload = described.model_dump(mode="json")
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(describe_payload, indent=2))],
                structuredContent=describe_payload,
                isError=False,
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
                    await server.request_context.session.send_tool_list_changed()
            payload = outcome.model_dump(mode="json")
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(payload, indent=2))],
                structuredContent=payload,
                isError=outcome.refused is not None,
            )
        if name == _META_EXECUTE_TOOL:
            raw_args = arguments.get("arguments", {})
            exec_args = dict(raw_args) if isinstance(raw_args, dict) else {}
            outcome = meta_execute(
                str(arguments.get("command_key", "") or ""),
                exec_args,
                descriptors=descriptors,
                persona=persona,
                run=_gated_subprocess_run,
            )
            if outcome.refused is not None:
                return CallToolResult(content=[TextContent(type="text", text=outcome.refused)], isError=True)
            envelope = outcome.envelope or {}
            # Thin the executed verb's bulk arrays here too, so the meta
            # `execute` path and the direct-call path emit one identical shape.
            thinned_envelope, links = thin_envelope(str(arguments.get("command_key", "") or ""), envelope)
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(envelope, indent=2)), *_resource_links(links)],
                structuredContent=thinned_envelope,
                isError=outcome.is_error,
            )
        descriptor = by_name.get(name)
        if descriptor is None:
            return CallToolResult(content=[TextContent(type="text", text=f"unknown tool: {name}")], isError=True)
        key = command_key_for_tool(name, command_keys=[d.command_key for d in descriptors])
        if key is None:
            return CallToolResult(content=[TextContent(type="text", text=f"unmapped tool: {name}")], isError=True)
        scope_refusal = persona_scope_refusal(persona=persona, command_key=key)
        if scope_refusal is not None:
            return CallToolResult(content=[TextContent(type="text", text=scope_refusal)], isError=True)
        if persona is not None and is_handoff_denied(persona=persona, command_key=key):
            return CallToolResult(
                content=[TextContent(type="text", text=handoff_denial_message(persona=persona, command_key=key))],
                isError=True,
            )
        identity_refusal = identity_gate_refusal(key, state=identity_state)
        if identity_refusal is not None:
            _record_telemetry(telemetry, tool_name=name, command_key=key, route="identity_block", is_error=True)
            return CallToolResult(content=[TextContent(type="text", text=identity_refusal)], isError=True)
        policy = confirmation_for_tool(command_key=key)
        route = resolve_confirm_route(
            policy=policy,
            command_key=key,
            client_supports_elicitation=_client_supports_elicitation(server),
        )
        if route in (ConfirmRoute.REFUSE_BLOCKED, ConfirmRoute.REFUSE_NO_CHANNEL):
            _record_telemetry(telemetry, tool_name=name, command_key=key, route=route.value, is_error=True)
            return CallToolResult(
                content=[TextContent(type="text", text=refusal_message(route, command_key=key))],
                isError=True,
            )
        route_label = route.value
        if route is ConfirmRoute.ELICIT:
            request = confirmation_request(command_key=key)
            # Name the active-taxpayer LABEL in the human-facing prompt
            # so the person approving a destructive/handoff verb sees whose data
            # it touches and can catch an Erik/Erika mismatch at the gate.
            echo = identity_elicitation_echo(active_profile_label=build_whoami_identity().active_profile)
            result = await server.request_context.session.elicit(
                message=f"{echo}\n\n{request.message}",
                requestedSchema=request.requested_schema,
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
                    isError=True,
                )
        arguments_json = json.dumps(arguments, ensure_ascii=False, sort_keys=True)
        faith = arguments_faithfulness(arguments_json=arguments_json, window=window, blocking=is_handoff_command(key))
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
                isError=True,
            )
        started = time.monotonic()
        envelope, is_error = await _run_tool_with_progress(descriptor, arguments)
        envelope_json = json.dumps(envelope, ensure_ascii=False, sort_keys=True)
        window.record(envelope_json)
        _record_telemetry(
            telemetry,
            tool_name=name,
            command_key=key,
            route=route_label,
            is_error=is_error,
            duration_ms=int((time.monotonic() - started) * 1000),
            arguments_text=arguments_json,
            result_text=envelope_json,
        )
        # Move the verb's declared bulk arrays out of structuredContent to
        # resource_link URIs a resources-capable client fetches on demand; the text
        # content still carries the full envelope for a client without resources.
        thinned_envelope, links = thin_envelope(key, envelope)
        content: list[ContentBlock] = []
        if not faith.faithful:
            content.append(TextContent(type="text", text=advisory_line(faith)))
        content.append(TextContent(type="text", text=json.dumps(envelope, indent=2)))
        content.extend(_resource_links(links))
        return CallToolResult(content=content, structuredContent=thinned_envelope, isError=is_error)

    # Guided-workflow prompt channel: the slash-command surface a client
    # renders for the USER. The catalogue and each prompt's embedded skill (plus
    # the operating rules for orientation) are derived from the shipped harness in
    # ``_prompts.py``; ``get`` returns the operating brief as a user message
    # followed by each embedded document as an ``EmbeddedResource``.
    @server.list_prompts()
    async def _list_prompts() -> list[Prompt]:
        return [
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
        ]

    @server.get_prompt()
    async def _get_prompt(name: str, arguments: dict[str, str] | None = None) -> GetPromptResult:
        try:
            document = prompt_document(name, arguments)
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
                        uri=AnyUrl(embedded.uri),
                        mimeType=embedded.mime_type,
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
    @server.list_resources()
    async def _list_resources() -> list[Resource]:
        return [
            Resource(
                uri=AnyUrl(ref.uri),
                name=ref.name,
                description=ref.description,
                mimeType=ref.mime_type,
            )
            for ref in list_harness_resources()
        ]

    @server.list_resource_templates()
    async def _list_resource_templates() -> list[ResourceTemplate]:
        return [
            ResourceTemplate(
                uriTemplate=template.uri_template,
                name=template.name,
                description=template.description,
                mimeType=template.mime_type,
            )
            for template in list_harness_resource_templates()
        ]

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
        envelope, is_error = await run_sync(_run_subprocess_tool, descriptor, resolver_args)
        result = envelope.get("result")
        if is_error or not isinstance(result, dict):
            raise ValueError(f"could not resolve resource {uri}")
        if resolution.id_arg is None and result.get("bucket_id") != identity:
            raise ValueError(f"resource {uri} does not match the active bucket")
        rows = result.get(resolution.result_field)
        if not isinstance(rows, list):
            raise ValueError(f"resource {uri} resolved no {resolution.result_field} rows")
        return json.dumps(rows, ensure_ascii=False, indent=2)

    @server.read_resource()
    async def _read_resource(uri: AnyUrl) -> list[ReadResourceContents]:
        try:
            kind, name = parse_resource_uri(str(uri))
        except HarnessResourceNotFoundError as exc:
            raise ValueError(str(exc)) from exc
        if kind in BUCKET_SCOPED_RESOURCE_KINDS:
            text = await _resolve_bulk_resource(kind, name, str(uri))
            return [ReadResourceContents(content=text, mime_type="application/json")]
        try:
            content = read_harness_resource(str(uri))
        except HarnessResourceNotFoundError as exc:
            raise ValueError(str(exc)) from exc
        return [ReadResourceContents(content=content.text, mime_type=content.ref.mime_type)]

    # Argument autocompletion for the guided-workflow prompts: a client
    # completing a prompt argument (filing year, period) gets the accepted
    # values from the typed axes.
    @server.completion()
    async def _complete(ref: object, argument: CompletionArgument, context: object) -> Completion | None:
        from mcp.types import PromptReference

        if not isinstance(ref, PromptReference):
            return None
        values = complete_prompt_argument(argument.name, argument.value)
        return Completion(values=list(values), total=len(values), hasMore=False)

    return server


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

    Exercised only when the ``cadrumo[agent]`` extra is installed; the descriptor,
    annotation, dispatch, block, and capability-registration logic it composes are
    unit-tested without the stdio transport via :func:`build_server`.
    """
    import anyio
    from mcp.server.stdio import stdio_server

    telemetry = SessionTelemetryWriter(session_id=f"mcp-{uuid.uuid4().hex[:12]}")
    server: Server = build_server(descriptors, persona=persona, telemetry=telemetry, surface_mode=surface_mode)

    async def _amain() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server_initialization_options(server))

    anyio.run(_amain)
