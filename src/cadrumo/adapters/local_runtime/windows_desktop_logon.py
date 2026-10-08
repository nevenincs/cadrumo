"""Current-session authentication witness from native token and WinSta0 metadata.

This supports the calling process's session only. It neither inventories other
logins nor grants unattended authority. Native calls are synchronous; bounded
buffers do not imply a cancellable native-call deadline. No ACL is modified.
"""

from __future__ import annotations

import ctypes
import os
import sys
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import cast

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

_WINDOWS_DLL_LOADER = "WinDLL"
_SID_MAX_BYTES = 68
_TEXT_MAX_BYTES = 512
_MAX_GROUPS = 4096


@dataclass(frozen=True, slots=True, repr=False)
class WindowsDesktopLogon:
    """Native current-desktop identity, for exact retained-peer comparison only."""

    os_owner_id: str
    authentication_id: int
    session_id: int
    logon_sid: str


@dataclass(frozen=True, slots=True, repr=False)
class _TokenSnapshot:
    os_owner_id: str
    authentication_id: int
    session_id: int
    logon_sid: str
    logon_sid_count: int
    logon_kind: int
    token_id: int
    modified_id: int


@dataclass(frozen=True, slots=True, repr=False)
class _StationSnapshot:
    name: str
    kind: str
    flags: int
    associated_sid: str | None
    inherited: bool
    reserved: bool


class _UserObjectFlags(ctypes.Structure):
    _fields_ = (("inherit", ctypes.c_int32), ("reserved", ctypes.c_int32), ("flags", ctypes.c_uint32))


def _unavailable() -> RuntimeRefusalError:
    return RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


def _sid_text_valid(value: str) -> bool:
    parts = value.split("-")
    if not 4 <= len(parts) <= 18 or parts[:2] != ["S", "1"]:
        return False
    for index, part in enumerate(parts[2:]):
        if not part.isascii() or not part.isdecimal() or len(part) > 15 or str(int(part)) != part:
            return False
        if int(part) > (2**48 - 1 if index == 0 else 2**32 - 1):
            return False
    return True


def _logon_sid_valid(value: str) -> bool:
    return _sid_text_valid(value) and len(value.split("-")) == 6 and value.startswith("S-1-5-5-")


def _validated_witness(
    before_token: _TokenSnapshot,
    before_station: _StationSnapshot,
    after_token: _TokenSnapshot,
    after_station: _StationSnapshot,
) -> WindowsDesktopLogon:
    if before_token != after_token or before_station != after_station:
        raise _unavailable()
    token, station = before_token, before_station
    if (
        not _native_token_origin_is_valid(token)
        or not _native_token_role_is_valid(token)
        or not _native_token_generation_is_valid(token)
        or not _native_station_association_is_valid(station, token)
    ):
        raise _unavailable()
    return WindowsDesktopLogon(token.os_owner_id, token.authentication_id, token.session_id, token.logon_sid)


def _windows_library(name: str) -> ctypes.CDLL:
    loader = cast(Callable[..., ctypes.CDLL], getattr(ctypes, _WINDOWS_DLL_LOADER))
    return loader(name, use_last_error=True)


@contextmanager
def _owned_handle(handle: int, close: Callable[[int], bool]) -> Generator[int]:
    primary: BaseException | None = None
    try:
        yield handle
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            if not close(handle):
                raise _unavailable()
        except BaseException:
            if primary is None:
                raise _unavailable() from None
            primary.add_note("Owned native desktop witness handle cleanup failed")


def _native_sid_text(value: object) -> str:
    import win32security

    create_sid = cast(Callable[[int, None], object], win32security.CreateWellKnownSid)
    sid_type = type(create_sid(win32security.WinNullSid, None))
    if not isinstance(value, sid_type):
        raise _unavailable()
    convert_sid = cast(Callable[[object], object], win32security.ConvertSidToStringSid)
    result = convert_sid(value)
    if not isinstance(result, str) or not _sid_text_valid(result):
        raise _unavailable()
    return result


def _luid(value: object) -> int:
    if type(value) is not int or not -(2**63) <= value < 2**63 or value == 0:
        raise _unavailable()
    return value


