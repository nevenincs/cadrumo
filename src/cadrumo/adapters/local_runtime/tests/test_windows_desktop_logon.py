"""Pure witness and ownership decisions; no native Windows acceptance claim."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

from ..windows_desktop_logon import (
    WindowsDesktopLogon,
    _object_text,
    _owned_handle,
    _StationSnapshot,
    _TokenSnapshot,
    _validated_witness,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_OWNER = "S-1-5-21-100-200-300-1001"
_LOGON_SID = "S-1-5-5-0-1234"
_TOKEN = _TokenSnapshot(_OWNER, 101, 1, _LOGON_SID, 1, 2, 201, 301)
_STATION = _StationSnapshot("WinSta0", "WindowStation", 1, _LOGON_SID, False, False)


def test_exact_stable_logon_sid_witness_retains_immutable_native_identity() -> None:
    result = _validated_witness(_TOKEN, _STATION, _TOKEN, _STATION)
    assert result == WindowsDesktopLogon(_OWNER, 101, 1, _LOGON_SID)
    field_name = "authentication_id"
    with pytest.raises(FrozenInstanceError):
        setattr(result, field_name, 102)
    assert _OWNER not in repr(result) and _LOGON_SID not in repr(result)


@pytest.mark.parametrize(
    "station",
    [
        replace(_STATION, associated_sid=None),
        replace(_STATION, associated_sid=_OWNER),
        replace(_STATION, associated_sid="S-1-5-5-0-9999"),
        replace(_STATION, associated_sid="invalid"),
        replace(_STATION, name="WinSta0-lookalike"),
        replace(_STATION, kind="Desktop"),
        replace(_STATION, flags=0),
        replace(_STATION, flags=3),
        replace(_STATION, inherited=True),
        replace(_STATION, reserved=True),
    ],
)
def test_missing_foreign_account_or_noncanonical_station_never_substitutes_for_logon_role(
    station: _StationSnapshot,
) -> None:
    with pytest.raises(RuntimeRefusalError) as caught:
        _validated_witness(_TOKEN, station, _TOKEN, station)
    assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE


@pytest.mark.parametrize(
    "token",
    [
        replace(_TOKEN, authentication_id=0),
        replace(_TOKEN, authentication_id=True),
        replace(_TOKEN, authentication_id=2**63),
        replace(_TOKEN, session_id=0),
        replace(_TOKEN, session_id=True),
        replace(_TOKEN, logon_sid_count=0),
        replace(_TOKEN, logon_sid_count=2),
        replace(_TOKEN, logon_sid_count=True),
        replace(_TOKEN, logon_kind=3),
        replace(_TOKEN, logon_kind=9),
        replace(_TOKEN, logon_sid=_OWNER),
        replace(_TOKEN, logon_sid="S-1-5-5-0-4294967296"),
        replace(_TOKEN, os_owner_id="not-a-sid"),
        replace(_TOKEN, token_id=0),
        replace(_TOKEN, modified_id=0),
    ],
)
def test_invalid_noninteractive_or_ambiguous_token_cannot_become_a_current_desktop_witness(
    token: _TokenSnapshot,
) -> None:
    station = replace(_STATION, associated_sid=token.logon_sid)
    with pytest.raises(RuntimeRefusalError) as caught:
        _validated_witness(token, station, token, station)
    assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE


@pytest.mark.parametrize(
    "after_token",
    [
        replace(_TOKEN, authentication_id=102),
        replace(_TOKEN, session_id=2),
        replace(_TOKEN, os_owner_id="S-1-5-21-100-200-300-1002"),
        replace(_TOKEN, logon_sid="S-1-5-5-0-9999"),
        replace(_TOKEN, logon_kind=10),
        replace(_TOKEN, token_id=202),
        replace(_TOKEN, modified_id=302),
    ],
)
def test_changed_token_incarnation_refuses_even_when_both_snapshots_individually_look_valid(
    after_token: _TokenSnapshot,
) -> None:
    with pytest.raises(RuntimeRefusalError) as caught:
        _validated_witness(_TOKEN, _STATION, after_token, _STATION)
    assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE


def test_station_reassociation_to_same_account_new_logon_refuses_old_token() -> None:
    replacement = replace(_STATION, associated_sid="S-1-5-5-0-9999")
    with pytest.raises(RuntimeRefusalError) as caught:
        _validated_witness(_TOKEN, _STATION, _TOKEN, replacement)
    assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE
    # Stable stale association also refuses; account SID equality cannot rescue it.
    with pytest.raises(RuntimeRefusalError):
        _validated_witness(_TOKEN, replacement, _TOKEN, replacement)


@pytest.mark.parametrize("payload", [b"", b"x", b"x\0", b"\0\0x\0\0\0", b"\x00\xd8\0\0", b"x\0" * 257])
def test_malformed_unterminated_or_excessive_native_text_refuses(payload: bytes) -> None:
    with pytest.raises(RuntimeRefusalError) as caught:
        _object_text(payload)
    assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE


def test_owned_handle_cleanup_occurs_once_before_a_witness_can_be_released() -> None:
    closed: list[int] = []

    def close(handle: int) -> bool:
        closed.append(handle)
        return True

    with _owned_handle(17, close) as handle:
        assert handle == 17 and not closed
    assert closed == [17]
    with pytest.raises(RuntimeRefusalError) as caught, _owned_handle(18, lambda _handle: False):
        pass
    assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE


def test_cleanup_failure_preserves_primary_refusal_without_native_error_text() -> None:
    original = RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)

    def close(_handle: int) -> bool:
        raise OSError("private native diagnostic")

    with pytest.raises(RuntimeRefusalError) as caught, _owned_handle(19, close):
        raise original
    assert caught.value is original
    assert "private native diagnostic" not in str(caught.value)
    assert caught.value.__notes__ == ["Owned native desktop witness handle cleanup failed"]
