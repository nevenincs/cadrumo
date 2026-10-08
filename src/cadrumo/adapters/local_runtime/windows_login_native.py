"""Strict native LSA, token and WTS inventory decoding for Windows login provenance."""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

WINDOWS_MAX_LOGONS = 4096


@dataclass(frozen=True)
class WindowsLogonRecord:
    """Validated native LSA logon coordinates and optional aware timestamp."""

    kind: int
    session: int
    owner: str
    logon_time: datetime | None


def read_windows_logon(authentication_id: int) -> WindowsLogonRecord:
    """Read only an exactly addressed and strictly typed native LSA logon."""
    if sys.platform != "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    from datetime import UTC

    import win32security

    # The installed binding returns a mapping; some stub versions declare a
    # tuple. Validate the native boundary instead of trusting either annotation.
    raw = cast(object, win32security.LsaGetLogonSessionData(authentication_id))
    if not isinstance(raw, Mapping):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    fields = cast(Mapping[str, object], raw)
    kind, session, sid = fields.get("LogonType"), fields.get("Session"), fields.get("Sid")
    create_sid = cast(Callable[[int, None], object], win32security.CreateWellKnownSid)
    sid_type = type(create_sid(win32security.WinNullSid, None))
    if _logon_coordinates_refused(kind, session, sid, sid_type, fields, authentication_id):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    instant = fields.get("LogonTime")
    logon_time = instant.astimezone(UTC) if isinstance(instant, datetime) and instant.utcoffset() is not None else None
    convert_sid = cast(Callable[[object], str], win32security.ConvertSidToStringSid)
    return WindowsLogonRecord(cast(int, kind), cast(int, session), convert_sid(sid), logon_time)


@dataclass(frozen=True)
class WindowsTokenIdentity:
    """Validated native token owner, authentication context and session."""

    owner: str
    authentication_id: int
    session_id: int


def read_windows_token_identity(token: int) -> WindowsTokenIdentity:
    """Read strict token coordinates from the caller's retained native handle."""
    import win32security

    information = cast(Callable[[int, int], object], win32security.GetTokenInformation)
    user = information(token, win32security.TokenUser)
    statistics = information(token, win32security.TokenStatistics)
    session = information(token, win32security.TokenSessionId)
    create_sid = cast(Callable[[int, None], object], win32security.CreateWellKnownSid)
    sid_type = type(create_sid(win32security.WinNullSid, None))
    if not isinstance(user, tuple) or not isinstance(statistics, Mapping):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    fields = cast(tuple[object, ...], user)
    authentication = cast(Mapping[str, object], statistics).get("AuthenticationId")
    if (
        len(fields) != 2
        or not isinstance(fields[0], sid_type)
        or type(authentication) is not int
        or not -(2**63) <= authentication < 2**63
        or authentication == 0
        or type(session) is not int
        or not 0 <= session <= 0xFFFFFFFF
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    convert_sid = cast(Callable[[object], str], win32security.ConvertSidToStringSid)
    return WindowsTokenIdentity(convert_sid(fields[0]), authentication, session)


def windows_logon_ids() -> tuple[int, ...]:
    """Validate the complete native LUID array before processing any rows."""
    import win32security

    raw: object = win32security.LsaEnumerateLogonSessions()
    if (
        not isinstance(raw, tuple)
        or len(raw) > WINDOWS_MAX_LOGONS
        or any(type(value) is not int or value == 0 or not -(2**63) <= value < 2**63 for value in raw)
        or len(set(raw)) != len(raw)
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    return tuple(sorted(int(value) for value in raw))


def windows_desktop_sessions() -> tuple[tuple[int, int], ...]:
    """Read the local WTS inventory under its native Query Information permission."""
    import win32ts

    raw: object = win32ts.WTSEnumerateSessions(win32ts.WTS_CURRENT_SERVER_HANDLE, 1, 0)
    if not isinstance(raw, tuple) or len(raw) > WINDOWS_MAX_LOGONS:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    result: list[tuple[int, int]] = []
    for row in raw:
        result.append(_validated_desktop_session_row(row))
    if len({session for session, _ in result}) != len(result):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    return tuple(sorted(result))


def _logon_coordinates_refused(
    kind: object,
    session: object,
    sid: object,
    sid_type: type,
    fields: Mapping[str, object],
    authentication_id: int,
) -> bool:
    """Refuse native LSA field type, range or addressed identity disagreement."""
    return (
        type(kind) is not int
        or not 0 <= kind <= 4294967295
        or type(session) is not int
        or (not 0 <= session <= 4294967295)
        or (not isinstance(sid, sid_type))
        or (type(fields.get("LogonId")) is not int)
        or (fields.get("LogonId") != authentication_id)
    )


def _validated_desktop_session_row(row: object) -> tuple[int, int]:
    """Refuse malformed WTS session rows before they can corroborate native absence."""
    if not isinstance(row, Mapping):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    fields = cast(Mapping[str, object], row)
    session, state = fields.get("SessionId"), fields.get("State")
    if type(session) is not int or not 0 <= session <= 0xFFFFFFFF or type(state) is not int or not 0 <= state <= 9:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    return session, state
