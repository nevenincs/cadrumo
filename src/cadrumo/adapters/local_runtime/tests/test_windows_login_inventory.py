"""Portable native-port inventory proofs, without claiming Windows acceptance."""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import ModuleType, SimpleNamespace
from typing import cast

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.login import RuntimeLoginInventory
from cadrumo.application.user_profile.access_contracts import Availability, LoginEligibility

from .. import windows_desktop_observation, windows_login, windows_login_native
from ..windows_desktop_logon import WindowsDesktopLogon
from ..windows_login import WindowsLoginBinding, capture_windows_login, windows_login_inventory

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_OWNER = "S-1-5-21-100-200-300-1001"
_OTHER = "S-1-5-21-100-200-300-1002"
_LOGON_SID = "S-1-5-5-0-1234"
_OTHER_LOGON_SID = "S-1-5-5-0-9999"
_TIME = datetime(2026, 10, 1, tzinfo=UTC)
_TICKS = int((_TIME - datetime(1601, 1, 1, tzinfo=UTC)) // timedelta(microseconds=1)) * 10


class _NativeError(Exception):
    """Exact explicit native refusal, never an actual OS probe."""


class _Sid:
    def __init__(self, value: str) -> None:
        self.value = value


class _Function:
    def __init__(self, call: Callable[..., object]) -> None:
        self.call = call

    def __call__(self, *args: object) -> object:
        return self.call(*args)


class _Native:
    def __init__(self) -> None:
        self.ids: object = (101,)
        self.after_ids: object | None = None
        self.wts: object = ({"SessionId": 1, "State": 0},)
        self.after_wts: object | None = None
        self.enumerations = 0
        self.wts_enumerations = 0
        self.rows: dict[int, object] = {101: self.row(101)}
        self.lsa_reads = 0
        self.query_reads = 0
        self.query_error = 0
        self.generation_changes = False
        self.owner_changes = False
        self.lsa_changes = False
        self.state = 0
        self.flags = 1
        self.desktop_owner = _OWNER
        self.desktop_time = _TICKS
        self.current_witness = WindowsDesktopLogon(_OWNER, 101, 1, _LOGON_SID)
        self.after_current_witness: WindowsDesktopLogon | None = None
        self.current_witness_reads = 0
        self.tokens_closed: list[int] = []
        self.peer_owner = _OWNER
        self.peer_authentication = 101
        self.peer_session = 1
        self.lookup_error = False
        self.allocations: dict[int, windows_desktop_observation.WindowsSessionInformation] = {}
        self.freed: list[int] = []
        self.now = 0.0
        self.elapsed_on_query = False

    @staticmethod
    def row(identifier: int, *, owner: str = _OWNER, kind: int = 2, session: int = 1) -> dict[str, object]:
        return {"LogonId": identifier, "LogonType": kind, "Session": session, "Sid": _Sid(owner), "LogonTime": _TIME}

    def enumerate_lsa(self) -> object:
        self.enumerations += 1
        return self.after_ids if self.enumerations > 1 and self.after_ids is not None else self.ids

    def enumerate_wts(self, server: int, version: int, reserved: int) -> object:
        assert (server, version, reserved) == (0, 1, 0)
        self.wts_enumerations += 1
        if isinstance(self.wts, BaseException):
            raise self.wts
        return self.after_wts if self.wts_enumerations > 1 and self.after_wts is not None else self.wts

    def logon(self, identifier: int) -> object:
        self.lsa_reads += 1
        row = self.rows[identifier]
        if isinstance(row, BaseException):
            raise row
        if self.lsa_changes and self.lsa_reads > 1:
            return self.row(identifier, owner=_OTHER)
        return row

    def lookup(self, server: None, account: str) -> tuple[_Sid, str, int]:
        assert server is None and account == "DOMAIN\\owner"
        if self.lookup_error:
            raise _NativeError("lookup unavailable")
        owner = _OTHER if self.owner_changes and self.query_reads > 1 else self.desktop_owner
        return _Sid(owner), "DOMAIN", 1

    def current_desktop_logon(self) -> WindowsDesktopLogon:
        self.current_witness_reads += 1
        if self.after_current_witness is not None and self.current_witness_reads > 1:
            return self.after_current_witness
        return self.current_witness

    def query(self, server: None, session: int, kind: int, buffer: object, count: object) -> int:
        assert server is None and session == 1 and kind == 25
        self.query_reads += 1
        if self.query_error:
            return 0
        information = windows_desktop_observation.WindowsSessionInformation()
        information.level = 1
        information.data.session_id = session
        information.data.state = self.state
        information.data.flags = self.flags
        information.data.logon_time = self.desktop_time + (
            10 if self.generation_changes and self.query_reads > 1 else 0
        )
        for target, value in ((information.data.domain, "DOMAIN"), (information.data.user, "owner")):
            for index, character in enumerate(value):
                target[index] = ord(character)
        address = ctypes.addressof(information)
        self.allocations[address] = information
        # The real observer passes byref C arguments through this native seam.
        ctypes.cast(cast(ctypes.c_void_p, buffer), ctypes.POINTER(ctypes.c_void_p))[0] = address
        ctypes.cast(cast(ctypes.c_void_p, count), ctypes.POINTER(ctypes.c_uint32))[0] = ctypes.sizeof(information)
        if self.elapsed_on_query:
            self.now = 3.0
        return 1

    def free(self, buffer: ctypes.c_void_p) -> None:
        assert buffer.value is not None
        self.freed.append(buffer.value)
        del self.allocations[buffer.value]


@pytest.fixture
def native(monkeypatch: pytest.MonkeyPatch) -> _Native:
    """Exercise real observer parsing and inventory through isolated native ports."""
    port = _Native()
    security = ModuleType("win32security")
    security.__dict__.update(
        LsaEnumerateLogonSessions=port.enumerate_lsa,
        LsaGetLogonSessionData=port.logon,
        LookupAccountName=port.lookup,
        CreateWellKnownSid=lambda *_args: _Sid("S-1-0-0"),
        ConvertSidToStringSid=lambda sid: sid.value,
        WinNullSid=0,
        SidTypeUser=1,
        OpenProcessToken=lambda handle, access: 77,
        GetTokenInformation=lambda token, information: (
            (_Sid(port.peer_owner), 0)
            if information == 1
            else {"AuthenticationId": port.peer_authentication}
            if information == 2
            else port.peer_session
        ),
        TokenUser=1,
        TokenStatistics=2,
        TokenSessionId=3,
    )
    api = ModuleType("win32api")
    api.__dict__["CloseHandle"] = port.tokens_closed.append
    errors = ModuleType("pywintypes")
    errors.__dict__["error"] = _NativeError
    wts = ModuleType("win32ts")
    wts.__dict__.update(WTSEnumerateSessions=port.enumerate_wts, WTS_CURRENT_SERVER_HANDLE=0)
    for module in (security, errors, wts, api):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    for owner in (windows_login, windows_login_native, windows_desktop_observation):
        monkeypatch.setattr(
            owner, "sys", SimpleNamespace(platform="win32", getwindowsversion=lambda: SimpleNamespace(major=10))
        )
    monkeypatch.setattr(windows_login, "current_windows_desktop_logon", port.current_desktop_logon)
    monkeypatch.setattr(windows_login, "time", SimpleNamespace(monotonic=lambda: port.now))
    monkeypatch.setattr(
        windows_desktop_observation,
        "ctypes",
        SimpleNamespace(
            WinDLL=lambda *_args, **_kwargs: SimpleNamespace(
                WTSQuerySessionInformationW=_Function(port.query), WTSFreeMemory=_Function(port.free)
            ),
            c_void_p=ctypes.c_void_p,
            c_uint32=ctypes.c_uint32,
            c_int32=ctypes.c_int32,
            POINTER=ctypes.POINTER,
            byref=ctypes.byref,
            sizeof=ctypes.sizeof,
            string_at=ctypes.string_at,
            get_last_error=lambda: port.query_error,
        ),
    )
    return port


@pytest.mark.parametrize(("state", "flags"), [(0, 0), (0, 1), (4, 0), (4, 1)])
def test_locked_and_disconnected_owner_login_remains_a_positive_witness(
    native: _Native, state: int, flags: int
) -> None:
    native.state, native.flags = state, flags
    native.wts = ({"SessionId": 1, "State": state},)
    result = windows_login_inventory(expected_owner=_OWNER)
    assert result.complete and result.eligibility is LoginEligibility.ELIGIBLE
    assert len(result.logins) == 1
    binding = result.logins[0]
    assert isinstance(binding, WindowsLoginBinding)
    assert binding == WindowsLoginBinding(_OWNER, 101, 1, _TICKS)
    assert binding.login_id == f"windows:65:1:{_TICKS}"
    for facilities in (Availability.AVAILABLE, Availability.UNAVAILABLE):
        observed = binding.observe(credential_facilities=facilities)
        assert observed.active and observed.unattended is LoginEligibility.ELIGIBLE
        assert observed.locked is (flags == 0)
        assert observed.credential_facilities is facilities and observed.login_id == binding.login_id
    assert not native.allocations and len(native.freed) == native.query_reads


@pytest.mark.parametrize("kind", ["empty", "foreign", "noninteractive", "absent_desktop"])
def test_current_only_witness_cannot_prove_complete_absence(native: _Native, kind: str) -> None:
    if kind == "empty":
        native.ids = ()
    elif kind == "foreign":
        native.rows[101] = native.row(101, owner=_OTHER)
    elif kind == "noninteractive":
        native.rows[101] = native.row(101, kind=3)
    else:
        native.wts = ()
        native.query_error = 7022
    result = windows_login_inventory(expected_owner=_OWNER)
    assert result == RuntimeLoginInventory((), False)
    assert result.eligibility is LoginEligibility.UNKNOWN


@pytest.mark.parametrize(
    "failure", ["denied", "malformed", "lookup", "naked_not_found", "access_error", "wts_denied", "missing_lsa_time"]
)
def test_unreadable_or_uncorrelated_owner_rows_never_prove_absence(native: _Native, failure: str) -> None:
    if failure == "denied":
        native.rows[101] = _NativeError("unreadable LSA row")
    elif failure == "malformed":
        native.rows[101] = {"LogonType": True}
    elif failure == "lookup":
        native.lookup_error = True
    elif failure == "wts_denied":
        native.wts = _NativeError("WTS enumeration unavailable")
    elif failure == "missing_lsa_time":
        native.rows[101] = {**native.row(101), "LogonTime": None}
    else:
        native.query_error = 7022 if failure == "naked_not_found" else 5
    result = windows_login_inventory(expected_owner=_OWNER)
    assert result == RuntimeLoginInventory((), False)
    assert result.eligibility is LoginEligibility.UNKNOWN
    assert not native.allocations


@pytest.mark.parametrize("race", ["lsa_set", "wts_set", "lsa_row", "wts_time", "wts_owner", "elapsed"])
def test_enumeration_or_incarnation_races_do_not_publish_a_login(native: _Native, race: str) -> None:
    if race == "lsa_set":
        native.after_ids = (101, 102)
    elif race == "wts_set":
        native.after_wts = ()
    elif race == "lsa_row":
        native.lsa_changes = True
    elif race == "wts_time":
        native.generation_changes = True
    elif race == "wts_owner":
        native.owner_changes = True
    else:
        native.elapsed_on_query = True
    result = windows_login_inventory(expected_owner=_OWNER)
    assert not result.logins and not result.complete
    assert result.eligibility is LoginEligibility.UNKNOWN
    assert not native.allocations


def test_retained_lsa_cannot_bind_another_owners_reused_desktop(native: _Native) -> None:
    original = WindowsLoginBinding(_OWNER, 101, 1, _TICKS)
    native.desktop_owner = _OTHER
    result = windows_login_inventory(expected_owner=_OWNER)
    assert not result.logins and not result.complete
    assert result.eligibility is LoginEligibility.UNKNOWN
    observed = original.observe(credential_facilities=Availability.AVAILABLE)
    assert not observed.active and observed.locked and observed.unattended is LoginEligibility.INELIGIBLE
    assert observed.login_id == original.login_id
    assert original == WindowsLoginBinding(_OWNER, 101, 1, _TICKS)


def test_positive_owner_witness_survives_unreadable_other_luid_without_claiming_completeness(native: _Native) -> None:
    native.ids = (101, 102)
    native.rows[102] = _NativeError("ownership unavailable")
    result = windows_login_inventory(expected_owner=_OWNER)
    assert not result.complete and result.eligibility is LoginEligibility.ELIGIBLE
    assert result.logins == (WindowsLoginBinding(_OWNER, 101, 1, _TICKS),)


def test_unsupported_other_owned_authentication_id_does_not_prove_complete_inventory(native: _Native) -> None:
    native.ids = (101, 102)
    native.rows[102] = native.row(102)
    result = windows_login_inventory(expected_owner=_OWNER)
    assert result.logins == (WindowsLoginBinding(_OWNER, 101, 1, _TICKS),)
    assert not result.complete and result.eligibility is LoginEligibility.ELIGIBLE


def test_lsa_and_wts_timestamp_difference_does_not_override_current_witness(native: _Native) -> None:
    native.desktop_time += 10
    binding = capture_windows_login(55, expected_owner=_OWNER)
    result = windows_login_inventory(expected_owner=_OWNER)
    observed = binding.observe(credential_facilities=Availability.AVAILABLE)
    assert binding == WindowsLoginBinding(_OWNER, 101, 1, _TICKS + 10)
    assert cast(dict[str, object], native.rows[101])["LogonTime"] == _TIME and native.desktop_time != _TICKS
    assert result == RuntimeLoginInventory((binding,), True)
    assert observed.active and observed.unattended is LoginEligibility.ELIGIBLE
    assert observed.login_id == binding.login_id


def test_changed_logon_sid_at_current_witness_bookends_is_not_trusted(native: _Native) -> None:
    native.after_current_witness = WindowsDesktopLogon(_OWNER, 101, 1, _OTHER_LOGON_SID)
    original = WindowsLoginBinding(_OWNER, 101, 1, _TICKS)
    with pytest.raises(RuntimeRefusalError) as caught:
        capture_windows_login(55, expected_owner=_OWNER)
    assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE
    assert native.tokens_closed == [77]

    native.current_witness_reads = 0
    observed = original.observe(credential_facilities=Availability.AVAILABLE)
    assert not observed.active and observed.locked
    assert observed.unattended is LoginEligibility.UNKNOWN
    assert observed.login_id == original.login_id
    assert native.current_witness_reads >= 2

    native.current_witness_reads = 0
    inventory = windows_login_inventory(expected_owner=_OWNER)
    assert inventory == RuntimeLoginInventory((), False)
    assert inventory.eligibility is LoginEligibility.UNKNOWN
    assert native.current_witness_reads >= 2
    assert not native.allocations and len(native.freed) == native.query_reads


@pytest.mark.parametrize("ids", [(True,), (101, 101), (2**64,), [101], tuple(range(1, 4098))])
def test_malformed_or_excessive_native_luid_array_refuses_before_row_reads(native: _Native, ids: object) -> None:
    native.ids = ids
    result = windows_login_inventory(expected_owner=_OWNER)
    assert result == RuntimeLoginInventory((), False)
    assert native.lsa_reads == native.query_reads == 0


def test_missing_lsa_time_refuses_capture_and_makes_observation_unknown(native: _Native) -> None:
    original = WindowsLoginBinding(_OWNER, 101, 1, _TICKS)
    native.rows[101] = {**native.row(101), "LogonTime": None}
    with pytest.raises(RuntimeRefusalError) as caught:
        capture_windows_login(55, expected_owner=_OWNER)
    assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE
    assert native.tokens_closed == [77]
    observed = original.observe(credential_facilities=Availability.AVAILABLE)
    assert not observed.active and observed.locked
    assert observed.unattended is LoginEligibility.UNKNOWN
    assert observed.login_id == original.login_id == f"windows:65:1:{_TICKS}"
    assert original == WindowsLoginBinding(_OWNER, 101, 1, _TICKS)
    assert not native.allocations and len(native.freed) == native.query_reads


def test_new_wts_generation_is_captured_but_old_peer_is_refused(native: _Native) -> None:
    original = WindowsLoginBinding(_OWNER, 101, 1, _TICKS)
    native.desktop_time += 10
    captured = capture_windows_login(55, expected_owner=_OWNER)
    observed = original.observe(credential_facilities=Availability.AVAILABLE)
    assert captured == WindowsLoginBinding(_OWNER, 101, 1, _TICKS + 10)
    assert not observed.active and observed.locked
    assert observed.unattended is LoginEligibility.INELIGIBLE
    assert observed.login_id == original.login_id
    assert not native.allocations and len(native.freed) == native.query_reads


@pytest.mark.parametrize("session,kind", [(0, 4), (0, 5), (2, 10)])
def test_same_account_client_from_another_session_uses_runtime_desktop(
    native: _Native, session: int, kind: int
) -> None:
    native.peer_authentication = 202
    native.peer_session = session
    native.rows[202] = {**native.row(202), "Session": session, "LogonType": kind}
    binding = capture_windows_login(55, expected_owner=_OWNER)
    assert binding == WindowsLoginBinding(_OWNER, 101, 1, _TICKS)
    assert binding.observe(credential_facilities=Availability.AVAILABLE).active
    assert native.tokens_closed == [77]


def test_another_account_cannot_borrow_runtime_desktop(native: _Native) -> None:
    native.peer_owner = _OTHER
    native.rows[101] = {**native.row(101), "Sid": _Sid(_OTHER)}
    with pytest.raises(RuntimeRefusalError) as caught:
        capture_windows_login(55, expected_owner=_OWNER)
    assert caught.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED
    assert native.tokens_closed == [77]


def test_same_account_peer_uses_current_desktop_but_old_binding_expires(native: _Native) -> None:
    original = WindowsLoginBinding(_OWNER, 101, 1, _TICKS)
    native.ids = (101, 202)
    native.rows[202] = native.row(202)
    native.current_witness = WindowsDesktopLogon(_OWNER, 202, 1, _LOGON_SID)
    assert capture_windows_login(55, expected_owner=_OWNER) == WindowsLoginBinding(_OWNER, 202, 1, _TICKS)
    observed = original.observe(credential_facilities=Availability.AVAILABLE)
    inventory = windows_login_inventory(expected_owner=_OWNER)
    assert not observed.active and observed.locked
    assert observed.unattended is LoginEligibility.INELIGIBLE
    assert observed.login_id == original.login_id
    assert inventory.logins == (WindowsLoginBinding(_OWNER, 202, 1, _TICKS),)
    assert not inventory.complete and inventory.eligibility is LoginEligibility.ELIGIBLE
    assert not native.allocations and len(native.freed) == native.query_reads


@pytest.mark.parametrize(
    "rows",
    [({"SessionId": True, "State": 0},), ({"SessionId": 1, "State": 0}, {"SessionId": 1, "State": 4}), []],
)
def test_malformed_wts_inventory_never_corroborates_absence(native: _Native, rows: object) -> None:
    native.wts = rows
    native.query_error = 7022
    result = windows_login_inventory(expected_owner=_OWNER)
    assert result == RuntimeLoginInventory((), False)
    assert native.lsa_reads == native.query_reads == 0
