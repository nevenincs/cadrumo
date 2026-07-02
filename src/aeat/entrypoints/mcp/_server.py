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
resolver. The ``prompts`` capability stays registered empty until W02.P04 (S14)
populates it from ``_prompts.py``. :func:`build_server` owns that registration
and is unit-tested against the real SDK without the stdio transport.

Per D1 of ``2026-07-01-agent-harness-adr``, the server also enforces the
persona-scoped tool boundary declared in ``_persona_scope.py``:
:func:`serve` resolves the active persona once, at startup, from the
``AEAT_MCP_PERSONA`` environment variable via
:func:`~aeat.entrypoints.mcp._persona_scope.active_persona`. When a persona is
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

from ._dispatch import command_key_for_tool
from ._harness_tools import (
    HARNESS_LOAD_TOOL,
    build_harness_floor_payload,
    build_harness_floor_tool,
    render_harness_floor_text,
)
from ._hitl import ConfirmationPolicy, confirmation_for_tool
from ._input_schema import cli_argv_for
from ._meta_tools import meta_execute, search_commands
from ._persona_scope import AgentPersona, active_persona, is_tool_in_persona_scope
from ._resources import (
    HarnessResourceNotFoundError,
    list_harness_resource_templates,
    list_harness_resources,
    read_harness_resource,
)
from ._tools import McpToolDescriptor, build_tool_descriptors

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
    :func:`~aeat.entrypoints.mcp._persona_scope.active_persona` error
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
    :func:`~aeat.entrypoints.mcp._hitl.confirmation_for_tool` so an
    out-of-scope call is refused before HITL policy is even consulted.
    """
    if persona is None:
        return None
    if is_tool_in_persona_scope(persona=persona, command_key=command_key):
        return None
    return f"refused: {command_key!r} is outside the active persona {persona.value!r}'s tool scope"


def build_sdk_tools(descriptors: tuple[McpToolDescriptor, ...]) -> list[object]:
    """Adapt the SDK-independent descriptors into MCP SDK ``Tool`` objects.

    Lazily imports the SDK types so the module still imports (and ``serve`` still
    refuses gracefully) when the ``aeat[agent]`` extra is absent. Exposed at module
    level so the adaptation - including the mutability-to-annotation projection -
    is unit-tested against the real SDK types when they are installed.
    """
    from mcp.types import Tool, ToolAnnotations

    tools: list[object] = []
    for descriptor in descriptors:
        annotations = descriptor.annotations
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
    """
    argv = ["aeat", *cli_argv_for(descriptor.verb_schema, arguments)]
    completed = subprocess.run(argv, capture_output=True, text=True, check=False)  # noqa: S603
    raw = completed.stdout.strip() or completed.stderr.strip()
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        return ({"status": "error", "raw": raw}, True)
    is_error = envelope.get("status") == "error" or completed.returncode != 0
    return (envelope, is_error)


def build_meta_sdk_tools() -> list[object]:
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


def build_server(
    descriptors: tuple[McpToolDescriptor, ...],
    *,
    persona: AgentPersona | None = None,
) -> object:
    """Build the MCP ``Server`` with the tool, prompt, and resource handlers.

    Registers the persona-scoped per-verb tools plus the ``search`` / ``execute``
    meta-tools, and empty-but-valid prompt and resource handlers so the server
    advertises the ``prompts`` and ``resources`` capabilities during negotiation -
    W02 populates the handler bodies. Extracted from the stdio runner so the
    handler registration and capability negotiation are unit-tested against the
    real SDK. ``persona`` scopes the per-verb tool list and the direct call-tool
    refusal per D1; the meta-tools are always advertised and ``execute`` applies
    the persona gate internally.

    Returns:
        The configured :class:`mcp.server.Server`.
    """
    from mcp.server import Server
    from mcp.server.lowlevel.helper_types import ReadResourceContents
    from mcp.types import (
        CallToolResult,
        GetPromptResult,
        Prompt,
        Resource,
        ResourceTemplate,
        TextContent,
        Tool,
    )
    from pydantic import AnyUrl

    scoped_descriptors = filter_descriptors_for_persona(descriptors, persona=persona)
    by_name = {descriptor.name: descriptor for descriptor in descriptors}
    sdk_tools = build_sdk_tools(scoped_descriptors)
    meta_tools = build_meta_sdk_tools()
    floor_tool = build_harness_floor_tool()

    server: Server = Server(_SERVER_NAME)

    @server.list_tools()
    async def _list_tools() -> list[Tool]:
        # TYPE-IGNORE-RATIONALE-SDK-TOOL-LIST: build_sdk_tools / build_meta_sdk_tools /
        # build_harness_floor_tool return the MCP SDK's real Tool type; the stub
        # package this module type-checks against declares a narrower parameter type.
        # The harness.load floor tool is advertised first and is never persona-scoped
        # away: per ADR R4 it is the universal operating-layer channel that must reach
        # any client, including a minimal tools-only one.
        return [floor_tool, *sdk_tools, *meta_tools]  # type: ignore[list-item]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, object]) -> CallToolResult:
        if name == HARNESS_LOAD_TOOL:
            floor_payload = build_harness_floor_payload(persona=persona)
            return CallToolResult(
                content=[TextContent(type="text", text=render_harness_floor_text(floor_payload))],
                structuredContent=floor_payload.model_dump(mode="json"),
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
                run=_run_subprocess_tool,
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
        if confirmation_for_tool(command_key=key, annotations=descriptor.annotations) is ConfirmationPolicy.BLOCK:
            return CallToolResult(
                content=[TextContent(type="text", text="refused: AEAT live-write is permanently forbidden")],
                isError=True,
            )
        envelope, is_error = _run_subprocess_tool(descriptor, arguments)
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(envelope, indent=2))],
            structuredContent=envelope,
            isError=is_error,
        )

    # Empty-but-valid prompt handlers: registering them makes the server
    # advertise the ``prompts`` capability during negotiation; W02.P04 (S14)
    # populates their bodies from ``_prompts.py``. Registering an empty ``list``
    # and a not-found ``get`` is the minimal valid surface until then.
    @server.list_prompts()
    async def _list_prompts() -> list[Prompt]:
        return []

    @server.get_prompt()
    async def _get_prompt(name: str, arguments: dict[str, str] | None = None) -> GetPromptResult:
        raise ValueError(f"unknown prompt: {name}")

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
    from mcp.server import Server
    from mcp.server.stdio import stdio_server

    server: Server = build_server(descriptors, persona=persona)  # type: ignore[assignment]

    async def _amain() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    anyio.run(_amain)
