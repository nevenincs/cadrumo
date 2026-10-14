"""Human receipt refusals retain public facts; external attendance discloses none.

The installed clients, transport, runtime and custody are real. The native
login, keychain and clock are controlled ports. Receipt failures are exercised
on a CLI connection, while MCP has no person proof or held session to use.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from cadrumo.adapters.persistence.storage.custody import acceleration_receipt as receipt_custody
from cadrumo.adapters.persistence.storage.custody.sign_in_generation import SignInGenerationCustody
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.login_session import ProfileReceiptRefusedError
from cadrumo.core.config import override_settings
from cadrumo.core.profile_session import ProfileSessionRefusalReason
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_harness.mcp.protocol_contract import (
    KEYCHAIN_REMEDY,
    SIGN_IN_REMEDY,
    refusal_code,
    sign_in_remedy,
)
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_runtime.host.tests.stored_sign_in_runtime import StoredSignInRuntime, stored_sign_in_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker and protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]


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


async def _person_refusal_and_external_status(runtime: StoredSignInRuntime) -> tuple[dict[str, Any], dict[str, Any]]:
    """Project an actual person receipt refusal, then ask external attendance for status."""
    person = FrontendClient(runtime.connect(), profile_id=runtime.profile_id, frontend=OperationFrontendProjection.CLI)
    adapter = RuntimeMcpAdapter(profile_id=None, client=None, requests_attendance=True)
    try:
        with pytest.raises(ProfileReceiptRefusedError) as failure:
            await asyncio.to_thread(person.resume_receipt)
        error = failure.value
        answered = error.__cause__
        if isinstance(answered, FrontendRefusedError):
            code = refusal_code(answered)
        elif error.reason is ProfileSessionRefusalReason.KEYRING_UNAVAILABLE:
            code = "custody_unavailable"
        elif error.reason in {ProfileSessionRefusalReason.EXPIRED_IDLE, ProfileSessionRefusalReason.EXPIRED_ABSOLUTE}:
            code = "session_expired"
        else:
            code = "authentication_required"
        facts = {"sign_in_reason": error.reason.value}
        if error.binding is not None:
            facts["sign_in_binding"] = error.binding.value
        if error.keychain is not None:
            facts["sign_in_keychain"] = error.keychain.value
        refused = {"outcome": "refused", "code": code, **facts, "remedy": sign_in_remedy(code, facts)}
        status = await adapter.call("status", {})
    finally:
        await adapter.close()
        await asyncio.to_thread(person.close)
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
        refused, status = await _person_refusal_and_external_status(runtime)

        facts = {"sign_in_reason": "absent", "sign_in_binding": "generation_changed"}
        assert refused == {
            "outcome": "refused",
            "code": "authentication_required",
            **facts,
            "remedy": sign_in_remedy("authentication_required"),
        }
        # External attendance has no held person and receives no receipt refusal facts.
        assert status == _no_session(runtime, "authentication_required")
        assert runtime.leases() == ()


@pytest.mark.anyio
async def test_a_sign_in_made_at_another_login_says_so(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        # The receipt was stored at the person's login; the CLI connection now comes from another one.
        runtime.native_login.login_id = "another-desktop-login"
        refused, _status = await _person_refusal_and_external_status(runtime)

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
        refused, status = await _person_refusal_and_external_status(runtime)

        assert refused == {
            "outcome": "refused",
            "code": "session_expired",
            "sign_in_reason": "expired_idle",
            "remedy": sign_in_remedy("session_expired"),
        }
        assert status == _no_session(runtime, "authentication_required")
        assert runtime.leases() == ()


class _LogonWithoutCredentials:
    """The credential store as a Windows logon that holds no credentials meets it."""

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
        refused, status = await _person_refusal_and_external_status(runtime)

        # The fact is value-free: it names the prerequisite, never an account, a path or an error text.
        assert refused["sign_in_keychain"] == "logon_without_credentials"
        assert status == _no_session(runtime, "authentication_required")
        # The person sees the keychain remedy; external attendance gets only its own no-holder refusal.
        assert refused["remedy"] == KEYCHAIN_REMEDY
        assert status["remedy"] == SIGN_IN_REMEDY
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
