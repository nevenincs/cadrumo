"""The installed stdio executable exposes public authority before profile admission."""

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

from cadrumo.domain.calculations.registry.authority_location import bundled_authority_descriptor_path

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def _installed_server(tmp_path: Path, profile_id: UUID) -> StdioServerParameters:
    executable = Path(sysconfig.get_path("scripts")) / ("cadrumo-mcp.exe" if sys.platform == "win32" else "cadrumo-mcp")
    assert executable.is_file(), "the installed MCP entry point is required"
    return StdioServerParameters(
        command=str(executable),
        args=["--profile-id", str(profile_id)],
        cwd=tmp_path,
        env={
            "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "storage"),
            "CADRUMO_AUTHORITY_ROOT": str(bundled_authority_descriptor_path().parent),
            "PYDANTIC_DISABLE_PLUGINS": "__all__",
        },
    )


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
            private = await client.call_tool("search", {})
            authority = await client.call_tool("authority", {"query": "auth_providers"})

    assert {"status", "execute", "session", "installation"} <= {tool.name for tool in tools}
    assert all(tool.annotations is not None for tool in tools)
    assert status.is_error is False
    assert status.structured_content == {
        "outcome": "status",
        "profile_id": str(profile_id),
        "authenticated": False,
        "session": "none",
        "surface": "full",
        "denial": "authentication_required",
    }
    assert private.is_error is True
    assert private.structured_content == {"outcome": "refused", "code": "authentication_required"}
    assert authority.is_error is False and authority.structured_content["outcome"] == "published"


@pytest.mark.anyio
async def test_installed_stdio_public_authority_and_private_admission(tmp_path: Path) -> None:
    profile_id = uuid4()
    parameters = _installed_server(tmp_path, profile_id)
    with (tmp_path / "server.stderr").open("w", encoding="utf-8") as error_log:
        async with (
            stdio_client(parameters, errlog=error_log) as (reader, writer),
            ClientSession(reader, writer, read_timeout_seconds=45) as client,
        ):
            await client.initialize()
            status = await client.call_tool("status", {})
            assert status.is_error is False
            assert status.structured_content == {
                "outcome": "status",
                "profile_id": str(profile_id),
                "authenticated": False,
                "session": "none",
                "surface": "full",
                "denial": "authentication_required",
            }
            private = await client.call_tool("search", {})
            assert private.is_error is True
            assert private.structured_content == {"outcome": "refused", "code": "authentication_required"}
            authority = await client.call_tool(
                "authority", {"query": "describe", "modelo": "100", "filing_year": 2024, "period": "0A"}
            )
            assert authority.is_error is False
            document = authority.structured_content
            assert document is not None
            assert document["outcome"] == "published"
            assert document["report"]["authority_grade"] == "filing"
            assert document["report"]["filing_year"] == 2024
            assert document["logical_generation"]
            assert document["reader_incarnation"]
