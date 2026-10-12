"""The MCP adapter against the real runtime: session acts and a typed secret, as the command line has them.

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
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID, AuthReadRequest
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import AuthorityState, ProfileAccessStatus, SessionKind
from cadrumo.application.user_profile.bundle_export_contracts import ProfileBundleExportPurpose
from cadrumo.application.user_profile.profile_operation_contracts import (
    PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
    ProfileBundleExportOperationRequest,
)
from cadrumo.core.config import override_settings
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
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
_TYPED = "synthetic-bundle-export-text-41c7"


def _adapter() -> RuntimeMcpAdapter:
    """An adapter started with no credential reference and no profile named."""
    return RuntimeMcpAdapter(profile_id=None, client=None, resumes_sign_in=True)


def _signed_in(reply: dict[str, Any], runtime: StoredSignInRuntime) -> UUID:
    """Return the session a status reply reports as held by sign-in for the runtime's profile."""
    assert reply["outcome"] == "status" and reply["session"] == "sign_in", reply
    status = ProfileAccessStatus.model_validate_json(canonical_json_bytes(reply["status"]))
    assert status.profile_id == runtime.profile_id and status.denial is None
    assert status.session_id is not None
    assert runtime.lease(status.session_id).kind is SessionKind.HUMAN
    return status.session_id


async def _person(runtime: StoredSignInRuntime) -> tuple[RuntimeFrontendClient, UUID]:
    """The person's own session on the command line, resumed from the same stored sign-in."""
    person = RuntimeFrontendClient(runtime.connect(), profile_id=runtime.profile_id, frontend=_CLI)
    await asyncio.to_thread(person.resume_receipt)
    return person, person.session_id


