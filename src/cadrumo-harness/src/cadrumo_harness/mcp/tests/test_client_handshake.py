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

from .._dispatch import tool_name_for_command
from .._harness_tools import HARNESS_LOAD_TOOL
from .._server import build_server
from .._tools import build_tool_descriptors
from .session import connected_server_and_client_session as connect

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
    # CORE advertises the persona-scoped orientation slice only; a verb outside
    # it is discovered, not listed, and stays reachable through execute or a
    # direct call by name. The descriptor-set assertion keeps the exclusion from
    # passing vacuously were the verb to disappear from the surface entirely.
    assert tool_name_for_command("overview.status") in names
    assert tool_name_for_command("registry.inspect") not in names
    assert tool_name_for_command("registry.inspect") in {d.name for d in build_tool_descriptors()}
    # The shipped read-only floor tool avoids depending on a second executable.
    assert result.is_error is False
    assert result.content


async def _list_memory_session_output_schemas() -> dict[str, dict[str, object] | None]:
    server = build_server(build_tool_descriptors())
    async with connect(server) as session:
        listed = await session.list_tools()
        return {tool.name: tool.output_schema for tool in listed.tools}


async def _list_memory_session_input_schemas() -> dict[str, dict[str, object]]:
    server = build_server(build_tool_descriptors())
    async with connect(server) as session:
        listed = await session.list_tools()
        return {tool.name: tool.input_schema for tool in listed.tools}


def _object_schema_mapping(value: object) -> dict[str, object]:
    """Validate an SDK JSON-schema fragment before asserting its object shape."""
    assert isinstance(value, dict)
    return {str(key): item for key, item in value.items()}


def test_memory_session_tools_list_preserves_object_shaped_response_envelopes() -> None:
    # Drive the SDK's actual initialized in-memory client/server session. This
    # proves the advertised descriptor serializes through tools/list, not just
    # that the SDK-independent descriptor happens to contain the right keys.
    output_schemas = _run(_list_memory_session_output_schemas())
    schema = _object_schema_mapping(output_schemas[tool_name_for_command("overview.status")])
    assert schema["type"] == "object"
    branches = schema["oneOf"]
    assert isinstance(branches, list) and len(branches) == 2
    success_branch, error_branch = branches
    success_branch = _object_schema_mapping(success_branch)
    error_branch = _object_schema_mapping(error_branch)
    success_properties = _object_schema_mapping(success_branch["properties"])
    error_properties = _object_schema_mapping(error_branch["properties"])
    assert success_properties["command"] == {"const": "overview.status", "type": "string"}
    assert error_properties["status"] == {"const": "error", "type": "string"}


def test_memory_session_tools_list_preserves_resolver_backed_action_capabilities() -> None:
    input_schemas = _run(_list_memory_session_input_schemas())
    tool_name = tool_name_for_command("overview.status")
    schema = _object_schema_mapping(input_schemas[tool_name])
    capabilities = schema["x-cadrumo-action-capabilities"]
    descriptor = next(item for item in build_tool_descriptors() if item.name == tool_name)
    assert isinstance(capabilities, list)
    assert capabilities == descriptor.input_schema["x-cadrumo-action-capabilities"]
    assert [capability["action_id"] for capability in capabilities] == ["operator.overview.status"]


async def _stdio_handshake() -> _HandshakeObservation:
    params = StdioServerParameters(
        command="cadrumo-mcp",
        env={**os.environ, "CADRUMO_MCP_PERSONA": "cadrumo-verifier"},
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
            "server_name": initialized.server_info.name,
            "resource_uris": tuple(str(item.uri) for item in resources.resources),
            "template_uris": tuple(item.uri_template for item in templates.resource_templates),
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
    assert call.is_error is False
    assert call.content
