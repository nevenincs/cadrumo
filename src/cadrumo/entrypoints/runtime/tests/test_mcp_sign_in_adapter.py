"""The MCP adapter against the real runtime: it works under the person's sign-in and stops with it.

The adapter, the installed client it opens, the native transport, the runtime,
the session authority, the profile worker and the stored sign-in are real. The
native login the runtime observes, the keychain holding the proof and the
runtime's wall clock are ports held by the test. The MCP SDK uses its memory
transport, so this is not installed-host acceptance.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime import runtime_credentials
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.persistence.storage.custody.sign_in_generation import SignInGenerationCustody
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID, AuthReadRequest
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.sign_in import SignInPresence
from cadrumo.application.user_profile.access_contracts import AuthorityState, ProfileAccessStatus, SessionKind
from cadrumo.application.user_profile.profile_pointer import active_profile_pointer_transaction
from cadrumo.core.bucket_pointer import resolve_active_bucket_id
from cadrumo.core.config import override_settings
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.operations import profile_operation_subject
from cadrumo.core.time.clock import now
from cadrumo_harness.mcp.protocol_contract import MCP_TOOL_CATALOGUE, sign_in_remedy
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
_PROFILE_CALL: tuple[str, dict[str, object]] = ("observe", {"observation": {}})
"""A tool that reads the profile's own operations, so it is answered only under a session."""


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


def _no_session(runtime: StoredSignInRuntime, denial: str, **facts: object) -> dict[str, object]:
    return {
        "outcome": "status",
        "profile_id": str(runtime.profile_id),
        "authenticated": False,
        "session": "none",
        "surface": "full",
        "denial": denial,
        **facts,
        "remedy": sign_in_remedy(denial),
    }


_ABSENT = {"sign_in_reason": "absent"}
"""What the command line reports beside the code when no sign-in is stored to present."""


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
                private = await sdk.call_tool(*_PROFILE_CALL)
        finally:
            await adapter.close()

        assert names == [name for name, _description, _schema in MCP_TOOL_CATALOGUE]
        assert status.is_error is False
        assert status.structured_content == _no_session(runtime, "authentication_required", **_ABSENT)
        assert private.is_error is True
        assert private.structured_content == {
            "outcome": "refused",
            "code": "authentication_required",
            **_ABSENT,
            "remedy": sign_in_remedy("authentication_required"),
        }
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
            assert await adapter.call(*_PROFILE_CALL) == {
                "outcome": "refused",
                "code": "session_expired",
                "remedy": sign_in_remedy("session_expired"),
            }
            assert adapter.client is None and adapter.admission is None
            assert _logins(runtime)[3:] == _ONE_MCP_RESUME
            # Each later call asks once more and is refused again; nothing is retried in between.
            assert await adapter.call("status", {}) == _no_session(runtime, "session_expired")
            assert _logins(runtime)[4:] == _ONE_MCP_RESUME
            assert runtime.leases() == ()
        finally:
            await adapter.close()


def _read_status_submission(runtime: StoredSignInRuntime, **options: object) -> dict[str, object]:
    """The arguments of an MCP ``execute`` of the sign-in status read for the runtime's profile."""
    return {
        "definition_id": AUTH_READ_OPERATION_DEFINITION_ID,
        "subject_ref": profile_operation_subject(str(runtime.profile_id)),
        "payload": AuthReadRequest(profile_id=runtime.profile_id, kind="status").model_dump(mode="json"),
        **options,
    }


def _sign_in_deadlines(runtime: StoredSignInRuntime) -> tuple[datetime, datetime]:
    """The idle and absolute deadlines of the stored sign-in, read from its record."""
    stored = runtime.stored_sign_in()
    assert stored is not None
    metadata = json.loads(stored)
    return datetime.fromisoformat(metadata["idle_deadline"]), datetime.fromisoformat(metadata["absolute_deadline"])


async def _sign_in_again(runtime: StoredSignInRuntime) -> None:
    """The person signs in again, which stores a new sign-in and puts its proof in the keychain."""
    await asyncio.to_thread(runtime.store_sign_in)


def _mcp_logins(runtime: StoredSignInRuntime) -> int:
    return sum(1 for _method, frontend, _surface in _logins(runtime) if frontend is _MCP)


