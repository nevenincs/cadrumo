"""MCP server shell: the thin protocol wiring over the SDK-independent core.

The Model Context Protocol runtime is an optional dependency behind the
``aeat[agent]`` extra. :func:`serve` imports it lazily and, when it is absent,
refuses with the install hint and a non-zero exit instead of raising a raw
``ModuleNotFoundError`` - the same graceful-degradation contract the Google,
browser, and Anthropic integrations follow. The tool list, annotations, and the
forbidden-live-write block are sourced from the SDK-independent core in this
package; ``call_tool`` runs the deterministic CLI in a subprocess and returns its
JSON envelope as structured content.
"""

from __future__ import annotations

import json
import subprocess
import sys

from ._dispatch import command_key_for_tool, tool_request_argv
from ._hitl import ConfirmationPolicy, confirmation_for_tool
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
    """Run the ``aeat-mcp`` stdio server, or refuse if the SDK is not installed."""
    try:
        import mcp.server  # noqa: F401
    except ModuleNotFoundError:
        emit_missing_sdk_refusal()
        return
    _run_server(build_tool_descriptors())


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


def _run_server(descriptors: tuple[McpToolDescriptor, ...]) -> None:  # pragma: no cover - requires the SDK runtime
    """Build and run the MCP stdio server from the tool descriptors.

    Exercised only when the ``aeat[agent]`` extra is installed; the descriptor,
    annotation, dispatch, and block logic it composes are all unit-tested without
    the SDK.
    """
    import anyio
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import CallToolResult, TextContent, Tool

    by_name = {descriptor.name: descriptor for descriptor in descriptors}
    sdk_tools = build_sdk_tools(descriptors)

    server: Server = Server(_SERVER_NAME)

    @server.list_tools()
    async def _list_tools() -> list[Tool]:
        return list(sdk_tools)  # type: ignore[arg-type]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, object]) -> CallToolResult:
        descriptor = by_name.get(name)
        if descriptor is None:
            return CallToolResult(content=[TextContent(type="text", text=f"unknown tool: {name}")], isError=True)
        key = command_key_for_tool(name, command_keys=[d.command_key for d in descriptors])
        if key is None:
            return CallToolResult(content=[TextContent(type="text", text=f"unmapped tool: {name}")], isError=True)
        if confirmation_for_tool(command_key=key, annotations=descriptor.annotations) is ConfirmationPolicy.BLOCK:
            return CallToolResult(
                content=[TextContent(type="text", text="refused: AEAT live-write is permanently forbidden")],
                isError=True,
            )
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