@pytest.mark.anyio
async def test_the_session_tool_lists_and_locks_sessions_as_the_command_line_does(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        stored = runtime.stored_sign_in()
        adapter = _adapter()
        try:
            own_id = _signed_in(await adapter.call("status", {}), runtime)
            person, person_id = await _person(runtime)

            listed = await adapter.call("session", {"action": "list"})
            on_the_command_line = await asyncio.to_thread(person.sessions)

            # The inventory is the one the command line reads, session for session.
            assert listed["outcome"] == "sessions" and listed["session"] == "sign_in", listed
            assert {item["session_id"] for item in listed["sessions"]} == {str(own_id), str(person_id)}
            assert sorted(listed["sessions"], key=lambda item: item["session_id"]) == sorted(
                (json.loads(item.model_dump_json()) for item in on_the_command_line),
                key=lambda item: item["session_id"],
            )

            locked = await adapter.call("session", {"action": "lock", "target_session_id": str(person_id)})
            assert locked == {
                "outcome": "locked",
                "session": "sign_in",
                "target_session_id": str(person_id),
                "session_ids": [str(person_id)],
            }
            assert {item.session_id for item in runtime.leases()} == {own_id}
            assert adapter.client is not None

            own = await adapter.call("session", {"action": "lock"})
            assert own == {
                "outcome": "locked",
                "session": "none",
                "target_session_id": str(own_id),
                "session_ids": [str(own_id)],
            }
            # The adapter dropped the lease it ended, and no lock touched the stored sign-in.
            assert adapter.client is None and adapter.admission is None
            assert runtime.leases() == ()
            assert runtime.stored_sign_in() == stored

            # The sign-in is still stored, so the next call resumes it to a new session.
            assert _signed_in(await adapter.call("status", {}), runtime) != own_id
        finally:
            await adapter.close()


@pytest.mark.anyio
async def test_the_session_tool_signs_the_person_out_everywhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        adapter = _adapter()
        try:
            async with connected_server_and_client_session(build_server(adapter)) as sdk:
                status = await sdk.call_tool("status", {})
                assert status.structured_content is not None
                own_id = _signed_in(status.structured_content, runtime)
                _person_client, person_id = await _person(runtime)

                signed_out = await sdk.call_tool("session", {"action": "sign_out"})
                after = await sdk.call_tool("status", {})
                listed = await sdk.call_tool("session", {"action": "list"})

            assert signed_out.is_error is False
            result = signed_out.structured_content
            assert result is not None
            assert result["outcome"] == "signed_out" and result["session"] == "none", result
            assert {str(own_id), str(person_id)} <= set(result["session_ids"])
            assert result["receipt_removed"] is True and result["keychain_removed"] is True
            # The sign-in is gone for every frontend, and the adapter holds nothing.
            assert runtime.stored_sign_in() is None and runtime.leases() == ()
            assert adapter.client is None and adapter.admission is None
            assert after.structured_content is not None
            assert after.structured_content["session"] == "none"
            assert after.structured_content["denial"] == "authentication_required"
            assert listed.is_error is True
            # No sign-in is left to present, which the reply names as the command line does.
            assert listed.structured_content == {
                "outcome": "refused",
                "code": "authentication_required",
                "sign_in_reason": "absent",
            }
        finally:
            await adapter.close()


@pytest.mark.anyio
async def test_the_session_tool_denies_all_automation_and_refuses_a_malformed_act_before_asking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        # One enrolled client holds an active grant for the denial to reach.
        subject = runtime.enrollment
        request_id = uuid4()
        subject.service.request(request_id, subject.proposal)
        subject.approve(request_id)
        assert [item.state for item in subject.store.snapshot().grants] == [AuthorityState.ACTIVE]
        adapter = _adapter()
        try:
            own_id = _signed_in(await adapter.call("status", {}), runtime)

            for malformed in (
                {"action": "deny_automation", "kind": "key"},
                {"action": "deny_automation", "kind": "all", "target_id": str(own_id)},
                {"action": "list", "target_session_id": str(own_id)},
                {"action": "sign_out", "kind": "all"},
                {"action": "lock", "target_session_id": "not-a-session"},
            ):
                assert await adapter.call("session", malformed) == {"outcome": "refused", "code": "invalid_request"}
            assert {item.session_id for item in runtime.leases()} == {own_id}
            assert [item.state for item in subject.store.snapshot().grants] == [AuthorityState.ACTIVE]

            denied = await adapter.call("session", {"action": "deny_automation", "kind": "all"})

            assert denied["outcome"] == "denied" and denied["session"] == "sign_in", denied
            assert denied["kind"] == "all" and denied["target_id"] is None
            assert denied["receipt"]["profile_id"] == str(runtime.profile_id)
            assert denied["receipt"]["access_denied"] is True
            assert AuthorityState.ACTIVE not in [item.state for item in subject.store.snapshot().grants]
            # Denying automation ended no session of the person's.
            assert {item.session_id for item in runtime.leases()} == {own_id}

            locked = await adapter.call("session", {"action": "deny_automation", "kind": "profile_lock"})

            # Locking the profile ends every session of it, and the adapter keeps no lease it ended.
            assert locked["outcome"] == "denied" and locked["session"] == "none", locked
            assert locked["receipt"]["profile_lock_generation"] is not None
            assert adapter.client is None and adapter.admission is None
            assert runtime.leases() == ()
        finally:
            await adapter.close()


@pytest.mark.anyio
async def test_a_secret_given_where_none_is_declared_or_withheld_where_one_is_required_submits_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        adapter = _adapter()
        try:
            unexpected = await adapter.call(
                "execute",
                {
                    "definition_id": AUTH_READ_OPERATION_DEFINITION_ID,
                    "payload": AuthReadRequest(profile_id=runtime.profile_id, kind="status").model_dump(mode="json"),
                    "secret": _TYPED,
                },
            )
            missing = await adapter.call(
                "execute",
                {
                    "definition_id": PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
                    "payload": ProfileBundleExportOperationRequest(
                        profile_id=runtime.profile_id,
                        destination=tmp_path / "unwritten.bundle",
                        purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER,
                    ).model_dump(mode="json"),
                },
            )
        finally:
            await adapter.close()

        assert unexpected == {
            "outcome": "refused",
            "code": "invalid_request",
            "message": "secret is not accepted: this operation's contract declares no typed secret",
        }
        assert missing == {
            "outcome": "refused",
            "code": "invalid_request",
            "message": "secret is required: this operation's contract says ephemeral_secret_required",
        }
        assert not (tmp_path / "unwritten.bundle").exists()


@pytest.mark.anyio
async def test_a_typed_secret_reaches_the_worker_through_the_execute_tool_and_the_export_settles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        destination = tmp_path / "private-transfer.bundle"
        adapter = _adapter()
        try:
            _signed_in(await adapter.call("status", {}), runtime)
            submitted = await adapter.call(
                "execute",
                {
                    "definition_id": PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
                    "payload": ProfileBundleExportOperationRequest(
                        profile_id=runtime.profile_id,
                        destination=destination,
                        purpose=ProfileBundleExportPurpose.PORTABLE_TRANSFER,
                    ).model_dump(mode="json"),
                    "secret": _TYPED,
                },
            )
            assert submitted["outcome"] == "submitted", submitted
            assert submitted["receipt"]["secret_requirement"] is not None
            assert submitted["secret_delivery"] == {"outcome": "delivered"}, submitted
            assert submitted["start"]["kind"] == "operation_acknowledged", submitted
            operation_id = submitted["receipt"]["operation_id"]
            observation = {"operation_id": operation_id, "after_cursor": 0, "page_limit": 32}
            async with asyncio.timeout(90):
                while True:
                    observed = await adapter.call("observe", {"observation": observation})
                    projection = observed["reply"]["observation"]["projection"]
                    if projection["lifecycle"] == "terminal":
                        break
                    await asyncio.sleep(0.2)
            released = await adapter.call("result", {"result": {"operation_id": operation_id}})
        finally:
            await adapter.close()

        # The worker consumed the secret the tool carried: the passphrase-encrypted export was written.
        assert projection["terminal_condition"] == "succeeded", projection
        assert destination.is_file() and destination.stat().st_size > 0
        assert released["outcome"] == "reply", released
        assert released["document"]["projection"]["profile_id"] == str(runtime.profile_id)
        assert released["document"]["projection"]["transport"] == "passphrase_encrypted"
        # No reply repeated the text, and the export does not hold it in the clear.
        for reply in (submitted, observed, released):
            assert _TYPED not in json.dumps(reply)
        assert _TYPED.encode("utf-8") not in destination.read_bytes()
