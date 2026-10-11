"""The MCP adapter against the real runtime: a password the person entered at a terminal, taken by reference.

The adapter, the installed client it opens, the native transport, the runtime,
the session authority, the profile worker and the profile's custody are real,
and so is the held-secret custody that keeps what the person entered. The
credential store under that custody, the native login the runtime observes and
the keychain are ports held by the test. The same act is put to the runtime
with the password typed into the call beside it, and the runtime is asked the
same thing either way.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.config import override_settings
from cadrumo_harness.mcp import runtime_adapter as mcp_runtime
from cadrumo_harness.mcp.held_secrets import HELD_SECRET_NAMESPACE, held_secret_custody
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

from .stored_sign_in_runtime import stored_sign_in_runtime
from .test_mcp_password_session_acts import _adapter, _held, _logins

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
_LABEL = "synthetic profile password"


def _holds_no_entered_text(*replies: object, records: list[logging.LogRecord]) -> None:
    """No reply and no log record repeats a text the person entered at their terminal."""
    logged = "\n".join(f"{record.getMessage()} {record.__dict__!r}" for record in records)
    for text in (PROFILE_INPUT, _WRONG, _REPLACEMENT):
        assert text not in json.dumps(replies, default=str)
        assert text not in logged


def _held_references(store: MemoryNativePort) -> set[str]:
    return {account for namespace, account in store.items if namespace == HELD_SECRET_NAMESPACE}


@pytest.mark.anyio
async def test_a_password_entered_at_a_terminal_signs_in_by_reference_as_the_typed_one_does(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    client_store = MemoryNativePort()
    monkeypatch.setattr(mcp_runtime, "installed_automation_secret_store", lambda: client_store)
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch, signed_in=False) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        close_active_bucket_session()
        custody = held_secret_custody(client_store)
        kept = custody.hold_entered(label=_LABEL, secret=bytearray(PROFILE_INPUT, "utf-8"), single_use=False)
        once = custody.hold_entered(label=_LABEL, secret=bytearray(PROFILE_INPUT, "utf-8"), single_use=True)
        wrong = custody.hold_entered(label=_LABEL, secret=bytearray(_WRONG, "utf-8"), single_use=False)
        adapter = _adapter()
        try:
            async with connected_server_and_client_session(build_server(adapter)) as sdk:
                signed_in = await sdk.call_tool(
                    "session", {"action": "sign_in", "secret_reference": str(kept.reference)}
                )
                assert signed_in.structured_content is not None, signed_in
                first_id = _held(signed_in.structured_content, runtime, "typed_sign_in")
                locked = await sdk.call_tool("session", {"action": "lock"})
                # The same reference signs in again after the lock: the password never reached the caller.
                again = await sdk.call_tool("session", {"action": "sign_in", "secret_reference": str(kept.reference)})
                assert again.structured_content is not None, again
                second_id = _held(again.structured_content, runtime, "typed_sign_in")
                typed = await sdk.call_tool("session", {"action": "sign_in", "secret": PROFILE_INPUT})
                spent = await sdk.call_tool("session", {"action": "sign_in", "secret_reference": str(once.reference)})
                asked_before_spent_again = len(runtime.profiles.logins)
                spent_again = await sdk.call_tool(
                    "session", {"action": "sign_in", "secret_reference": str(once.reference)}
                )
                asked_after_spent_again = len(runtime.profiles.logins)
                refused = await sdk.call_tool(
                    "session", {"action": "sign_in", "secret_reference": str(wrong.reference)}
                )
        finally:
            await adapter.close()

        assert signed_in.is_error is False and again.is_error is False and locked.is_error is False
        assert second_id != first_id
        # The runtime was asked exactly what the typed form asks it, once for each call that reached it.
        assert _logins(runtime) == [("password", _MCP, False)] * 5
        assert typed.is_error is False and typed.structured_content is not None
        assert set(signed_in.structured_content) == set(typed.structured_content)
        by_reference, as_typed = signed_in.structured_content["sign_in"], typed.structured_content["sign_in"]
        assert set(by_reference) == set(as_typed)
        assert (by_reference["session_persisted"], by_reference["resumed"]) == (False, False)
        assert (as_typed["session_persisted"], as_typed["resumed"]) == (False, False)
        # A reference held for one use signs in once, and the call that presents it again reaches no runtime.
        assert spent.is_error is False and spent.structured_content is not None
        assert spent.structured_content["outcome"] == "signed_in"
        assert spent_again.is_error is True and asked_after_spent_again == asked_before_spent_again
        assert spent_again.structured_content == {"outcome": "refused", "code": "invalid_request"}
        # A wrong password by reference is the runtime's refusal, as it is typed.
        assert refused.is_error is True and refused.structured_content is not None
        assert refused.structured_content["outcome"] == "refused"
        assert refused.structured_content["code"] != "invalid_request"
        assert _held_references(client_store) == {str(kept.reference), str(wrong.reference)}
        _holds_no_entered_text(
            signed_in.structured_content,
            again.structured_content,
            spent.structured_content,
            spent_again.structured_content,
            refused.structured_content,
            records=caplog.records,
        )


@pytest.mark.anyio
async def test_the_password_is_changed_with_every_secret_given_by_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    client_store = MemoryNativePort()
    monkeypatch.setattr(mcp_runtime, "installed_automation_secret_store", lambda: client_store)
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        custody = held_secret_custody(client_store)
        current = custody.hold_entered(label=_LABEL, secret=bytearray(PROFILE_INPUT, "utf-8"), single_use=True)
        # One held secret fills the new password and its confirmation, although one use deletes it.
        replacement = custody.hold_entered(label=_LABEL, secret=bytearray(_REPLACEMENT, "utf-8"), single_use=True)
        after = custody.hold_entered(label=_LABEL, secret=bytearray(_REPLACEMENT, "utf-8"), single_use=False)
        adapter = _adapter()
        try:
            changed = await adapter.call(
                "session",
                {
                    "action": "change_password",
                    "secret_reference": str(current.reference),
                    "new_secret_reference": str(replacement.reference),
                    "new_secret_confirmation_reference": str(replacement.reference),
                },
            )
            new = await adapter.call("session", {"action": "sign_in", "secret_reference": str(after.reference)})
        finally:
            await adapter.close()

        assert changed["outcome"] == "password_changed", changed
        assert changed["profile_id"] == str(runtime.profile_id) and changed["password_generation"] >= 2
        assert new["outcome"] == "signed_in", new
        _held(new, runtime, "typed_sign_in")
        # The command line is held to the same change: the old password no longer signs in there.
        person = RuntimeFrontendClient(runtime.connect(), profile_id=runtime.profile_id, frontend=_CLI)
        with pytest.raises(RuntimeFrontendRefusedError):
            person.login_password(bytearray(PROFILE_INPUT.encode()))
        assert _held_references(client_store) == {str(after.reference)}
        _holds_no_entered_text(changed, new, records=caplog.records)


@pytest.mark.anyio
async def test_a_recovery_code_held_for_the_person_resets_the_password_by_its_reference_and_stays_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    client_store = MemoryNativePort()
    monkeypatch.setattr(mcp_runtime, "installed_automation_secret_store", lambda: client_store)
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        custody = held_secret_custody(client_store)
        replacement = custody.hold_entered(label=_LABEL, secret=bytearray(_REPLACEMENT, "utf-8"), single_use=False)
        adapter = _adapter()
        try:
            enabled = await adapter.call("session", {"action": "enable_recovery", "secret": PROFILE_INPUT})
            assert enabled["outcome"] == "completed", enabled
            # The reference the reply names is the one a later call presents; nobody has read the code.
            reset = await adapter.call(
                "session",
                {
                    "action": "reset_password",
                    "secret_reference": enabled["secret_reference"],
                    "new_secret_reference": str(replacement.reference),
                    "new_secret_confirmation_reference": str(replacement.reference),
                },
            )
            new = await adapter.call("session", {"action": "sign_in", "secret_reference": str(replacement.reference)})
            old = await adapter.call("session", {"action": "sign_in", "secret": PROFILE_INPUT})
        finally:
            await adapter.close()

        assert reset["outcome"] == "password_reset", reset
        assert reset["profile_id"] == str(runtime.profile_id) and reset["password_generation"] >= 2
        assert reset["recovery_enrollment_retained"] is True
        assert new["outcome"] == "signed_in", new
        _held(new, runtime, "typed_sign_in")
        assert old["outcome"] == "refused", old
        # Using the code did not show it and is not the person reading it: it is still held and listed
        # as theirs to read, and it is in no reply and no log record.
        delivered = UUID(enabled["secret_reference"])
        code = custody.read(delivered)
        assert not code.entered
        assert {(entry.reference, entry.entered) for entry in custody.entries()} == {
            (delivered, False),
            (replacement.reference, True),
        }
        recovery_code = code.secret.get_secret_value().decode("utf-8")
        logged = "\n".join(f"{record.getMessage()} {record.__dict__!r}" for record in caplog.records)
        assert recovery_code not in json.dumps([enabled, reset, new, old]) and recovery_code not in logged
        _holds_no_entered_text(enabled, reset, new, old, records=caplog.records)
