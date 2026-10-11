"""The MCP adapter against the real runtime: the session acts that take a secret, and the lifecycle notice.

The adapter, the installed client it opens, the native transport, the runtime,
the session authority, the profile worker and the profile's custody are real.
The native login the runtime observes, the keychain holding the proof and the
runtime's wall clock are ports held by the test. Each act is put to the
runtime through the ``session`` tool and, where the command line has the same
act, through the command line's own client beside it.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import ProfileAccessStatus, SessionKind
from cadrumo.application.user_profile.login_session import resolve_login_target
from cadrumo.application.user_profile.profile_pointer import active_profile_pointer_transaction
from cadrumo.application.user_profile.recovery_custody import enroll_profile_recovery
from cadrumo.core.bucket_pointer import resolve_active_bucket_id
from cadrumo.core.config import override_settings
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

from .stored_sign_in_runtime import StoredSignInRuntime, stored_sign_in_runtime
from .test_modelo_metadata import _issue_scoped_key

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker and protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_CLI = OperationFrontendProjection.CLI
_MCP = OperationFrontendProjection.MCP
_WRONG = "synthetic-wrong-password-9d2e"
_REPLACEMENT = "synthetic-replacement-password-51ab"
_TYPED = (PROFILE_INPUT, _WRONG, _REPLACEMENT)


def _adapter(profile_id: UUID | None = None) -> RuntimeMcpAdapter:
    """An adapter started with no credential reference, for the selected profile or a named one."""
    return RuntimeMcpAdapter(profile_id=profile_id, client=None, resumes_sign_in=True)


def _held(reply: dict[str, Any], runtime: StoredSignInRuntime, session: str) -> UUID:
    """Return the person's session a reply reports as held, admitted the way ``session`` names."""
    assert reply["session"] == session, reply
    status = ProfileAccessStatus.model_validate_json(canonical_json_bytes(reply["status"]))
    assert status.profile_id == runtime.profile_id and status.denial is None
    assert status.session_id is not None
    assert runtime.lease(status.session_id).kind is SessionKind.HUMAN
    return status.session_id


def _logins(runtime: StoredSignInRuntime) -> list[tuple[str, OperationFrontendProjection, bool]]:
    return [(item.method, item.frontend, item.persist_receipt) for item in runtime.profiles.logins]


def _holds_no_typed_text(*replies: object, records: list[logging.LogRecord]) -> None:
    """No reply and no log record repeats a text that was typed as a secret."""
    logged = "\n".join(f"{record.getMessage()} {record.__dict__!r}" for record in records)
    for text in _TYPED:
        assert text not in json.dumps(replies, default=str)
        assert text not in logged


@pytest.mark.anyio
async def test_the_password_signs_the_person_in_on_mcp_as_on_the_command_line_and_storing_asks_the_same(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch, signed_in=False) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        key = _issue_scoped_key(runtime.enrollment).decode("utf-8")
        close_active_bucket_session()
        adapter = _adapter()
        try:
            async with connected_server_and_client_session(build_server(adapter)) as sdk:
                before = await sdk.call_tool("status", {})
                presence = await sdk.call_tool("session", {"action": "sign_in_status"})
                signed_in = await sdk.call_tool("session", {"action": "sign_in", "secret": PROFILE_INPUT})
                assert signed_in.structured_content is not None
                first_id = _held(signed_in.structured_content, runtime, "typed_sign_in")
                listed = await sdk.call_tool("session", {"action": "list"})
                stored = await sdk.call_tool("session", {"action": "sign_in", "secret": PROFILE_INPUT, "store": True})
                assert stored.structured_content is not None
                second_id = _held(stored.structured_content, runtime, "typed_sign_in")
                keyed = await sdk.call_tool("session", {"action": "sign_in", "secret": key, "method": "api_key"})
                status = await sdk.call_tool("status", {})
                # The command line's own client asks the runtime for the same stored sign-in.
                asked = RuntimeFrontendClient(runtime.connect(), profile_id=runtime.profile_id, frontend=_CLI)
                kept = await asyncio.to_thread(
                    lambda: asked.login_password(bytearray(PROFILE_INPUT.encode()), persist_receipt=True)
                )
                await asyncio.to_thread(asked.lock)
                # A refused sign-in admits nobody and leaves the session already held where it was.
                held = adapter.client
                wrong = await sdk.call_tool("session", {"action": "sign_in", "secret": _WRONG})
                assert adapter.client is held and len(runtime.leases()) == 1

        finally:
            await adapter.close()

        assert before.structured_content is not None and before.structured_content["session"] == "none"
        assert _logins(runtime) == [
            ("password", _MCP, False),
            ("password", _MCP, True),
            ("api_key", _MCP, False),
            ("password", _CLI, True),
            ("password", _MCP, False),
        ]
        assert presence.structured_content is not None
        assert presence.structured_content["outcome"] == "sign_in_status"
        assert presence.structured_content["status"]["presence"] == "absent"
        assert wrong.is_error is True and wrong.structured_content is not None
        assert wrong.structured_content["outcome"] == "refused"
        assert signed_in.is_error is False and stored.is_error is False
        assert second_id != first_id
        assert listed.structured_content is not None
        assert [item["session_id"] for item in listed.structured_content["sessions"]] == [str(first_id)]
        # A sign-in that is not stored leaves none behind. One that is asks the runtime exactly what the
        # command line's login asks, and both are told the same about whether it was kept.
        assert signed_in.structured_content["sign_in"]["session_persisted"] is False
        assert signed_in.structured_content["sign_in"]["resumed"] is False
        assert kept.human_login is not None
        assert stored.structured_content["sign_in"]["session_persisted"] is kept.human_login.session_persisted
        assert keyed.is_error is False and keyed.structured_content is not None
        assert keyed.structured_content["session"] == "key"
        assert status.structured_content is not None and status.structured_content["session"] == "key"
        _holds_no_typed_text(
            wrong.structured_content,
            signed_in.structured_content,
            stored.structured_content,
            keyed.structured_content,
            key,
            records=caplog.records,
        )
        assert key not in json.dumps(keyed.structured_content)