@pytest.mark.anyio
async def test_after_the_person_signs_out_the_adapter_is_refused_until_a_new_sign_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        adapter = _adapter()
        try:
            first_id = _signed_in(await adapter.call("status", {}), runtime)

            person = RuntimeFrontendClient(runtime.connect(), profile_id=runtime.profile_id, frontend=_CLI)
            signed_out = await asyncio.to_thread(person.human_sign_out)
            assert first_id in signed_out.session_ids
            # No key was issued, so nothing is left that could admit an agent.
            assert signed_out.agent_access_remains is False
            assert runtime.stored_sign_in() is None
            assert await asyncio.to_thread(adapter._retired.wait, 10)

            # The sign-in and its proof are gone, so the adapter has nothing to present and submits nothing.
            absent = {
                "outcome": "refused",
                "code": "authentication_required",
                **_ABSENT,
                "remedy": sign_in_remedy("authentication_required"),
            }
            assert await adapter.call(*_PROFILE_CALL) == absent
            assert await adapter.call("execute", _read_status_submission(runtime)) == absent
            assert await adapter.call("status", {}) == _no_session(runtime, "authentication_required", **_ABSENT)
            assert adapter.client is None and adapter.admission is None
            assert _mcp_logins(runtime) == 1

            # Only a new sign-in lets the next call through, and it is a new session.
            await _sign_in_again(runtime)
            second_id = _signed_in(await adapter.call("status", {}), runtime)
            assert second_id != first_id
            assert _mcp_logins(runtime) == 2
            assert (await adapter.call("search", _READ))["outcome"] == "found"
        finally:
            await adapter.close()


@pytest.mark.anyio
async def test_when_the_runtime_passes_the_idle_deadline_it_ends_the_adapter_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        idle, absolute = _sign_in_deadlines(runtime)
        # Only the idle deadline is passed: the absolute cap is hours further on.
        assert idle + timedelta(minutes=1) < absolute
        adapter = _adapter()
        try:
            assert _signed_in(await adapter.call("status", {}), runtime)
            runtime.clock.ahead = idle - now() + timedelta(minutes=1)
            assert await asyncio.to_thread(adapter._retired.wait, 10)

            assert await adapter.call(*_PROFILE_CALL) == {
                "outcome": "refused",
                "code": "session_expired",
                "remedy": sign_in_remedy("session_expired"),
            }
            assert adapter.client is None and adapter.admission is None and runtime.leases() == ()
            # Each later call asks once more and is refused again: nothing the person left behind revives the session.
            assert await adapter.call("execute", _read_status_submission(runtime)) == {
                "outcome": "refused",
                "code": "session_expired",
                "remedy": sign_in_remedy("session_expired"),
            }
            assert _mcp_logins(runtime) == 3
        finally:
            await adapter.close()


@pytest.mark.anyio
async def test_a_sign_in_past_its_idle_deadline_is_retired_and_only_a_new_one_lets_the_adapter_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch, signed_in=False) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        # The person signed in a minute more than the idle window ago; the absolute cap still stands.
        runtime.store_sign_in(age=timedelta(minutes=16))
        idle, absolute = _sign_in_deadlines(runtime)
        assert idle < now() < absolute
        adapter = _adapter()
        try:
            assert await adapter.call(*_PROFILE_CALL) == {
                "outcome": "refused",
                "code": "session_expired",
                "sign_in_reason": "expired_idle",
                "remedy": sign_in_remedy("session_expired"),
            }
            # The custody that holds the sign-in found it timed out and removed it, so it is not offered again.
            assert runtime.stored_sign_in() is None
            assert await adapter.call(*_PROFILE_CALL) == {
                "outcome": "refused",
                "code": "authentication_required",
                **_ABSENT,
                "remedy": sign_in_remedy("authentication_required"),
            }
            assert _mcp_logins(runtime) == 1
            assert runtime.leases() == ()

            await _sign_in_again(runtime)
            assert _signed_in(await adapter.call("status", {}), runtime)
            assert _mcp_logins(runtime) == 2
        finally:
            await adapter.close()


