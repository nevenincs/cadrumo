"""MCP SDK transport wiring for the client-owned runtime adapter."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

import anyio

from cadrumo.domain.calculations.registry.authority import release_bundled_indexed_authority

from .protocol_contract import (
    MCP_TOOL_CATALOGUE,
    MCP_TOOL_HINTS,
    UNKNOWN_OUTCOME_MEMBER,
    has_refusal,
    unknown_outcome_instruction,
)
from .surfaces import DEFAULT_MCP_SURFACE, MCP_SURFACES, McpSurface

if TYPE_CHECKING:
    from mcp.server import Server

    from .runtime_adapter import RuntimeMcpAdapter


def build_server(adapter: RuntimeMcpAdapter) -> Server:
    """Register the tools of the adapter's surface around one connection-owned adapter."""
    from mcp.server import Server
    from mcp.types import CallToolRequestParams, CallToolResult, ListToolsResult, TextContent, Tool, ToolAnnotations

    def annotations(name: str) -> ToolAnnotations:
        hints = MCP_TOOL_HINTS[name]
        return ToolAnnotations(
            title=hints.title,
            read_only_hint=hints.read_only,
            destructive_hint=hints.destructive,
            idempotent_hint=hints.idempotent,
            open_world_hint=hints.open_world,
        )

    async def list_tools(_context: object, _params: object) -> ListToolsResult:
        return ListToolsResult(
            tools=[
                Tool(
                    name=name,
                    description=description,
                    input_schema=cast(dict[str, Any], schema),
                    annotations=annotations(name),
                )
                for name, description, schema in MCP_TOOL_CATALOGUE
                if name in adapter.surface.tools
            ]
        )

    async def call_tool(_context: object, params: CallToolRequestParams) -> CallToolResult:
        result = await adapter.call(params.name, params.arguments or {})
        instruction = unknown_outcome_instruction(result)
        if instruction is not None:
            result = {**result, UNKNOWN_OUTCOME_MEMBER: instruction}
        # The text block repeats the document for a client that reads no structured content.
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(result, ensure_ascii=False, separators=(",", ":")))],
            structured_content=result,
            is_error=has_refusal(result),
        )

    return Server("cadrumo", on_list_tools=list_tools, on_call_tool=call_tool)


def serve(
    *,
    profile_id: UUID | None = None,
    credential_reference: UUID | None = None,
    surface: McpSurface = MCP_SURFACES[DEFAULT_MCP_SURFACE],
) -> None:
    """Run one stdio adapter on one surface; EOF closes its lease, never the shared runtime.

    With a credential reference, which only the person's launch configuration
    gives, the adapter authenticates by that enrolled key for the named
    profile. Without one it starts with no session and requests scoped
    attendance from the person holding the selected profile. No human receipt
    is read or presented by this external connection.
    """
    from mcp.server.lowlevel import NotificationOptions
    from mcp.server.stdio import stdio_server

    async def run() -> None:
        from .runtime_adapter import RuntimeMcpAdapter

        adapter = RuntimeMcpAdapter(
            profile_id=profile_id, client=None, surface=surface, requests_attendance=credential_reference is None
        )
        try:
            if credential_reference is not None:
                await adapter.bootstrap_reference(credential_reference)
            server = build_server(adapter)
            async with stdio_server() as (read_stream, write_stream):
                await server.run(
                    read_stream,
                    write_stream,
                    server.create_initialization_options(NotificationOptions(), experimental_capabilities={}),
                )
        finally:
            await adapter.close()

    _serve_until_orderly_shutdown(lambda: anyio.run(run))


def _serve_until_orderly_shutdown(serve_transport: Callable[[], object]) -> None:
    """Release shared authority only after the stdio transport returns normally."""
    serve_transport()
    release_bundled_indexed_authority()
