"""Real-client handshake conformance floor across every advertised MCP surface.

The floor beneath the live subagent harness: a real MCP client can
initialize a session with the real server, list its resources, prompts, and tools,
and round-trip one read-only call. The primary test uses the SDK's in-process
memory transport against ``build_server`` for focused diagnostics; a second test
spawns the installed/current ``cadrumo-mcp`` executable and drives it through a
real SDK client over stdio, including orderly client and server shutdown.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Coroutine
from typing import TypedDict

import mcp.types as mcp_types
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.memory import create_connected_server_and_client_session as connect

from .._dispatch import tool_name_for_command
from .._harness_tools import HARNESS_LOAD_TOOL
from .._server import build_server
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _HandshakeObservation(TypedDict):
    server_name: str
    resource_uris: tuple[str, ...]
    template_uris: tuple[str, ...]
    prompt_names: tuple[str, ...]
    tool_names: tuple[str, ...]
    call: mcp_types.CallToolResult


def _run[T](coro: Coroutine[object, object, T]) -> T:
    return asyncio.run(coro)


async def _initialize_list_and_call() -> tuple[list[str], mcp_types.CallToolResult]:
    server = build_server(build_tool_descriptors())
    async with connect(server) as session:
        # The context manager performs the initialize handshake; a successful
        # tools-list proves the session negotiated and is live.
        listed = await session.list_tools()
        names = [tool.name for tool in listed.tools]
        result = await session.call_tool(HARNESS_LOAD_TOOL, {})
        return names, result


def test_in_process_client_initializes_lists_and_round_trips_a_read_only_call() -> None:
    names, result = _run(_initialize_list_and_call())
    # tools-list carries the floor tool and the meta-tools alongside the verbs.
    assert HARNESS_LOAD_TOOL in names
    assert {"search", "execute"} <= set(names)
    assert tool_name_for_command("contract") in names
    # The shipped read-only floor tool avoids depending on a second executable.
    assert result.isError is False
    assert result.content


async def _stdio_handshake() -> _HandshakeObservation:
    params = StdioServerParameters(
        command="cadrumo-mcp",
        env={**os.environ, "CADRUMO_MCP_PERSONA": "verifier"},
    )
    async with (
        stdio_client(params) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        initialized = await session.initialize()
        resources = await session.list_resources()
        templates = await session.list_resource_templates()
        prompts = await session.list_prompts()
        tools = await session.list_tools()
        call = await session.call_tool(HARNESS_LOAD_TOOL, {})
        return {
            "server_name": initialized.serverInfo.name,
            "resource_uris": tuple(str(item.uri) for item in resources.resources),
            "template_uris": tuple(item.uriTemplate for item in templates.resourceTemplates),
            "prompt_names": tuple(item.name for item in prompts.prompts),
            "tool_names": tuple(item.name for item in tools.tools),
            "call": call,
        }


def test_stdio_subprocess_client_proves_cadrumo_identity_and_round_trip() -> None:
    observed = _run(_stdio_handshake())
    assert observed["server_name"] == "cadrumo"

    resource_uris = observed["resource_uris"]
    template_uris = observed["template_uris"]
    prompt_names = observed["prompt_names"]
    tool_names = observed["tool_names"]
    assert isinstance(resource_uris, tuple)
    assert isinstance(template_uris, tuple)
    assert isinstance(prompt_names, tuple)
    assert isinstance(tool_names, tuple)
    assert resource_uris and all(uri.startswith("cadrumo://") for uri in resource_uris)
    assert template_uris and all(uri.startswith("cadrumo://") for uri in template_uris)
    assert "cadrumo-empezar" in prompt_names
    assert HARNESS_LOAD_TOOL in tool_names
    assert any(name.startswith("cadrumo_") for name in tool_names)

    former_identity = "aeat"
    identity_values = (str(observed["server_name"]), *resource_uris, *template_uris, *prompt_names, *tool_names)
    assert not any(former_identity in value.casefold() for value in identity_values)

    call = observed["call"]
    assert isinstance(call, mcp_types.CallToolResult)
    assert call.isError is False
    assert call.content