@pytest.mark.anyio
async def test_an_operation_submitted_and_settled_through_mcp_moves_no_deadline_of_the_sign_in(
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
        assert deadlines.idle_deadline is not None and deadlines.absolute_deadline is not None
        adapter = _adapter()
        try:
            opened = await adapter.call("status", {})
            session_id = _signed_in(opened, runtime)
            expires_at = runtime.lease(session_id).expires_at
            assert expires_at == min(deadlines.idle_deadline, deadlines.absolute_deadline)

            submitted = await adapter.call("execute", _read_status_submission(runtime))
            assert submitted["outcome"] == "submitted", submitted
            assert submitted["start"]["kind"] == "operation_acknowledged", submitted
            observation = {"operation_id": submitted["receipt"]["operation_id"], "after_cursor": 0, "page_limit": 20}
            async with asyncio.timeout(60):
                while True:
                    observed = await adapter.call("observe", {"observation": observation})
                    projection = observed["reply"]["observation"]["projection"]
                    if projection["lifecycle"] == "terminal":
                        break
                    await asyncio.sleep(0.2)
            # The operation ran to its end under the session, and left every deadline where it was.
            assert projection["terminal_condition"] == "succeeded", projection
            assert runtime.stored_sign_in() == stored
            assert runtime.sign_in(observer) == deadlines
            assert runtime.lease(session_id).expires_at == expires_at
            assert (await adapter.call("status", {}))["status"] == opened["status"]
            assert _mcp_logins(runtime) == 1
        finally:
            await adapter.close()


@pytest.mark.anyio
async def test_a_proof_the_runtime_finds_no_sign_in_for_is_refused_and_nothing_is_submitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        # The person's sign-out elsewhere fenced the sign-in's generation. The record and its proof are still
        # here for the adapter to present, and the runtime is the one to find that they no longer count.
        SignInGenerationCustody(root=runtime.root, binding=runtime.binding).advance()
        adapter = _adapter()
        try:
            assert await adapter.call("execute", _read_status_submission(runtime)) == {
                "outcome": "refused",
                "code": "authentication_required",
                "sign_in_reason": "absent",
                "sign_in_binding": "generation_changed",
                "remedy": sign_in_remedy("authentication_required"),
            }
            absent = {
                "outcome": "refused",
                "code": "authentication_required",
                **_ABSENT,
                "remedy": sign_in_remedy("authentication_required"),
            }
            assert await adapter.call(*_PROFILE_CALL) == absent
            assert await adapter.call("status", {}) == _no_session(runtime, "authentication_required", **_ABSENT)
            # The runtime was asked once and removed the record it refused, so the later calls had nothing to present.
            assert _logins(runtime) == [("receipt", _MCP, None)]
            assert runtime.stored_sign_in() is None
            assert runtime.leases() == ()
            assert adapter.client is None and adapter.admission is None
        finally:
            await adapter.close()


@pytest.mark.anyio
async def test_with_no_profile_selected_only_the_tool_list_and_status_answer_and_the_runtime_is_not_asked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        active_profile_pointer_transaction(runtime.root) as pointer,
        override_settings(cadrumo_active_profile=None),
    ):
        pointer.clear()
        assert resolve_active_bucket_id() is None
        adapter = _adapter()
        try:
            async with connected_server_and_client_session(build_server(adapter)) as sdk:
                names = [tool.name for tool in (await sdk.list_tools()).tools]
                support = await sdk.call_tool("authority", {"query": "support"})
                status = await sdk.call_tool("status", {})
                private = await sdk.call_tool(*_PROFILE_CALL)
        finally:
            await adapter.close()

        assert names == [name for name, _description, _schema in MCP_TOOL_CATALOGUE]
        assert support.is_error is True
        assert support.structured_content == {
            "outcome": "refused",
            "code": "authentication_required",
            "remedy": sign_in_remedy("authentication_required"),
        }
        assert status.is_error is False
        assert status.structured_content == {
            "outcome": "status",
            "profile_id": None,
            "authenticated": False,
            "session": "none",
            "surface": "full",
            "denial": "authentication_required",
            "remedy": sign_in_remedy("authentication_required"),
        }
        assert private.structured_content == {
            "outcome": "refused",
            "code": "authentication_required",
            "remedy": sign_in_remedy("authentication_required"),
        }
        # A sign-in is stored, and still nothing resumed it: there was no profile to resume it for.
        assert runtime.stored_sign_in() is not None
        assert _logins(runtime) == [] and runtime.leases() == ()
        assert adapter.client is None


@pytest.mark.anyio
@pytest.mark.parametrize("signed_in", [False, True], ids=["nobody-signed-in", "a-sign-in-is-stored"])
async def test_an_adapter_started_with_a_credential_reference_authenticates_with_the_configured_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, signed_in: bool
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch, signed_in=signed_in) as runtime:
        subject = runtime.enrollment
        request_id = uuid4()
        subject.service.request(request_id, subject.proposal)
        subject.approve(request_id)
        enrolled = next(item for item in subject.store.enrollment_state().requests if item.request_id == request_id)
        assert enrolled.credential_reference is not None
        # The key the client holds for the reference lives in the client's native store, not in this keychain.
        monkeypatch.setattr(runtime_credentials, "installed_automation_secret_store", lambda: subject.client_native)
        adapter = RuntimeMcpAdapter(profile_id=runtime.profile_id, client=None)
        try:
            with override_settings(cadrumo_active_profile=str(runtime.profile_id)):
                # The launch configuration names the key, as serve does; no tool names one.
                await adapter.bootstrap_reference(enrolled.credential_reference)
                async with connected_server_and_client_session(build_server(adapter)) as sdk:
                    status = await sdk.call_tool("status", {})
                    listed = await sdk.call_tool("search", {})

            assert status.structured_content is not None
            assert status.structured_content["session"] == "key"
            held = ProfileAccessStatus.model_validate_json(canonical_json_bytes(status.structured_content["status"]))
            assert held.profile_id == runtime.profile_id and held.denial is None
            assert held.grant_state is AuthorityState.ACTIVE and held.grant_valid
            assert held.session_id is not None
            lease = runtime.lease(held.session_id)
            assert lease.kind is SessionKind.API_KEY and lease.binding == runtime.binding
            assert listed.is_error is False
            assert adapter.admission is McpAdmission.KEY
            # The key was the only proof presented; a stored sign-in was never resumed.
            assert _logins(runtime) == [("api_key", _MCP, None)]
        finally:
            await adapter.close()
