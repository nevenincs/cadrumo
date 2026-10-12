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

from cadrumo.adapters.persistence.storage.custody.sign_in_generation import SignInGenerationCustody
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from cadrumo.adapters.persistence.storage.master_key.login_throttle import (
    THROTTLE_BACKOFF_CAP_SECONDS,
    record_login_failure,
)
from cadrumo.core.config import override_settings
from cadrumo.core.time.clock import now
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
        assert refused == {"outcome": "refused", "code": "authentication_required", **facts}
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

        assert refused == {"outcome": "refused", "code": "session_expired", "sign_in_reason": "expired_idle"}
        assert status == _no_session(runtime, "authentication_required", sign_in_reason="absent")
        assert runtime.leases() == ()


@pytest.mark.anyio
async def test_a_throttled_password_sign_in_says_how_long_to_wait(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch, signed_in=False) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        # Six wrong passwords in a row put the next attempt behind the longest backoff.
        for _ in range(6):
            record_login_failure(storage_root=runtime.root, bucket_id=str(runtime.profile_id), now=now())
        adapter = RuntimeMcpAdapter(profile_id=None, client=None, resumes_sign_in=True)
        try:
            refused = await adapter.call("session", {"action": "sign_in", "secret": PROFILE_INPUT})
        finally:
            await adapter.close()

        seconds = refused.pop("seconds")
        assert refused == {
            "outcome": "refused",
            "code": "authentication_required",
            "sign_in_reason": "throttled",
        }
        assert isinstance(seconds, int) and 0 < seconds <= THROTTLE_BACKOFF_CAP_SECONDS
        # The correct password was never tried, so no session was admitted.
        assert runtime.leases() == ()