def _token_snapshot(process: int) -> _TokenSnapshot:
    import win32api
    import win32con
    import win32security

    open_token = cast(Callable[[int, int], int], win32security.OpenProcessToken)
    information = cast(Callable[[int, int], object], win32security.GetTokenInformation)
    token = open_token(process, 8)

    def close_token(_handle: int) -> bool:
        win32api.CloseHandle(token)
        return True

    with _owned_handle(int(token), close_token):
        raw_user = information(token, win32security.TokenUser)
        statistics = information(token, win32security.TokenStatistics)
        session = information(token, win32security.TokenSessionId)
        primary_type = information(token, win32security.TokenType)
        groups = information(token, win32security.TokenGroups)
        if not _native_token_fields_are_supported(raw_user, statistics, session, primary_type, groups):
            raise _unavailable()
        session = cast(int, session)
        user_fields = cast(tuple[object, ...], raw_user)
        statistic_fields = cast(Mapping[str, object], statistics)
        group_rows = cast(Sequence[object], groups)
        if len(user_fields) != 2 or not 1 <= len(group_rows) <= _MAX_GROUPS:
            raise _unavailable()
        owner = _native_sid_text(user_fields[0])
        authentication = _luid(statistic_fields.get("AuthenticationId"))
        token_id = _luid(statistic_fields.get("TokenId"))
        modified_id = _luid(statistic_fields.get("ModifiedId"))
        logon_sids: list[str] = []
        mask = win32con.SE_GROUP_LOGON_ID & 0xFFFFFFFF
        _append_native_logon_sids(logon_sids, group_rows, mask)
        if len(logon_sids) != 1 or not _logon_sid_valid(logon_sids[0]):
            raise _unavailable()
        # Keep this defining module independent of windows_login. Native LSA
        # metadata establishes interactive kind; timestamps are not correlated.
        read_logon = cast(Callable[[int], object], win32security.LsaGetLogonSessionData)
        logon = read_logon(authentication)
        kind = _validated_native_logon_kind(logon, authentication, owner, session)
        return _TokenSnapshot(
            owner, authentication, session, logon_sids[0], len(logon_sids), kind, token_id, modified_id
        )


def _object_bytes(user: ctypes.CDLL, station: int, index: int, maximum: int) -> bytes:
    query = user.GetUserObjectInformationW
    query.argtypes = (
        ctypes.c_void_p,
        ctypes.c_int32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
    )
    query.restype = ctypes.c_int32
    buffer, needed = ctypes.create_string_buffer(maximum), ctypes.c_uint32()
    if not query(station, index, buffer, maximum, ctypes.byref(needed)) or needed.value > maximum:
        raise _unavailable()
    return buffer.raw[: needed.value]


def _object_text(payload: bytes) -> str:
    if not 2 <= len(payload) <= _TEXT_MAX_BYTES or len(payload) % 2:
        raise _unavailable()
    try:
        text = payload.decode("utf-16-le")
    except UnicodeError:
        raise _unavailable() from None
    if not text.endswith("\0") or "\0" in text[:-1]:
        raise _unavailable()
    return text[:-1]


def _station_snapshot(user: ctypes.CDLL, handle: int) -> _StationSnapshot:
    import win32security

    name = _object_text(_object_bytes(user, handle, 2, _TEXT_MAX_BYTES))
    kind = _object_text(_object_bytes(user, handle, 3, _TEXT_MAX_BYTES))
    payload = _object_bytes(user, handle, 1, ctypes.sizeof(_UserObjectFlags))
    if len(payload) != ctypes.sizeof(_UserObjectFlags):
        raise _unavailable()
    flags = _UserObjectFlags.from_buffer_copy(payload)
    if flags.inherit not in (0, 1) or flags.reserved not in (0, 1):
        raise _unavailable()
    sid_bytes = _object_bytes(user, handle, 4, _SID_MAX_BYTES)
    if not 8 <= len(sid_bytes) <= _SID_MAX_BYTES or (len(sid_bytes) - 8) % 4:
        raise _unavailable()
    advapi = _windows_library("advapi32")
    valid = advapi.IsValidSid
    valid.argtypes, valid.restype = (ctypes.c_void_p,), ctypes.c_int32
    length = advapi.GetLengthSid
    length.argtypes, length.restype = (ctypes.c_void_p,), ctypes.c_uint32
    owned_sid = ctypes.create_string_buffer(sid_bytes, _SID_MAX_BYTES)
    if not valid(owned_sid) or int(length(owned_sid)) != len(sid_bytes):
        raise _unavailable()
    sid_from_bytes = cast(Callable[[bytes], object], win32security.SID)
    sid = _native_sid_text(sid_from_bytes(sid_bytes))
    return _StationSnapshot(name, kind, int(flags.flags), sid, bool(flags.inherit), bool(flags.reserved))


