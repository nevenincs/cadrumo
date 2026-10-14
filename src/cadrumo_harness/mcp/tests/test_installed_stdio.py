"""The installed stdio executable answers its tool list and status, and nothing else, before anyone is admitted.

No runtime serves the storage root these tests give the server, and nobody is
signed in. An agent works only inside the profile the person signed in to, so
reference data, discovery and the profile's operations are all refused, each
with the remedy that tells the agent to ask the person to sign in to Cadrumo.
"""

from __future__ import annotations

import sys
import sysconfig
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from mcp import ClientSession
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import LATEST_PROTOCOL_VERSION

from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.domain.calculations.registry.authority_location import bundled_authority_descriptor_path

from ..protocol_contract import SIGN_IN_REMEDY
from ..surfaces import MCP_SURFACES, McpSurfaceName

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_PROFILE_CALL: tuple[str, dict[str, object]] = ("observe", {"observation": {}})
"""A tool that reads the profile's own operations, so it is answered only under a session."""


def _installed_server(tmp_path: Path, profile_id: UUID, *arguments: str) -> StdioServerParameters:
    executable = Path(sysconfig.get_path("scripts")) / ("cadrumo-mcp.exe" if sys.platform == "win32" else "cadrumo-mcp")
    assert executable.is_file(), "the installed MCP entry point is required"
    return StdioServerParameters(
        command=str(executable),
        args=["--profile-id", str(profile_id), *arguments],
        cwd=tmp_path,
        env={
            "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "storage"),
            "CADRUMO_AUTHORITY_ROOT": str(bundled_authority_descriptor_path().parent),
            "PYDANTIC_DISABLE_PLUGINS": "__all__",
        },
    )


_UNADMITTED: tuple[tuple[str, dict[str, object]], ...] = (
    _PROFILE_CALL,
    ("authority", {"query": "auth_providers"}),
    ("corpus_search", {"query": "iva"}),
    ("search", {"query": AUTH_READ_OPERATION_DEFINITION_ID, "limit": 3}),
    ("describe", {"definition_id": AUTH_READ_OPERATION_DEFINITION_ID}),
)
"""Every kind of call but status: none of them answers without a session."""

_REMOVED_TOOLS = frozenset(
    {"session", "installation", "authenticate", "authorization_prepare", "authorization_request", "authorization_poll"}
)


def _status_without_a_session(profile_id: UUID) -> dict[str, object]:
    return {
        "outcome": "status",
        "profile_id": str(profile_id),
        "authenticated": False,
        "session": "none",
        "surface": "full",
        "denial": "authentication_required",
        "remedy": SIGN_IN_REMEDY,
    }


@pytest.mark.anyio
async def test_installed_stdio_serves_a_client_that_never_sends_the_handshake(tmp_path: Path) -> None:
    profile_id = uuid4()
    # The child's stderr goes to a real file: a captured stream has no descriptor to hand to a process.
    with (tmp_path / "server.stderr").open("w", encoding="utf-8") as error_log:
        transport = stdio_client(_installed_server(tmp_path, profile_id), errlog=error_log)
        async with Client(transport, read_timeout_seconds=45, cache=None) as client:
            # The client asked what the server speaks and adopted it; no initialize was sent.
            assert client.session.initialize_result is None
            assert client.session.protocol_version == LATEST_PROTOCOL_VERSION
            tools = (await client.list_tools()).tools
            status = await client.call_tool("status", {})
            refused = [await client.call_tool(name, arguments) for name, arguments in _UNADMITTED]

    names = {tool.name for tool in tools}
    assert {"status", "execute", "authority", "search"} <= names
    assert not names & _REMOVED_TOOLS
    assert all(tool.annotations is not None for tool in tools)
    assert status.is_error is False
    assert status.structured_content == _status_without_a_session(profile_id)
    for (name, _arguments), answer in zip(_UNADMITTED, refused, strict=True):
        assert answer.is_error is True, name
        assert answer.structured_content == {
            "outcome": "refused",
            "code": "authentication_required",
            "remedy": SIGN_IN_REMEDY,
        }, name


@pytest.mark.anyio
async def test_installed_stdio_answers_a_handshaking_client_the_same_way(tmp_path: Path) -> None:
    profile_id = uuid4()
    with (tmp_path / "server.stderr").open("w", encoding="utf-8") as error_log:
        async with (
            stdio_client(_installed_server(tmp_path, profile_id), errlog=error_log) as (reader, writer),
            ClientSession(reader, writer, read_timeout_seconds=45) as client,
        ):
            await client.initialize()
            status = await client.call_tool("status", {})
            authority = await client.call_tool(
                "authority", {"query": "describe", "modelo": "100", "filing_year": 2024, "period": "0A"}
            )
            removed = [await client.call_tool(name, {}) for name in sorted(_REMOVED_TOOLS)]

    assert status.is_error is False
    assert status.structured_content == _status_without_a_session(profile_id)
    assert authority.is_error is True
    assert authority.structured_content == {
        "outcome": "refused",
        "code": "authentication_required",
        "remedy": SIGN_IN_REMEDY,
    }
    for answer in removed:
        assert answer.is_error is True
        assert answer.structured_content == {"outcome": "refused", "code": "unknown_tool"}


@pytest.mark.anyio
async def test_installed_stdio_on_a_narrowed_surface_lists_its_tools_and_answers_nothing_else_without_a_session(
    tmp_path: Path,
) -> None:
    surface = MCP_SURFACES[McpSurfaceName.READ_ONLY_LOCAL]
    with (tmp_path / "server.stderr").open("w", encoding="utf-8") as error_log:
        transport = stdio_client(
            _installed_server(tmp_path, uuid4(), "--surface", surface.name.value), errlog=error_log
        )
        async with Client(transport, read_timeout_seconds=45, cache=None) as client:
            names = {tool.name for tool in (await client.list_tools()).tools}
            found = await client.call_tool("search", {"limit": 100})

    assert names == surface.tools
    assert found.is_error is True
    assert found.structured_content == {
        "outcome": "refused",
        "code": "authentication_required",
        "remedy": SIGN_IN_REMEDY,
    }
