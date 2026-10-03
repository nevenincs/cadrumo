"""The installed stdio executable exposes public authority before profile admission."""

from __future__ import annotations

import sys
import sysconfig
from pathlib import Path
from uuid import uuid4

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cadrumo.domain.calculations.registry.authority import bundled_authority_descriptor_path

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


@pytest.mark.anyio
async def test_installed_stdio_public_authority_and_private_admission(tmp_path: Path) -> None:
    executable = Path(sysconfig.get_path("scripts")) / ("cadrumo-mcp.exe" if sys.platform == "win32" else "cadrumo-mcp")
    assert executable.is_file(), "the installed MCP entry point is required"
    profile_id = uuid4()
    parameters = StdioServerParameters(
        command=str(executable),
        args=["--profile-id", str(profile_id)],
        cwd=tmp_path,
        env={
            "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "storage"),
            "CADRUMO_AUTHORITY_ROOT": str(bundled_authority_descriptor_path().parent),
            "PYDANTIC_DISABLE_PLUGINS": "__all__",
        },
    )
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
