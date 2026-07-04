"""MCP server shell: the thin protocol wiring over the SDK-independent core.

The Model Context Protocol runtime is an optional dependency behind the
``aeat[agent]`` extra. :func:`serve` imports it lazily and, when it is absent,
refuses with the install hint and a non-zero exit instead of raising a raw
``ModuleNotFoundError`` - the same graceful-degradation contract the Google,
browser, and Anthropic integrations follow. The tool list, annotations, and the
forbidden-live-write block are sourced from the SDK-independent core in this
package; ``call_tool`` runs the deterministic CLI in a subprocess and returns its
JSON envelope as structured content. Alongside the per-verb tools the server
advertises the ``search`` / ``execute`` meta-tools and the ``harness.load`` floor
tool (the universal operating-layer channel of ADR R4), and serves the operating
layer through real ``resources`` handlers - the concrete ``aeat://`` skill / rule
/ persona set, the three ``aeat://<kind>/{name}`` templates, and a ``read``
resolver - and through real ``prompts`` handlers: the guided-workflow catalogue
and each prompt's embedded skill / rules, derived from ``_prompts.py``.
:func:`build_server` owns that registration and is unit-tested against the real
SDK without the stdio transport.

Per D1 of ``2026-07-01-agent-harness-adr``, the server also enforces the
persona-scoped tool boundary declared in ``_persona_scope.py``:
:func:`serve` resolves the active persona once, at startup, from the
``AEAT_MCP_PERSONA`` environment variable via
:func:`~entrypoints.mcp._persona_scope.active_persona`. When a persona is
active, ``_list_tools`` advertises only that persona's in-scope tools
(:func:`filter_descriptors_for_persona`) and ``_call_tool`` refuses an
out-of-scope call (:func:`persona_scope_refusal`) before the global HITL
``confirmation_for_tool`` gate runs. An unset/blank env var preserves the
full, unscoped tool surface - pre-D1 behaviour - for any un-personified
session. See ``_persona_scope.py``'s module docstring for the known
family-granularity limitation (the three modelo-lifecycle personas share one
manifest family and are not distinguished by this gate).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import uuid
from typing import TYPE_CHECKING

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
    build_harness_floor_payload,
    build_harness_floor_tool,
    render_harness_floor_text,
)
from ._hitl import (
    REQUIRES_USER_INTERACTION_META_KEY,
    confirmation_for_tool,
    is_handoff_command,
    requires_user_interaction,
)
from ._input_schema import cli_argv_for
from ._meta_tools import meta_execute, search_commands
from ._persona_scope import (
    AgentPersona,
    active_persona,
    handoff_denial_message,
    is_handoff_denied,
    is_tool_in_persona_scope,
)
from ._prompts import PromptNotFoundError, build_prompt_catalogue, prompt_document
from ._resources import (
    HarnessResourceNotFoundError,
    list_harness_resource_templates,
    list_harness_resources,
    read_harness_resource,
)
from ._telemetry import SessionTelemetryWriter
from ._terminology_tools import (
    TERMINOLOGY_SEARCH_TOOL,
    build_terminology_search_payload,
    build_terminology_search_tool,
    render_terminology_search_text,
)
from ._tools import McpToolDescriptor, build_tool_descriptors

if TYPE_CHECKING:
    # Typing-only: the MCP SDK is an optional runtime dependency (``aeat[agent]``),
    # so every real import of it is deferred to inside a function body (see the
    # module docstring). These names are never evaluated at runtime (deferred
    # annotations, `from __future__ import annotations`); they exist solely so
    # the standalone (non-nested) functions below can declare their true SDK
    # return/parameter types instead of the placeholder ``object``.
    from mcp.server import Server
    from mcp.types import ContentBlock, Tool

_INSTALL_HINT = "the MCP server requires the agent extra: pip install 'aeat[agent]'"
_SERVER_NAME = "aeat"

# The two meta-tools that reach the long-tail verb surface outside the curated
# toolsets. They are advertised alongside the per-verb tools and are never
# persona-scoped away (``execute`` applies the persona gate internally).
_META_SEARCH_TOOL = "search"
_META_EXECUTE_TOOL = "execute"


def emit_missing_sdk_refusal() -> None:
    """Write the agent-extra install hint to stderr and exit non-zero.

    The graceful-degradation path taken when the MCP SDK is absent. Exposed so the
    refusal contract is unit-tested directly, in any environment, rather than
    relying on the SDK being absent at test time.
    """
    sys.stderr.write(_INSTALL_HINT + "\n")
    raise SystemExit(3)


def serve() -> None:
    """Run the ``aeat-mcp`` stdio server, or refuse if the SDK is not installed.

    Resolves the active persona from ``AEAT_MCP_PERSONA`` before touching the
    SDK, so an invalid persona value fails with the instructive
    :func:`~entrypoints.mcp._persona_scope.active_persona` error
    regardless of whether the optional SDK is installed.
    """
    persona = active_persona()
    try:
        import mcp.server  # noqa: F401
    except ModuleNotFoundError:
        emit_missing_sdk_refusal()
        return
    _run_server(build_tool_descriptors(), persona=persona)


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
    refuses gracefully) when the ``aeat[agent]`` extra is absent. Exposed at module
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
        policy = confirmation_for_tool(command_key=descriptor.command_key, annotations=annotations)
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
                ),
                _meta=meta,
            ),
        )
    return tools


def _run_subprocess_tool(
    descriptor: McpToolDescriptor,
    arguments: dict[str, object],
) -> tuple[dict[str, object], bool]:
    """Run one tool's CLI command in a subprocess and return (envelope, is_error).

    The argv is reconstructed from the descriptor's per-verb input schema and the
    named ``arguments`` the client supplied - positional arguments in CLI order,
    then options - so the retired ``{args: [string]}`` bag has no path back in.

    ``stdin`` is isolated to ``DEVNULL``. Over the stdio transport the server's
    own stdin IS the MCP client pipe; without this isolation the spawned CLI
    child inherits that pipe and any read from it (a prompt, a confirm, or the
    secret-store passphrase fallback) blocks forever, competing with the client
    for the transport and deadlocking the session on the first CLI-backed call.
    A non-interactive stdin also makes every CLI verb take its explicit-flag /
    env path rather than an interactive prompt, which is the only correct mode
    for an agent-operated console.
    """
    # Decode the child's output as UTF-8 explicitly. The CLI always emits UTF-8
    # (its stdout JSON is UTF-8 and `write_stderr` reconfigures stderr to UTF-8),
    # but `text=True` alone would decode with the platform default —
    # ``locale.getpreferredencoding()`` is cp1252 on Windows — turning every
    # accented Spanish character in a relayed envelope or error into double-
    # encoded mojibake (``encontró`` -> ``encontrÃ³``) for the LLM client. The
    # live-model persona measurement observed exactly this. ``errors="replace"``
    # matches the CLI's own emit-side fallback so a stray non-UTF-8 byte degrades
    # to the replacement character rather than raising.
    argv = ["aeat", *cli_argv_for(descriptor.verb_schema, arguments)]
    completed = subprocess.run(  # noqa: S603
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        stdin=subprocess.DEVNULL,
    )
    raw = completed.stdout.strip() or completed.stderr.strip()
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        return ({"status": "error", "raw": raw}, True)
    is_error = envelope.get("status") == "error" or completed.returncode != 0
    return (envelope, is_error)


def build_meta_sdk_tools() -> list[Tool]:
    """Build the SDK ``Tool`` objects for the ``search`` and ``execute`` meta-tools.

    Lazily imports the SDK ``Tool`` type so the module still imports when the
    ``aeat[agent]`` extra is absent. Exposed at module level so the meta-tool
    surface is unit-tested against the real SDK types when they are installed.

    Returns:
        The ``search`` and ``execute`` :class:`mcp.types.Tool` objects.
    """
    from mcp.types import Tool

    return [
        Tool(
            name=_META_SEARCH_TOOL,
            description="Search aeat commands by keyword; returns matching command keys with mutability hints.",
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
            description="Execute one aeat command by key with named arguments, through the same safety gates.",
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


def build_server(
    descriptors: tuple[McpToolDescriptor, ...],
    *,
    persona: AgentPersona | None = None,
    telemetry: SessionTelemetryWriter | None = None,
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
        EmbeddedResource,
        GetPromptResult,
        Prompt,
        PromptMessage,
        Resource,
        ResourceTemplate,
        TextContent,
        TextResourceContents,
    )
    from pydantic import AnyUrl

    scoped_descriptors = tuple(
        descriptor
        for descriptor in filter_descriptors_for_persona(descriptors, persona=persona)
        if persona is None or not is_handoff_denied(persona=persona, command_key=descriptor.command_key)
    )
    by_name = {descriptor.name: descriptor for descriptor in descriptors}
    sdk_tools = build_sdk_tools(scoped_descriptors)
    meta_tools = build_meta_sdk_tools()
    floor_tool = build_harness_floor_tool()
    # Grounding tools (ADR R3): read-only search over the bundled legal corpus
    # and the taxpayer-facing terminology handbook. Always advertised (never
    # persona-scoped away) — every persona benefits from grounding its narration
    # in authoritative text, and neither tool mutates state.
    grounding_tools = [build_corpus_search_tool(), build_terminology_search_tool()]

    # Per-session serving-path gates (ADR R6) and telemetry (ADR R7): the
    # grounding window accumulates this session's tool-result JSON in memory
    # only; the telemetry writer (injected by the stdio runner; None in unit
    # builds) records payload-free per-call rows.
    window = SessionGroundingWindow()

    def _telemetry_record(
        *,
        tool_name: str,
        command_key: str = "",
        route: str = "",
        is_error: bool = False,
        duration_ms: int = 0,
        arguments_text: str = "",
        result_text: str = "",
    ) -> None:
        """Thin optional-sink forward onto ``telemetry.record``, mirroring its signature exactly."""
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
        policy = confirmation_for_tool(command_key=key, annotations=descriptor.annotations)
        route = resolve_confirm_route(policy=policy, command_key=key, client_supports_elicitation=False)
        if route in (ConfirmRoute.REFUSE_BLOCKED, ConfirmRoute.REFUSE_NO_CHANNEL):
            _telemetry_record(tool_name=descriptor.name, command_key=key, route=route.value, is_error=True)
            return ({"status": "error", "refusal": refusal_message(route, command_key=key)}, True)
        arguments_json = json.dumps(arguments, ensure_ascii=False, sort_keys=True)
        faith = arguments_faithfulness(arguments_json=arguments_json, window=window, blocking=is_handoff_command(key))
        if faith.blocks:
            _telemetry_record(
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
        _telemetry_record(
            tool_name=descriptor.name,
            command_key=key,
            route=route.value,
            is_error=is_error,
            duration_ms=int((time.monotonic() - started) * 1000),
            arguments_text=arguments_json,
            result_text=envelope_json,
        )
        return (envelope, is_error)

    server: Server = Server(_SERVER_NAME)

    @server.list_tools()
    async def _list_tools() -> list[Tool]:
        # The harness.load floor tool is advertised first and is never persona-scoped
        # away: per ADR R4 it is the universal operating-layer channel that must reach
        # any client, including a minimal tools-only one. The grounding tools follow
        # for the same always-available reason (ADR R3).
        return [floor_tool, *grounding_tools, *sdk_tools, *meta_tools]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, object]) -> CallToolResult:
        if name == HARNESS_LOAD_TOOL:
            floor_payload = build_harness_floor_payload(persona=persona)
            return CallToolResult(
                content=[TextContent(type="text", text=render_harness_floor_text(floor_payload))],
                structuredContent=floor_payload.model_dump(mode="json"),
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
            results = search_commands(str(arguments.get("query", "") or ""), descriptors=descriptors)
            payload: dict[str, object] = {"results": [result.model_dump() for result in results]}
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(payload, indent=2))],
                structuredContent=payload,
                isError=False,
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
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(envelope, indent=2))],
                structuredContent=envelope,
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
        policy = confirmation_for_tool(command_key=key, annotations=descriptor.annotations)
        route = resolve_confirm_route(
            policy=policy,
            command_key=key,
            client_supports_elicitation=_client_supports_elicitation(server),
        )
        if route in (ConfirmRoute.REFUSE_BLOCKED, ConfirmRoute.REFUSE_NO_CHANNEL):
            _telemetry_record(tool_name=name, command_key=key, route=route.value, is_error=True)
            return CallToolResult(
                content=[TextContent(type="text", text=refusal_message(route, command_key=key))],
                isError=True,
            )
        route_label = route.value
        if route is ConfirmRoute.ELICIT:
            request = confirmation_request(command_key=key)
            result = await server.request_context.session.elicit(
                message=request.message,
                requestedSchema=request.requested_schema,
            )
            decision = decision_from_elicitation(
                action=str(result.action),
                content=dict(result.content) if result.content else None,
            )
            route_label = f"{route.value}:{decision.value}"
            if decision is not ConfirmDecision.PROCEED:
                _telemetry_record(tool_name=name, command_key=key, route=route_label, is_error=True)
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
            _telemetry_record(
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
        envelope, is_error = _run_subprocess_tool(descriptor, arguments)
        envelope_json = json.dumps(envelope, ensure_ascii=False, sort_keys=True)
        window.record(envelope_json)
        _telemetry_record(
            tool_name=name,
            command_key=key,
            route=route_label,
            is_error=is_error,
            duration_ms=int((time.monotonic() - started) * 1000),
            arguments_text=arguments_json,
            result_text=envelope_json,
        )
        content: list[ContentBlock] = []
        if not faith.faithful:
            content.append(TextContent(type="text", text=advisory_line(faith)))
        content.append(TextContent(type="text", text=json.dumps(envelope, indent=2)))
        return CallToolResult(content=content, structuredContent=envelope, isError=is_error)

    # Guided-workflow prompt channel (ADR R4): the slash-command surface a client
    # renders for the USER. The catalogue and each prompt's embedded skill (plus
    # the operating rules for orientation) are derived from the shipped harness in
    # ``_prompts.py``; ``get`` returns the operating brief as a user message
    # followed by each embedded document as an ``EmbeddedResource``.
    @server.list_prompts()
    async def _list_prompts() -> list[Prompt]:
        return [
            Prompt(name=entry.name, title=entry.title, description=entry.description, arguments=[])
            for entry in build_prompt_catalogue()
        ]

    @server.get_prompt()
    async def _get_prompt(name: str, arguments: dict[str, str] | None = None) -> GetPromptResult:
        try:
            document = prompt_document(name)
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

    # Operating-layer resource channel (ADR R4): the concrete ``aeat://`` resource
    # set and the three ``aeat://<kind>/{name}`` templates are derived from the
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

    @server.read_resource()
    async def _read_resource(uri: AnyUrl) -> list[ReadResourceContents]:
        try:
            content = read_harness_resource(str(uri))
        except HarnessResourceNotFoundError as exc:
            raise ValueError(str(exc)) from exc
        return [ReadResourceContents(content=content.text, mime_type=content.ref.mime_type)]

    return server


def _run_server(
    descriptors: tuple[McpToolDescriptor, ...],
    *,
    persona: AgentPersona | None = None,
) -> None:  # pragma: no cover - requires the SDK runtime
    """Build and run the MCP stdio server from the tool descriptors.

    Exercised only when the ``aeat[agent]`` extra is installed; the descriptor,
    annotation, dispatch, block, and capability-registration logic it composes are
    unit-tested without the stdio transport via :func:`build_server`.
    """
    import anyio
    from mcp.server.stdio import stdio_server

    telemetry = SessionTelemetryWriter(session_id=f"mcp-{uuid.uuid4().hex[:12]}")
    server: Server = build_server(descriptors, persona=persona, telemetry=telemetry)

    async def _amain() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    anyio.run(_amain)