def current_windows_desktop_logon() -> WindowsDesktopLogon:
    """Return an exact current-session witness or a nonprompting typed refusal.

    Callers must independently compare retained peer TokenOwner/AuthID/Session
    and retain their originating WTS generation. This cannot authorize a peer
    from another session or establish a complete inventory of desktop logins.
    """
    if sys.platform != "win32" or sys.getwindowsversion().major < 10:
        raise _unavailable()
    import pywintypes

    try:
        kernel, user = _windows_library("kernel32"), _windows_library("user32")
        open_process = kernel.OpenProcess
        open_process.argtypes, open_process.restype = (
            (ctypes.c_uint32, ctypes.c_int32, ctypes.c_uint32),
            ctypes.c_void_p,
        )
        close_process = kernel.CloseHandle
        close_process.argtypes, close_process.restype = (ctypes.c_void_p,), ctypes.c_int32
        process: object = open_process(0x00100000 | 0x1000, False, os.getpid())
        if type(process) is not int or process <= 0:
            raise _unavailable()
        with _owned_handle(process, lambda handle: bool(close_process(handle))):
            before_token = _token_snapshot(process)
            open_station = user.OpenWindowStationW
            open_station.argtypes = (ctypes.c_wchar_p, ctypes.c_int32, ctypes.c_uint32)
            open_station.restype = ctypes.c_void_p
            close_station = user.CloseWindowStation
            close_station.argtypes, close_station.restype = (ctypes.c_void_p,), ctypes.c_int32
            station: object = open_station("WinSta0", False, 0x00020000 | 0x0002)
            if type(station) is not int or station <= 0:
                raise _unavailable()
            with _owned_handle(station, lambda handle: bool(close_station(handle))):
                before_station = _station_snapshot(user, station)
                after_token = _token_snapshot(process)
                after_station = _station_snapshot(user, station)
                return _validated_witness(before_token, before_station, after_token, after_station)
    except (pywintypes.error, OSError, KeyError, TypeError, ValueError, OverflowError):
        raise _unavailable() from None


def _native_token_origin_is_valid(token: _TokenSnapshot) -> bool:
    """Require canonical owner/logon SID and exact native authentication/session scalars."""
    return not (
        not _sid_text_valid(token.os_owner_id)
        or not _logon_sid_valid(token.logon_sid)
        or token.os_owner_id == token.logon_sid
        or (type(token.authentication_id) is not int)
        or (not -(2**63) <= token.authentication_id < 2**63)
        or (token.authentication_id == 0)
        or (type(token.session_id) is not int)
        or (not 0 < token.session_id <= 4294967295)
    )


def _native_token_role_is_valid(token: _TokenSnapshot) -> bool:
    """Require one logon SID and a supported interactive native logon kind."""
    return not (
        type(token.logon_sid_count) is not int
        or token.logon_sid_count != 1
        or type(token.logon_kind) is not int
        or (token.logon_kind not in (2, 10, 11, 12))
    )


def _native_token_generation_is_valid(token: _TokenSnapshot) -> bool:
    """Require exact nonzero native token and modification generation identities."""
    return not (
        type(token.token_id) is not int
        or not -(2**63) <= token.token_id < 2**63
        or token.token_id == 0
        or (type(token.modified_id) is not int)
        or (not -(2**63) <= token.modified_id < 2**63)
        or (token.modified_id == 0)
    )


def _native_station_association_is_valid(station: _StationSnapshot, token: _TokenSnapshot) -> bool:
    """Require exact WinSta0 metadata associated with this token's logon SID."""
    return not (
        station.name.casefold() != "winsta0"
        or station.kind != "WindowStation"
        or type(station.flags) is not int
        or (station.flags != 1)
        or (station.inherited is not False)
        or (station.reserved is not False)
        or (station.associated_sid != token.logon_sid)
    )


def _native_token_fields_are_supported(
    raw_user: object, statistics: object, session: object, primary_type: object, groups: object
) -> bool:
    """Require the closed native token field shapes before interpreting their contents."""
    return not (
        not isinstance(raw_user, tuple)
        or not isinstance(statistics, Mapping)
        or type(session) is not int
        or (not 0 < session <= 4294967295)
        or (type(primary_type) is not int)
        or (primary_type != 1)
        or (not isinstance(groups, (list, tuple)))
    )


def _append_native_logon_sids(logon_sids: list[str], group_rows: Sequence[object], mask: int) -> None:
    """Validate every native group tuple and retain only exact logon-role SIDs."""
    for row in group_rows:
        if not isinstance(row, tuple):
            raise _unavailable()
        group_fields = cast(tuple[object, ...], row)
        if len(group_fields) != 2:
            raise _unavailable()
        attributes = group_fields[1]
        if type(attributes) is not int:
            raise _unavailable()
        sid = _native_sid_text(group_fields[0])
        if attributes & mask == mask:
            logon_sids.append(sid)


def _validated_native_logon_kind(logon: object, authentication: int, owner: str, session: int) -> int:
    """Cross-check native LSA authentication, owner, session, and interactive kind."""
    if not isinstance(logon, Mapping):
        raise _unavailable()
    logon_fields = cast(Mapping[str, object], logon)
    kind = logon_fields.get("LogonType")
    logon_session = logon_fields.get("Session")
    if (
        _luid(logon_fields.get("LogonId")) != authentication
        or _native_sid_text(logon_fields.get("Sid")) != owner
        or type(logon_session) is not int
        or logon_session != session
        or type(kind) is not int
        or kind not in (2, 10, 11, 12)
    ):
        raise _unavailable()
    return kind
