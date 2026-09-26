"""``config auth login`` stays reachable through the identity gate from a fresh session.

Login reaches AEAT and declares ``aeat``, so the gate refuses it until the
session has read who the active taxpayer is. That read must not itself need an
AEAT session, or login could never be reached. The console identity read
(``whoami``) is local, so the sequence below is the one an agent follows from a
fresh session.

The server runs under the offline seal: once the gate clears, dispatch reaches
the supervised-subprocess transport, which the seal refuses, so nothing is
launched and the refused child process is the evidence that the call got past
the gate.
"""

from __future__ import annotations

from typing import Any, cast

import anyio
import pytest
from mcp.types import CallToolResult, TextContent

from cadrumo.tests.offline_seal import OfflineGuard, offline_guard_fixture

from .._command_policy import command_policy
from ..dispatch import tool_name_for_command
from ..harness_tools import WHOAMI_TOOL
from ..identity_gate import SessionIdentityState, identity_gate_refusal
from ..tools import build_tool_descriptors
from .session import connected_server_and_client_session as connect

__all__ = ["offline_guard_fixture"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LOGIN_KEY = "config.auth.login"


def _text(result: CallToolResult) -> str:
    return " ".join(block.text for block in result.content if isinstance(block, TextContent))


def test_login_declares_aeat_and_is_gated_until_an_identity_read() -> None:
    assert command_policy(_LOGIN_KEY).reaches_aeat is True
    assert identity_gate_refusal(_LOGIN_KEY, state=SessionIdentityState()) is not None


def test_login_is_reachable_from_a_fresh_session_after_a_local_identity_read(offline_guard: OfflineGuard) -> None:
    from ..server import build_server

    expected_refusal = identity_gate_refusal(_LOGIN_KEY, state=SessionIdentityState())
    assert expected_refusal is not None
    login_tool = tool_name_for_command(_LOGIN_KEY)
    server = cast("Any", build_server(build_tool_descriptors(), persona=None))

    async def _drive() -> tuple[str, bool, str]:
        async with connect(server) as session:
            refused = await session.call_tool(login_tool, {})
            whoami = await session.call_tool(WHOAMI_TOOL, {})
            admitted = await session.call_tool(login_tool, {})
        return _text(refused), bool(whoami.is_error), _text(admitted)

    refused_text, whoami_failed, admitted_text = anyio.run(_drive)

    assert refused_text == expected_refusal
    assert whoami_failed is False
    assert expected_refusal not in admitted_text
    assert "child process" in offline_guard.refused, "the admitted login never reached dispatch"
