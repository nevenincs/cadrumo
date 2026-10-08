"""Portable audit-token and session decisions; no macOS lifecycle proof."""

from __future__ import annotations

import struct

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.user_profile.access_contracts import Availability, LoginEligibility, OsLockState

from .. import macos_login
from ..macos_login import MacosLoginBinding, MacosSessionObservation, decode_macos_peer_audit_token

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_kernel_audit_token_preserves_exact_session_and_process_incarnation() -> None:
    value = decode_macos_peer_audit_token(
        struct.pack("=8I", 501, 501, 20, 501, 20, 123, 100022, 7), expected_owner="501"
    )
    assert value.process_id == 123 and value.process_version == 7 and value.audit_session_id == 100022
    assert value.audit_user_id == value.effective_user_id == value.real_user_id == 501


@pytest.mark.parametrize("position,value", [(0, 502), (1, 502), (3, 502), (5, 0), (6, 0), (6, 0xFFFFFFFF), (7, 0)])
def test_foreign_owner_unknown_session_or_unpinned_process_refuses(position: int, value: int) -> None:
    fields = [501, 501, 20, 501, 20, 123, 100022, 7]
    fields[position] = value
    with pytest.raises(RuntimeRefusalError) as caught:
        decode_macos_peer_audit_token(struct.pack("=8I", *fields), expected_owner="501")
    assert caught.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED


@pytest.mark.parametrize("payload", [b"", bytes(31), bytes(33)])
def test_partial_or_extended_native_audit_record_refuses(payload: bytes) -> None:
    with pytest.raises(RuntimeRefusalError):
        decode_macos_peer_audit_token(payload, expected_owner="501")


def test_graphic_session_does_not_imply_unlocked_or_unattended_eligibility(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: list[int] = []

    def session(session_id: int) -> MacosSessionObservation:
        observed.append(session_id)
        return MacosSessionObservation(session_id, 0x10)

    monkeypatch.setattr(macos_login, "observe_macos_session", session)
    binding = MacosLoginBinding("501", 100022)
    context = binding.observe(credential_facilities=Availability.AVAILABLE)
    assert observed == [100022] and context.login_id == "macos:501:100022"
    assert context.active and context.lock_state is OsLockState.UNKNOWN and not context.unlocked
    assert context.unattended is LoginEligibility.UNKNOWN
    assert context.credential_facilities is Availability.AVAILABLE


def test_missing_session_and_native_failure_remain_distinct_and_cannot_restore_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(_session_id: int) -> None:
        return None

    monkeypatch.setattr(macos_login, "observe_macos_session", missing)
    binding = MacosLoginBinding("501", 100022)
    absent = binding.observe(credential_facilities=Availability.UNAVAILABLE)
    assert not absent.active and absent.lock_state is OsLockState.UNKNOWN
    assert absent.unattended is LoginEligibility.INELIGIBLE

    def unavailable(_session_id: int) -> None:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)

    monkeypatch.setattr(macos_login, "observe_macos_session", unavailable)
    failed = binding.observe(credential_facilities=Availability.AVAILABLE)
    assert not failed.active and failed.lock_state is OsLockState.UNKNOWN
    assert failed.unattended is LoginEligibility.UNKNOWN


@pytest.mark.parametrize("flags", [0x2010, 0x4010, 0x6010, 0x5020, 0x7010, 0x4011])
def test_known_audit_flags_do_not_grant_lock_or_unattended_authority(
    flags: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = macos_login._session_observation(100022, 0, 100022, flags)
    assert value == MacosSessionObservation(100022, flags)
    monkeypatch.setattr(macos_login, "observe_macos_session", lambda _session_id: value)
    context = MacosLoginBinding("501", 100022).observe(credential_facilities=Availability.AVAILABLE)
    assert context.active is (bool(flags & 0x10) and not bool(flags & 0x1001))
    assert context.lock_state is OsLockState.UNKNOWN and not context.unlocked
    assert context.unattended is LoginEligibility.UNKNOWN


@pytest.mark.parametrize("status,observed,flags", [(1, 42, 0x6010), (0, 43, 0x6010), (0, 42, 0x8010)])
def test_audit_record_unknown_flags_error_and_changed_session_still_refuse(
    status: int, observed: int, flags: int
) -> None:
    with pytest.raises(RuntimeRefusalError) as caught:
        macos_login._session_observation(42, status, observed, flags)
    assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE
    assert macos_login._session_observation(42, -60500, 0, 0) is None
