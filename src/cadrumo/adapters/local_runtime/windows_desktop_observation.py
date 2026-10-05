"""Atomic Windows WTS desktop state and generation observation with owned native memory."""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError


class WindowsSessionLevel(ctypes.Structure):
    """Native WTS level-one session information fields."""

    _fields_ = (
        ("session_id", ctypes.c_uint32),
        ("state", ctypes.c_int32),
        ("flags", ctypes.c_int32),
        ("station", ctypes.c_uint16 * 33),
        ("user", ctypes.c_uint16 * 21),
        ("domain", ctypes.c_uint16 * 18),
        ("logon_time", ctypes.c_int64),
        ("connect_time", ctypes.c_int64),
        ("disconnect_time", ctypes.c_int64),
        ("last_input", ctypes.c_int64),
        ("current_time", ctypes.c_int64),
        ("counters", ctypes.c_uint32 * 6),
    )


class WindowsSessionInformation(ctypes.Structure):
    """Native tagged WTS session information buffer."""

    _fields_ = (("level", ctypes.c_uint32), ("data", WindowsSessionLevel))


@dataclass(frozen=True)
class WindowsDesktopObservation:
    """Only session lifecycle facts; native names and other account data are discarded."""

    session_id: int
    state: int
    flags: int
    logon_time: int
    os_owner_id: str


def _native_account_name(units: ctypes.Array[ctypes.c_uint16]) -> str:
    """Decode one terminated native name without accepting truncated identity."""
    values = tuple(units)
    if 0 not in values:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    value = b"".join(unit.to_bytes(2, "little") for unit in values[: values.index(0)]).decode("utf-16-le")
    if not value or any(ord(character) < 32 or character in "\\/" for character in value):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    return value


def _desktop_owner(data: WindowsSessionLevel) -> str:
    """Resolve the fully qualified account in the same atomic WTS snapshot."""
    import win32security

    domain, user = _native_account_name(data.domain), _native_account_name(data.user)
    sid, resolved_domain, kind = win32security.LookupAccountName(None, f"{domain}\\{user}")
    create_sid = cast(Callable[[int, None], object], win32security.CreateWellKnownSid)
    sid_type = type(create_sid(win32security.WinNullSid, None))
    if (
        not isinstance(sid, sid_type)
        or type(kind) is not int
        or kind != win32security.SidTypeUser
        or not isinstance(resolved_domain, str)
        or resolved_domain.casefold() != domain.casefold()
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    return win32security.ConvertSidToStringSid(sid)


def windows_desktop_observation(session_id: int) -> WindowsDesktopObservation:
    """Read the current WTS generation/lock state or refuse ambiguous evidence."""
    if sys.platform != "win32" or sys.getwindowsversion().major < 10 or session_id <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    library = ctypes.WinDLL("wtsapi32", use_last_error=True)
    query = library.WTSQuerySessionInformationW
    query.argtypes = (
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int32,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_uint32),
    )
    query.restype = ctypes.c_int32
    release = library.WTSFreeMemory
    release.argtypes = (ctypes.c_void_p,)
    release.restype = None
    buffer, count = ctypes.c_void_p(), ctypes.c_uint32()
    try:
        if not query(None, session_id, 25, ctypes.byref(buffer), ctypes.byref(count)):
            error = RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            error.__dict__["_wts_error_code"] = ctypes.get_last_error()
            raise error
        data = _validated_desktop_information(buffer, count, session_id)
        return WindowsDesktopObservation(
            int(data.session_id), int(data.state), int(data.flags), int(data.logon_time), _desktop_owner(data)
        )
    finally:
        if buffer.value:
            release(buffer)


def _validated_desktop_information(
    buffer: ctypes.c_void_p,
    count: ctypes.c_uint32,
    session_id: int,
) -> WindowsSessionLevel:
    """Require exact native buffer size and addressed WTS generation before projection."""
    if not buffer.value or count.value != ctypes.sizeof(WindowsSessionInformation):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    information = WindowsSessionInformation.from_buffer_copy(ctypes.string_at(buffer, count.value))
    data = cast(WindowsSessionLevel, information.data)
    if information.level != 1 or data.session_id != session_id or data.logon_time <= 0 or data.flags not in (0, 1):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    return data
