"""Real-client handshake conformance floor: initialize, tools-list, one call.

The floor beneath the live subagent harness (decision record R7): a real MCP client can
initialize a session with the real server, list its tools, and round-trip one
read-only call. The primary test uses the SDK's in-process memory transport
against ``build_server`` for CI determinism; a second test spawns a true
``aeat-mcp`` server subprocess and drives it over stdio through the live harness,
proving the same round-trip over the real transport.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable

import mcp.types as mcp_types
import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect

from ....agent.eval import LiveCallTool, ScriptedPersonaDriver, run_live_session
from .._dispatch import tool_name_for_command
from .._harness_tools import HARNESS_LOAD_TOOL
from .._server import build_server
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _run[T](coro: Awaitable[T]) -> T:
    return asyncio.run(coro)  # type: ignore[arg-type]


async def _initialize_list_and_call() -> tuple[list[str], mcp_types.CallToolResult]:
    server = build_server(build_tool_descriptors())
    async with connect(server) as session:
        # The context manager performs the initialize handshake; a successful
        # tools-list proves the session negotiated and is live.
        listed = await session.list_tools()
        names = [tool.name for tool in listed.tools]
        result = await session.call_tool(tool_name_for_command("contract"), {})
        return names, result


def test_in_process_client_initializes_lists_and_round_trips_a_read_only_call() -> None:
    names, result = _run(_initialize_list_and_call())
    # tools-list carries the floor tool and the meta-tools alongside the verbs.
    assert HARNESS_LOAD_TOOL in names
    assert {"search", "execute"} <= set(names)
    assert tool_name_for_command("contract") in names
    # The read-only call round-trips a non-error envelope for the contract command.
    assert result.isError is False
    assert result.structuredContent is not None
    assert result.structuredContent.get("command") == "contract"


def test_stdio_subprocess_client_round_trips_a_read_only_call() -> None:
    descriptors = build_tool_descriptors()
    command_key_by_tool = {tool_name_for_command(d.command_key): d.command_key for d in descriptors}
    command_key_by_tool[HARNESS_LOAD_TOOL] = ""
    driver = ScriptedPersonaDriver([LiveCallTool(tool_name=HARNESS_LOAD_TOOL, arguments_json="{}")])
    trajectory = run_live_session(
        [sys.executable, "-c", "from aeat.entrypoints.mcp import main; main()"],
        persona="verifier",
        session_id="handshake-conformance",
        driver=driver,
        command_key_by_tool=command_key_by_tool,
    )
    assert len(trajectory.tool_calls) == 1
    call = trajectory.tool_calls[0]
    assert call.tool_name == HARNESS_LOAD_TOOL
    assert call.is_error is False
    # The floor tool returns the operating layer as text over the real transport.
    assert call.result_text
