"""The installed stdio executable answers what needs no profile before anyone is admitted.

No runtime serves the storage root these tests give the server, and nobody is
signed in. The published authority and the registered operations' contracts
ship with the installed package, so both are read all the same.
"""

from __future__ import annotations

import json
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
from cadrumo.application.operations.mcp_surfaces import MCP_SURFACES, McpSurfaceName
from cadrumo.application.operations.registry import OperationPublicDefinitionDescriptionV1
from cadrumo.domain.calculations.registry.authority_location import bundled_authority_descriptor_path
from cadrumo_harness.mcp.public_operation_discovery import shipped_public_descriptions

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
            private = await client.call_tool(*_PROFILE_CALL)
            authority = await client.call_tool("authority", {"query": "auth_providers"})

    assert {"status", "execute"} <= {tool.name for tool in tools}
    assert not {"session", "installation", "authenticate"} & {tool.name for tool in tools}
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
            private = await client.call_tool(*_PROFILE_CALL)
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


def _described(document: dict[str, object]) -> OperationPublicDefinitionDescriptionV1:
    """Read a reply's description as the typed description it is the public value of."""
    return OperationPublicDefinitionDescriptionV1.model_validate_json(json.dumps(document["description"]))


@pytest.mark.anyio
async def test_installed_stdio_finds_and_describes_operations_with_no_sign_in_and_no_runtime(tmp_path: Path) -> None:
    shipped = shipped_public_descriptions()
    read = AUTH_READ_OPERATION_DEFINITION_ID
    with (tmp_path / "server.stderr").open("w", encoding="utf-8") as error_log:
        transport = stdio_client(_installed_server(tmp_path, uuid4()), errlog=error_log)
        async with Client(transport, read_timeout_seconds=45, cache=None) as client:
            unserved = await client.call_tool("installation", {"action": "profile_list"})
            status = await client.call_tool("status", {})
            ranked = await client.call_tool("search", {"query": read, "limit": 3})
            listed = await client.call_tool("search", {"family": "auth", "limit": 100})
            described = await client.call_tool("describe", {"definition_id": read})
            unregistered = await client.call_tool("describe", {"definition_id": "auth.synthetic-unregistered"})
            private = await client.call_tool("execute", {"definition_id": read, "payload": {}})

    # An act outside the profile is not served at all, and nobody is signed in.
    assert unserved.is_error is True
    assert unserved.structured_content == {"outcome": "refused", "code": "unknown_tool"}
    assert status.structured_content["authenticated"] is False
    assert ranked.is_error is False and listed.is_error is False and described.is_error is False
    assert (ranked.structured_content["outcome"], ranked.structured_content["session"]) == ("found", "none")
    assert ranked.structured_content["operations"][0]["definition_id"] == read
    family = sorted(definition_id for definition_id in shipped if definition_id.startswith("auth."))
    assert len(family) > 1
    assert [row["definition_id"] for row in listed.structured_content["operations"]] == family
    assert set(described.structured_content) == {"outcome", "description", "session"}
    assert described.structured_content["session"] == "none"
    assert _described(described.structured_content) == shipped[read]
    assert "profile_id" in described.structured_content["description"]["request_json_schema"]["properties"]
    assert unregistered.is_error is True
    assert unregistered.structured_content == {"outcome": "refused", "code": "operation_denied"}
    # Reading what an operation takes is not running it: that still needs the session.
    assert private.is_error is True
    assert private.structured_content["code"] in {"authentication_required", "runtime_unavailable"}


@pytest.mark.anyio
async def test_installed_stdio_on_a_narrowed_surface_finds_only_the_operations_that_surface_keeps(
    tmp_path: Path,
) -> None:
    surface = MCP_SURFACES[McpSurfaceName.READ_ONLY_LOCAL]
    shipped = shipped_public_descriptions()
    kept = sorted(definition_id for definition_id in shipped if surface.admits(definition_id))
    left_out = next(definition_id for definition_id in sorted(shipped) if not surface.admits(definition_id))
    assert kept, "the narrowed surface keeps no registered operation; the denominator is empty"
    listed: list[str] = []
    with (tmp_path / "server.stderr").open("w", encoding="utf-8") as error_log:
        transport = stdio_client(
            _installed_server(tmp_path, uuid4(), "--surface", surface.name.value), errlog=error_log
        )
        async with Client(transport, read_timeout_seconds=45, cache=None) as client:
            cursor: str | None = None
            while True:
                page = await client.call_tool("search", {"limit": 100} | ({} if cursor is None else {"cursor": cursor}))
                assert page.is_error is False and page.structured_content["session"] == "none"
                listed.extend(row["definition_id"] for row in page.structured_content["operations"])
                following = page.structured_content.get("next_cursor")
                assert following is None or isinstance(following, str)
                cursor = following
                if cursor is None:
                    break
            described = await client.call_tool("describe", {"definition_id": kept[0]})
            refused = await client.call_tool("describe", {"definition_id": left_out})

    assert listed == kept
    assert described.is_error is False and _described(described.structured_content) == shipped[kept[0]]
    assert refused.is_error is True
    assert refused.structured_content == {"outcome": "refused", "code": "frontend_denied"}
