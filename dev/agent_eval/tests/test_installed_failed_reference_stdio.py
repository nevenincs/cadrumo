"""Installed stdio stays publicly reachable when OS custody cannot admit a reference."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cadrumo.adapters.persistence.storage.custody.automation_secret_store import native_automation_secret_store
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
)
from cadrumo.domain.calculations.registry.authority import bundled_authority_descriptor_path
from cadrumo.entrypoints.cli.tests.native_api_cli_support import native_api_cli_session

from .test_installed_authenticated_stdio import (
    _installed_mcp_executable,
    _native_backend_for_current_platform,
    _scope_for_auth_read,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_core,
    pytest.mark.os_keychain,
    pytest.mark.skipif(
        sys.platform not in {"win32", "linux"}, reason="installed native admission is covered on Windows/Linux"
    ),
]


def _object(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


@pytest.mark.anyio
async def test_installed_missing_reference_keeps_public_stdio_and_fences_private_tools(tmp_path: Path) -> None:
    """The selected native backend can refuse admission without ending MCP stdio."""
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=_scope_for_auth_read,
        prepare_profile=lambda _profile_id, _root: None,
    ) as profile:
        backend = _native_backend_for_current_platform()
        try:
            native_automation_secret_store(backend)
        except AutomationCustodyError as error:
            assert error.reason in {AutomationCustodyCode.UNAVAILABLE, AutomationCustodyCode.UNSUPPORTED}
            expected_denials = {error.reason.value}
        else:
            expected_denials = {AutomationCustodyCode.MISSING.value, AutomationCustodyCode.UNAVAILABLE.value}

        # The fixture's profile, owner worker, and OS-login observation are
        # synthetic controls. The installed process uses the selected native
        # platform backend for this fresh, never-written reference.
        reference = uuid4()
        executable = _installed_mcp_executable()
        assert executable.is_file(), "the installed cadrumo-mcp executable is required"
        parameters = StdioServerParameters(
            command=str(executable),
            args=["--profile-id", str(profile.profile_id), "--credential-reference", str(reference)],
            cwd=tmp_path,
            env={
                "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "cadrumo-storage"),
                "CADRUMO_AUTHORITY_ROOT": str(bundled_authority_descriptor_path().parent),
                "PYDANTIC_DISABLE_PLUGINS": "__all__",
            },
        )
        with (tmp_path / "installed-mcp-failed-reference.stderr").open("w", encoding="utf-8") as error_log:
            async with (
                stdio_client(parameters, errlog=error_log) as (reader, writer),
                ClientSession(reader, writer, read_timeout_seconds=60) as client,
            ):
                await client.initialize()
                names = {tool.name for tool in (await client.list_tools()).tools}
                assert {
                    "status",
                    "authority",
                    "authorization_prepare",
                    "authenticate",
                    "search",
                    "describe",
                    "execute",
                    "observe",
                    "result",
                    "result_page",
                } <= names

                status_call = await client.call_tool("status", {})
                assert status_call.is_error is False
                status = _object(status_call.structured_content)
                assert status["outcome"] == "status"
                assert status["profile_id"] == str(profile.profile_id)
                assert status["authenticated"] is False
                denial = status["denial"]
                assert denial in expected_denials, f"{backend.value} denial was {denial!r}"

                public = await client.call_tool("authority", {"query": "modelos"})
                assert public.is_error is False, _object(public.structured_content)
                assert _object(public.structured_content)["outcome"] == "published"
                recovery = await client.call_tool("authorization_prepare", {"credential_reference": str(reference)})
                assert recovery.is_error is True
                assert recovery.structured_content == {"outcome": "refused", "code": denial}

                for name, args in (
                    ("search", {"query": "auth.local-read"}),
                    ("describe", {"definition_id": "auth.local-read"}),
                    (
                        "execute",
                        {
                            "definition_id": "auth.local-read",
                            "subject_ref": f"profile:{profile.profile_id}",
                            "payload": {"profile_id": str(profile.profile_id), "kind": "status"},
                        },
                    ),
                    ("observe", {"observation": {}}),
                    ("result", {"result": {}}),
                    ("result_page", {"result": {}, "page": {}}),
                ):
                    private = await client.call_tool(name, args)
                    assert private.is_error is True, name
                    assert private.structured_content == {"outcome": "refused", "code": denial}, name

                retried = await client.call_tool("authenticate", {"credential_reference": str(reference)})
                assert retried.is_error is True
                assert retried.structured_content == {"outcome": "refused", "code": denial}
                after = await client.call_tool("status", {})
                assert after.structured_content == status
                assert str(reference) not in repr(after.structured_content)
