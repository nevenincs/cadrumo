"""MCP SDK transport wiring for the client-owned runtime adapter."""

from __future__ import annotations

import json
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

import anyio

from cadrumo.application.operations.mcp_surfaces import DEFAULT_MCP_SURFACE, MCP_SURFACES, McpSurface
from cadrumo.domain.calculations.registry.authority import release_bundled_indexed_authority

from .protocol_contract import (
    MCP_TOOL_HINTS,
    UNKNOWN_OUTCOME_MEMBER,
    has_refusal,
    tool_catalogue,
    unknown_outcome_instruction,
)

if TYPE_CHECKING:
    from mcp.server import Server

    from .runtime_adapter import RuntimeMcpAdapter


def build_server(adapter: RuntimeMcpAdapter) -> Server:
    """Register the tools of the adapter's surface around one connection-owned adapter."""
    from mcp.server import Server
    from mcp.types import (
        CallToolRequestParams,
        CallToolResult,
        ListToolsResult,
        TextContent,
        Tool,
        ToolAnnotations,
    )

    from .installation_acts import installation_acts_on

    # The installation tool offers only the acts the surface allows; the adapter refuses the others.
    catalogue = tool_catalogue(installation_acts_on(adapter.surface))

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
                for name, description, schema in catalogue
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

    With a credential reference the adapter authenticates by that enrolled key
    for the named profile and never resumes a sign-in. Without one it starts
    with no session, and asks the runtime to resume the person's sign-in when
    a call first needs the profile.
    """
    from mcp.server.lowlevel import NotificationOptions
    from mcp.server.stdio import stdio_server

    async def run() -> None:
        from .runtime_adapter import RuntimeMcpAdapter

        adapter = RuntimeMcpAdapter(
            profile_id=profile_id, client=None, surface=surface, resumes_sign_in=credential_reference is None
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

    with _resume_composition(resumes_sign_in=credential_reference is None):
        _serve_until_orderly_shutdown(lambda: anyio.run(run))


@contextmanager
def _resume_composition(*, resumes_sign_in: bool) -> Generator[None]:
    """Bind, for the life of the process, the ports a resumed sign-in reads its receipt through.

    The proof a resume presents is read through the login-session port, which
    the command line and the terminal interface bind before they present it.
    This process is a root of its own and binds the same composition, so the
    resume reaches the runtime instead of failing here. A connection that
    serves an enrolled key presents no receipt and binds nothing.
    """
    if not resumes_sign_in:
        yield
        return
    from cadrumo.adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports

    with composed_profile_persistence_ports():
        yield


def _serve_until_orderly_shutdown(serve_transport: Callable[[], object]) -> None:
    """Release shared authority only after the stdio transport returns normally."""
    serve_transport()
    release_bundled_indexed_authority()
