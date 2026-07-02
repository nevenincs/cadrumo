"""MCP server shell: the thin protocol wiring over the SDK-independent core.

The Model Context Protocol runtime is an optional dependency behind the
``aeat[agent]`` extra. :func:`serve` imports it lazily and, when it is absent,
refuses with the install hint and a non-zero exit instead of raising a raw
``ModuleNotFoundError`` - the same graceful-degradation contract the Google,
browser, and Anthropic integrations follow. The tool list, annotations, and the
forbidden-live-write block are sourced from the SDK-independent core in this
package; ``call_tool`` runs the deterministic CLI in a subprocess and returns its
JSON envelope as structured content.

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

from ._dispatch import command_key_for_tool, tool_request_argv
from ._hitl import ConfirmationPolicy, confirmation_for_tool
from ._persona_scope import AgentPersona, active_persona, is_tool_in_persona_scope
from ._tools import McpToolDescriptor, build_tool_descriptors

_INSTALL_HINT = "the MCP server requires the agent extra: pip install 'aeat[agent]'"
_SERVER_NAME = "aeat"


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


def _run_subprocess_tool(descriptor: McpToolDescriptor, args: list[str]) -> tuple[dict[str, object], bool]:
    """Run one tool's CLI command in a subprocess and return (envelope, is_error)."""
    argv = ["aeat", *tool_request_argv(descriptor.command_key, args)]
    completed = subprocess.run(argv, capture_output=True, text=True, check=False)  # noqa: S603
    raw = completed.stdout.strip() or completed.stderr.strip()
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        return ({"status": "error", "raw": raw}, True)
    is_error = envelope.get("status") == "error" or completed.returncode != 0
    return (envelope, is_error)


def _run_server(
    descriptors: tuple[McpToolDescriptor, ...],
    *,
    persona: AgentPersona | None = None,
) -> None:  # pragma: no cover - requires the SDK runtime
    """Build and run the MCP stdio server from the tool descriptors.

    Exercised only when the ``aeat[agent]`` extra is installed; the descriptor,
    annotation, dispatch, and block logic it composes are all unit-tested without
    the SDK. ``persona`` (resolved once by :func:`serve`) scopes both the
    advertised tool list and the call-tool refusal per D1; ``None`` preserves
    the full, unscoped surface.
    """
    import anyio
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import CallToolResult, TextContent, Tool

    scoped_descriptors = filter_descriptors_for_persona(descriptors, persona=persona)
    by_name = {descriptor.name: descriptor for descriptor in descriptors}
    sdk_tools = build_sdk_tools(scoped_descriptors)

    server: Server = Server(_SERVER_NAME)

    @server.list_tools()
    async def _list_tools() -> list[Tool]:
        # TYPE-IGNORE-RATIONALE-SDK-TOOL-LIST: build_sdk_tools returns a
        # sequence of the MCP SDK's real Tool type; the stub package this
        # module type-checks against declares a narrower parameter type.
        return list(sdk_tools)  # type: ignore[arg-type]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, object]) -> CallToolResult:
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
        # TYPE-IGNORE-RATIONALE-MCP-TOOL-ARGS: ``arguments`` is the untyped
        # ``dict[str, object]`` MCP call-tool payload; ``.get("args", [])``
        # is iterated defensively and every element coerced through ``str()``.
        args = [str(value) for value in arguments.get("args", [])]  # type: ignore[union-attr]
        envelope, is_error = _run_subprocess_tool(descriptor, args)
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(envelope, indent=2))],
            structuredContent=envelope,
            isError=is_error,
        )

    async def _amain() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    anyio.run(_amain)