@pytest.mark.anyio
async def test_the_password_resumes_a_locked_profile_and_then_changes_itself_through_the_session_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        adapter = _adapter()
        try:
            locked = await adapter.call("session", {"action": "deny_automation", "kind": "profile_lock"})
            assert locked["outcome"] == "denied", locked
            assert runtime.enrollment.store.profile_lock_state().globally_locked

            refused = await adapter.call("session", {"action": "resume", "secret": _WRONG})
            assert refused["outcome"] == "refused", refused
            assert runtime.enrollment.store.profile_lock_state().globally_locked
            resumed = await adapter.call("session", {"action": "resume", "secret": PROFILE_INPUT, "grants": []})

            assert resumed["outcome"] == "resumed", resumed
            assert resumed["profile_id"] == str(runtime.profile_id)
            assert resumed["lock_generation"] == locked["receipt"]["profile_lock_generation"]
            assert resumed["reactivated_grants"] == [] and resumed["session"] == "none"
            assert not runtime.enrollment.store.profile_lock_state().globally_locked

            mismatched = await adapter.call(
                "session",
                {
                    "action": "change_password",
                    "secret": PROFILE_INPUT,
                    "new_secret": _REPLACEMENT,
                    "new_secret_confirmation": _WRONG,
                },
            )
            assert mismatched["outcome"] in {"refused", "unresolved"}, mismatched
            changed = await adapter.call(
                "session",
                {
                    "action": "change_password",
                    "secret": PROFILE_INPUT,
                    "new_secret": _REPLACEMENT,
                    "new_secret_confirmation": _REPLACEMENT,
                },
            )
            assert changed["outcome"] == "password_changed", changed
            assert changed["profile_id"] == str(runtime.profile_id)
            assert changed["password_generation"] >= 2 and changed["dek_epoch_preserved"] is True
            assert changed["session"] == "none" and adapter.client is None

            new = await adapter.call("session", {"action": "sign_in", "secret": _REPLACEMENT})
            assert new["outcome"] == "signed_in", new
            _held(new, runtime, "typed_sign_in")
            old = await adapter.call("session", {"action": "sign_in", "secret": PROFILE_INPUT})
        finally:
            await adapter.close()

        assert old["outcome"] == "refused", old
        # The command line is held to the same change: the old password no longer signs in there either.
        person = RuntimeFrontendClient(runtime.connect(), profile_id=runtime.profile_id, frontend=_CLI)
        with pytest.raises(RuntimeFrontendRefusedError):
            person.login_password(bytearray(PROFILE_INPUT.encode()))
        _holds_no_typed_text(refused, resumed, mismatched, changed, old, new, records=caplog.records)


