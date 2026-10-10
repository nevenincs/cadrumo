"""The MCP adapter against the real runtime: it works under the person's sign-in and stops with it.

The adapter, the installed client it opens, the native transport, the runtime,
the session authority, the profile worker and the stored sign-in are real. The
native login the runtime observes, the keychain holding the proof and the
runtime's wall clock are ports held by the test. The MCP SDK uses its memory
transport, so this is not installed-host acceptance.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID, AuthReadRequest
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.sign_in import SignInPresence
from cadrumo.application.user_profile.access_contracts import ProfileAccessStatus, SessionKind
from cadrumo.core.config import override_settings
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.operations import profile_operation_subject
from cadrumo_harness.mcp.protocol_contract import MCP_TOOL_CATALOGUE
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.runtime_admission import McpAdmission
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

from .stored_sign_in_runtime import StoredSignInRuntime, stored_sign_in_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker and protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_CLI = OperationFrontendProjection.CLI
_MCP = OperationFrontendProjection.MCP
_ONE_MCP_RESUME = [("receipt", _MCP, None)]
_READ = {"family": AUTH_READ_OPERATION_DEFINITION_ID}


def _adapter() -> RuntimeMcpAdapter:
    """An adapter started with no credential reference and no profile named."""
    return RuntimeMcpAdapter(profile_id=None, client=None, resumes_sign_in=True)


def _logins(runtime: StoredSignInRuntime) -> list[tuple[str, OperationFrontendProjection, str | None]]:
    """Every login the runtime was asked to admit, in order."""
    return [(item.method, item.frontend, item.surface) for item in runtime.profiles.logins]


def _signed_in(reply: dict[str, Any], runtime: StoredSignInRuntime) -> UUID:
    """Return the session a status reply reports as held by sign-in for the runtime's profile."""
    assert reply["outcome"] == "status" and reply["session"] == "sign_in", reply
    status = ProfileAccessStatus.model_validate_json(canonical_json_bytes(reply["status"]))
    assert status.profile_id == runtime.profile_id and status.denial is None
    assert status.grant_state is None and not status.grant_valid
    assert status.session_id is not None
    lease = runtime.lease(status.session_id)
    assert lease.kind is SessionKind.HUMAN and lease.binding == runtime.binding
    assert lease.surface is None
    return status.session_id


def _no_session(runtime: StoredSignInRuntime, denial: str) -> dict[str, object]:
    return {
        "outcome": "status",
        "profile_id": str(runtime.profile_id),
        "authenticated": False,
        "session": "none",
        "surface": "full",
        "denial": denial,
    }


@pytest.mark.anyio
async def test_with_nobody_signed_in_the_adapter_serves_its_tools_and_refuses_the_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch, signed_in=False) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        adapter = _adapter()
        try:
            async with connected_server_and_client_session(build_server(adapter)) as sdk:
                names = [tool.name for tool in (await sdk.list_tools()).tools]
                status = await sdk.call_tool("status", {})
                private = await sdk.call_tool("search", _READ)
        finally:
            await adapter.close()

        assert names == [name for name, _description, _schema in MCP_TOOL_CATALOGUE]
        assert status.is_error is False
        assert status.structured_content == _no_session(runtime, "authentication_required")
        assert private.is_error is True
        assert private.structured_content == {"outcome": "refused", "code": "authentication_required"}
        # No sign-in is stored, so there was no proof to present and the runtime admitted nobody.
        assert _logins(runtime) == []
        assert runtime.leases() == ()
        assert adapter.client is None


@pytest.mark.anyio
async def test_the_adapter_resumes_a_live_sign_in_once_and_loses_it_when_the_runtime_retires_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        stored = runtime.stored_sign_in()
        observer = runtime.connect()
        deadlines = runtime.sign_in(observer)
        assert stored is not None and deadlines.presence is SignInPresence.PRESENT
        adapter = _adapter()
        try:
            # The first call that needs the profile resumes the sign-in, and the calls after it reuse the session.
            first_id = _signed_in(await adapter.call("status", {}), runtime)
            assert adapter.admission is McpAdmission.SIGN_IN
            listed = await adapter.call("search", _READ)
            assert listed["outcome"] == "found", listed
            assert [item["definition_id"] for item in listed["operations"]] == [AUTH_READ_OPERATION_DEFINITION_ID]
            submitted = await adapter.call(
                "execute",
                {
                    "definition_id": AUTH_READ_OPERATION_DEFINITION_ID,
                    "subject_ref": profile_operation_subject(str(runtime.profile_id)),
                    "payload": AuthReadRequest(profile_id=runtime.profile_id, kind="status").model_dump(mode="json"),
                    "start": False,
                },
            )
            assert submitted["outcome"] == "submitted", submitted
            assert _logins(runtime) == _ONE_MCP_RESUME

            # Neither the resume nor the submission moved the person's deadlines or rewrote the sign-in.
            assert runtime.stored_sign_in() == stored
            assert runtime.sign_in(observer) == deadlines

            # The person, on the command line, ends the adapter's session. The sign-in itself stays.
            person = RuntimeFrontendClient(runtime.connect(), profile_id=runtime.profile_id, frontend=_CLI)
            await asyncio.to_thread(person.resume_receipt)
            await asyncio.to_thread(person.revoke_session, first_id)
            assert await asyncio.to_thread(adapter._retired.wait, 10)
            assert _logins(runtime) == [*_ONE_MCP_RESUME, ("receipt", _CLI, None)]

            # The next call that needs the profile asks the runtime once, and the runtime admits a new session.
            second_id = _signed_in(await adapter.call("status", {}), runtime)
            assert second_id != first_id
            assert _logins(runtime)[2:] == _ONE_MCP_RESUME

            # The sign-in times out: the runtime passes its deadlines and retires every session under it.
            runtime.clock.ahead = timedelta(days=2)
            assert await asyncio.to_thread(adapter._retired.wait, 10)
            assert await adapter.call("search", _READ) == {"outcome": "refused", "code": "session_expired"}
            assert adapter.client is None and adapter.admission is None
            assert _logins(runtime)[3:] == _ONE_MCP_RESUME
            # Each later call asks once more and is refused again; nothing is retried in between.
            assert await adapter.call("status", {}) == _no_session(runtime, "session_expired")
            assert _logins(runtime)[4:] == _ONE_MCP_RESUME
            assert runtime.leases() == ()
        finally:
            await adapter.close()
