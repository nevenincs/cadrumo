"""MCP SDK transport wiring for the client-owned runtime adapter."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

import anyio

from cadrumo.domain.calculations.registry.authority import release_bundled_indexed_authority

from .protocol_contract import MCP_TOOL_CATALOGUE, has_refusal

if TYPE_CHECKING:
    from mcp.server import Server

    from .runtime_adapter import RuntimeMcpAdapter


def build_server(adapter: RuntimeMcpAdapter) -> Server:
    """Register the stable protocol surface around one connection-owned adapter."""
    from mcp.server import Server
    from mcp.types import CallToolRequestParams, CallToolResult, ListToolsResult, TextContent, Tool

    async def list_tools(_context: object, _params: object) -> ListToolsResult:
        return ListToolsResult(
            tools=[
                Tool(name=name, description=description, input_schema=cast(dict[str, Any], schema))
                for name, description, schema in MCP_TOOL_CATALOGUE
            ]
        )

    async def call_tool(_context: object, params: CallToolRequestParams) -> CallToolResult:
        result = await adapter.call(params.name, params.arguments or {})
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(result, ensure_ascii=False, separators=(",", ":")))],
            structured_content=result,
            is_error=has_refusal(result),
        )

    return Server("cadrumo", on_list_tools=list_tools, on_call_tool=call_tool)


def serve(*, profile_id: UUID, credential_reference: UUID | None = None) -> None:
    """Run one stdio adapter; EOF closes its lease, never the shared runtime."""
    from mcp.server.lowlevel import NotificationOptions
    from mcp.server.stdio import stdio_server

    async def run() -> None:
        from .runtime_adapter import RuntimeMcpAdapter

        adapter = RuntimeMcpAdapter(profile_id=profile_id, client=None)
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
