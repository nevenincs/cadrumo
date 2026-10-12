"""An MCP reply names why the runtime refused the sign-in, with the facts the command line reports.

The adapter, the installed client it opens, the native transport, the runtime,
the session authority, the profile worker, the stored sign-in and the login
throttle are real. The native login the runtime observes, the keychain holding
the proof and the runtime's wall clock are ports held by the test. Each expected
fact is the one the command line's refusal context carries for the same
refusal: the denial code, ``sign_in_reason``, ``sign_in_binding`` and
``seconds``.
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from cadrumo.adapters.persistence.storage.custody import acceleration_receipt as receipt_custody
from cadrumo.adapters.persistence.storage.custody.sign_in_generation import SignInGenerationCustody
from cadrumo.core.config import override_settings
from cadrumo_harness.mcp.protocol_contract import KEYCHAIN_REMEDY, SIGN_IN_REMEDY, sign_in_remedy
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter

from .stored_sign_in_runtime import StoredSignInRuntime, stored_sign_in_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker and protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_PROFILE_CALL: tuple[str, dict[str, object]] = ("observe", {"observation": {}})
"""A tool that reads the profile's own operations, so it is answered only under a session."""


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


async def _refused_twice(runtime: StoredSignInRuntime) -> tuple[dict[str, Any], dict[str, Any]]:
    """Make a call that needs the profile, then read status, on one adapter that resumes the sign-in."""
    adapter = RuntimeMcpAdapter(profile_id=None, client=None, resumes_sign_in=True)
    try:
        refused = await adapter.call(*_PROFILE_CALL)
        status = await adapter.call("status", {})
    finally:
        await adapter.close()
    return refused, status


@pytest.mark.anyio
async def test_a_sign_in_fenced_by_a_sign_out_elsewhere_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        # A sign-out or lock elsewhere advances the generation; the stored sign-in is still here to present.
        SignInGenerationCustody(root=runtime.root, binding=runtime.binding).advance()
        refused, status = await _refused_twice(runtime)

        facts = {"sign_in_reason": "absent", "sign_in_binding": "generation_changed"}
        assert refused == {
            "outcome": "refused",
            "code": "authentication_required",
            **facts,
            "remedy": sign_in_remedy("authentication_required"),
        }
        # The status call asked again; the runtime had removed what it refused, so nothing was left to present.
        assert status == _no_session(runtime, "authentication_required", sign_in_reason="absent")
        assert runtime.leases() == ()


@pytest.mark.anyio
async def test_a_sign_in_made_at_another_login_says_so(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        # The sign-in was stored at the person's login; this connection now comes from another one.
        runtime.native_login.login_id = "another-desktop-login"
        refused, _status = await _refused_twice(runtime)

        assert refused == {
            "outcome": "refused",
            "code": "authentication_required",
            "sign_in_reason": "absent",
            "sign_in_binding": "login_mismatch",
            "remedy": sign_in_remedy("authentication_required"),
        }
        assert runtime.leases() == ()


@pytest.mark.anyio
async def test_a_sign_in_past_its_idle_deadline_says_it_expired(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch, signed_in=False) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        # The person signed in a minute more than the idle window ago; the absolute cap still stands.
        runtime.store_sign_in(age=timedelta(minutes=16))
        refused, status = await _refused_twice(runtime)

        assert refused == {
            "outcome": "refused",
            "code": "session_expired",
            "sign_in_reason": "expired_idle",
            "remedy": sign_in_remedy("session_expired"),
        }
        assert status == _no_session(runtime, "authentication_required", sign_in_reason="absent")
        assert runtime.leases() == ()


class _LogonWithoutCredentials:
    """The credential store as a Windows logon without credentials, such as an OpenSSH key sign-in, meets it."""

    def get_password(self, _service: str, _account: str) -> str | None:
        raise OSError(None, "A specified logon session does not exist", None, 1312)

    def set_password(self, _service: str, _account: str, _password: str) -> None:
        raise OSError(None, "A specified logon session does not exist", None, 1312)

    def delete_password(self, _service: str, _account: str) -> None:
        raise OSError(None, "A specified logon session does not exist", None, 1312)


def _in_a_logon_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    from keyring.errors import KeyringError, PasswordDeleteError

    store = _LogonWithoutCredentials()
    monkeypatch.setattr(receipt_custody, "_keyring", lambda: (store, KeyringError, PasswordDeleteError))


@pytest.mark.anyio
@pytest.mark.parametrize("signed_in", [True, False], ids=["a-sign-in-is-stored", "nothing-is-stored"])
async def test_a_logon_that_cannot_use_the_credential_store_says_so_and_sends_the_person_to_their_desktop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, signed_in: bool
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch, signed_in=signed_in) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        stored = runtime.stored_sign_in()
        _in_a_logon_without_credentials(monkeypatch)
        refused, status = await _refused_twice(runtime)

        # The fact is value-free: it names the prerequisite, never an account, a path or an error text.
        assert refused["sign_in_keychain"] == "logon_without_credentials"
        assert status["sign_in_keychain"] == "logon_without_credentials"
        # Signing in again would change nothing from this logon, so the remedy is the logon, not a sign-in.
        assert refused["remedy"] == status["remedy"] == KEYCHAIN_REMEDY
        expected = (
            {"code": "custody_unavailable", "sign_in_reason": "keyring_unavailable"}
            if signed_in
            else {"code": "authentication_required", "sign_in_reason": "absent"}
        )
        assert {key: refused[key] for key in expected} == expected
        assert set(refused) == {"outcome", "code", "sign_in_reason", "sign_in_keychain", "remedy"}
        # Nothing the runtime holds was admitted or changed by the refusal.
        assert runtime.leases() == () and runtime.stored_sign_in() == stored


def test_a_refusal_without_the_keychain_fact_keeps_the_sign_in_remedy() -> None:
    assert sign_in_remedy("authentication_required", {"sign_in_reason": "absent"}) == SIGN_IN_REMEDY
    assert sign_in_remedy("authentication_required", {"sign_in_keychain": "no_backend"}) == KEYCHAIN_REMEDY