@pytest.mark.anyio
async def test_the_recovery_code_resets_the_password_through_the_session_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        handed: list[str] = []
        enroll_profile_recovery(
            profile_id=runtime.profile_id,
            current_passphrase=PROFILE_INPUT,
            root=runtime.root,
            recovery_handover=lambda enrollment: handed.append(enrollment.recovery_key.code) or handed[-1],
        )
        close_active_bucket_session()
        (code,) = handed
        new_pair = {"new_secret": _REPLACEMENT, "new_secret_confirmation": _REPLACEMENT}
        adapter = _adapter()
        try:
            incomplete = await adapter.call("session", {"action": "reset_password", "secret": code})
            reset = await adapter.call("session", {"action": "reset_password", "secret": code, **new_pair})
            new = await adapter.call("session", {"action": "sign_in", "secret": _REPLACEMENT})
            assert new["outcome"] == "signed_in", new
            _held(new, runtime, "typed_sign_in")
            # The refused attempts come last: each starts a backoff that would delay what follows it.
            old = await adapter.call("session", {"action": "sign_in", "secret": PROFILE_INPUT})
            rejected = await adapter.call("session", {"action": "reset_password", "secret": _WRONG, **new_pair})
        finally:
            await adapter.close()

        assert rejected["outcome"] == "refused" and rejected["code"] in {"recovery_code_rejected", "throttled"}
        assert incomplete == {"outcome": "refused", "code": "invalid_request"}
        assert reset["outcome"] == "password_reset", reset
        assert reset["profile_id"] == str(runtime.profile_id)
        assert reset["password_generation"] >= 2 and reset["dek_epoch_preserved"] is True
        assert reset["recovery_enrollment_retained"] is True
        # The reset fenced the sign-in that was stored under the old password.
        assert runtime.stored_sign_in() is None
        assert old["outcome"] == "refused", old
        _holds_no_typed_text(rejected, incomplete, reset, old, new, records=caplog.records)
        logged = "\n".join(record.getMessage() for record in caplog.records)
        assert code not in json.dumps([rejected, incomplete, reset, old, new]) and code not in logged


@pytest.mark.anyio
async def test_a_named_profile_is_assessed_and_deleted_through_the_session_tool_and_the_selected_one_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        label = resolve_login_target(str(runtime.profile_id)).label
        named = {"action": "delete_profile", "profile": label}
        adapter = _adapter(runtime.profile_id)
        try:
            selected = await adapter.call("session", named | {"confirm": True})
            with active_profile_pointer_transaction(runtime.root) as pointer:
                pointer.clear()
            assert resolve_active_bucket_id() is None
            unknown = await adapter.call("session", {"action": "delete_profile", "profile": "no-such-profile"})
            unnamed = await adapter.call("session", {"action": "delete_profile", "confirm": True})
            assessed = await adapter.call("session", named)
            assert resolve_login_target(str(runtime.profile_id)).label == label
            deleted = await adapter.call("session", named | {"confirm": True})
            again = await adapter.call("session", named)
        finally:
            await adapter.close()

        assert selected == {"outcome": "refused", "code": "profile_selected", "profile_id": str(runtime.profile_id)}
        assert unknown == {"outcome": "refused", "code": "unknown_profile"}
        assert unnamed == {"outcome": "refused", "code": "invalid_request"}
        assert assessed["outcome"] == "profile_assessed" and assessed["deleted"] is False, assessed
        assert assessed["profile_id"] == str(runtime.profile_id) and assessed["display_name"] == label
        assert assessed["fingerprint"]["file_count"] >= 1 and assessed["retained_record_count"] == 0
        assert deleted["outcome"] == "profile_deleted" and deleted["deleted"] is True, deleted
        assert deleted["fingerprint"] == assessed["fingerprint"] and deleted["completed_at"]
        assert again == {"outcome": "refused", "code": "unknown_profile"}


@pytest.mark.anyio
async def test_the_runtime_tells_an_mcp_connection_that_an_update_is_pending_and_the_next_result_carries_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        adapter = _adapter()
        try:
            quiet = await adapter.call("status", {})
            # The adapter's connection offered to be told, as the command line's and the terminal interface's do.
            assert len(runtime.profiles._notice_connections) == 1

            flushed = await asyncio.to_thread(runtime.profiles._notify_upgrade, time.monotonic() + 10)
            async with asyncio.timeout(10):
                while adapter._notices._notice is None:
                    await asyncio.sleep(0.05)
            first = await adapter.call("search", {"family": "auth.local-read"})
            second = await adapter.call("search", {"family": "auth.local-read"})
            status = await adapter.call("status", {})
        finally:
            await adapter.close()

        assert flushed is True
        assert "notice" not in quiet
        assert first["outcome"] == "found" and first["notice"]["event"] == "upgrade_pending", first
        assert UUID(first["notice"]["notice_id"])
        # It is told once on an ordinary result, and status repeats it while the connection is held.
        assert "notice" not in second
        assert status["notice"] == first["notice"]
        # The notice ended nothing: the session it arrived on kept working.
        assert second["outcome"] == "found" and status["session"] == "sign_in"
