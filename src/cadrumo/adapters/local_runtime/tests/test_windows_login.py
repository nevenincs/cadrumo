"""Native current-token classification; interactive acceptance needs that OS context."""

from __future__ import annotations

import sys

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.user_profile.access_contracts import Availability, LoginEligibility

from ..windows_login import WindowsLoginBinding, capture_windows_login, observe_windows_login

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows token and WTS APIs"),
]


def test_current_process_requires_a_real_interactive_logon() -> None:
    import win32api
    import win32security

    process = win32api.GetCurrentProcess()
    token = win32security.OpenProcessToken(process, 8)
    try:
        sid, _ = win32security.GetTokenInformation(token, win32security.TokenUser)
        owner = win32security.ConvertSidToStringSid(sid)
        stats = win32security.GetTokenInformation(token, win32security.TokenStatistics)
        logon: object = win32security.LsaGetLogonSessionData(int(stats["AuthenticationId"]))
        assert isinstance(logon, dict)
        if logon["LogonType"] not in (2, 10, 11, 12) or logon["Session"] <= 0:
            with pytest.raises(RuntimeRefusalError) as refused:
                capture_windows_login(process, expected_owner=owner)
            assert refused.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED
        else:
            binding = capture_windows_login(process, expected_owner=owner)
            observed = observe_windows_login(binding, credential_facilities=Availability.UNAVAILABLE)
            assert observed.active and observed.unattended is LoginEligibility.ELIGIBLE
            assert observed.credential_facilities is Availability.UNAVAILABLE
            assert observed.login_id == binding.login_id
        with pytest.raises(RuntimeRefusalError):
            capture_windows_login(process, expected_owner="S-1-0-0")
    finally:
        win32api.CloseHandle(token)


def test_unknown_native_logon_never_becomes_an_eligible_session() -> None:
    missing = WindowsLoginBinding("S-1-0-0", 0x7FFFFFFFFFFFFFFF, 0x7FFFFFFF, 1)
    observed = observe_windows_login(missing, credential_facilities=Availability.AVAILABLE)
    assert not observed.active and observed.locked
    assert observed.unattended is LoginEligibility.UNKNOWN
    assert observed.credential_facilities is Availability.UNAVAILABLE
