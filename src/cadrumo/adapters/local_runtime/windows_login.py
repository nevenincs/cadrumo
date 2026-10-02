"""Native logon provenance and fresh desktop-session observations for local authority."""

from __future__ import annotations

import ctypes
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.login import RuntimeLoginInventory
from ...application.user_profile.access_contracts import Availability, LoginEligibility, OsLoginContext
from .windows_desktop_logon import WindowsDesktopLogon, current_windows_desktop_logon

_MAX_LOGONS = 4096
_INVENTORY_SECONDS = 2.0


class _SessionLevel(ctypes.Structure):
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


class _SessionInformation(ctypes.Structure):
    _fields_ = (("level", ctypes.c_uint32), ("data", _SessionLevel))


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


def _desktop_owner(data: _SessionLevel) -> str:
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
        if not buffer.value or count.value != ctypes.sizeof(_SessionInformation):
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        information = _SessionInformation.from_buffer_copy(ctypes.string_at(buffer, count.value))
        data = information.data
        if information.level != 1 or data.session_id != session_id or data.logon_time <= 0 or data.flags not in (0, 1):
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        return WindowsDesktopObservation(
            int(data.session_id), int(data.state), int(data.flags), int(data.logon_time), _desktop_owner(data)
        )
    finally:
        if buffer.value:
            release(buffer)


@dataclass(frozen=True)
class WindowsLoginBinding:
    """Trusted, nonportable provenance captured from a retained native process handle."""

    os_owner_id: str
    authentication_id: int
    session_id: int
    desktop_logon_time: int

    @property
    def login_id(self) -> str:
        """Identify this exact token logon and desktop generation without a credential."""
        return f"windows:{self.authentication_id:x}:{self.session_id}:{self.desktop_logon_time}"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Reobserve this exact native login without recapturing a reused session ID."""
        return observe_windows_login(self, credential_facilities=credential_facilities)


@dataclass(frozen=True)
class _Logon:
    kind: int
    session: int
    owner: str
    logon_time: datetime | None


def _logon(authentication_id: int) -> _Logon:
    if sys.platform != "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    import win32security

    # The installed binding returns a mapping; some stub versions declare a
    # tuple. Validate the native boundary instead of trusting either annotation.
    raw: object = win32security.LsaGetLogonSessionData(authentication_id)
    if not isinstance(raw, Mapping):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    fields = cast(Mapping[str, object], raw)
    kind, session, sid = fields.get("LogonType"), fields.get("Session"), fields.get("Sid")
    create_sid = cast(Callable[[int, None], object], win32security.CreateWellKnownSid)
    sid_type = type(create_sid(win32security.WinNullSid, None))
    if (
        type(kind) is not int
        or not 0 <= kind <= 0xFFFFFFFF
        or type(session) is not int
        or not 0 <= session <= 0xFFFFFFFF
        or not isinstance(sid, sid_type)
        or type(fields.get("LogonId")) is not int
        or fields.get("LogonId") != authentication_id
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    instant = fields.get("LogonTime")
    logon_time = instant.astimezone(UTC) if isinstance(instant, datetime) and instant.utcoffset() is not None else None
    convert_sid = cast(Callable[[object], str], win32security.ConvertSidToStringSid)
    return _Logon(kind, session, convert_sid(sid), logon_time)


@dataclass(frozen=True)
class _TokenIdentity:
    owner: str
    authentication_id: int
    session_id: int


def _token_identity(token: int) -> _TokenIdentity:
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
    return _TokenIdentity(convert_sid(fields[0]), authentication, session)


def _matches_current_desktop(identity: _TokenIdentity, witness: WindowsDesktopLogon) -> bool:
    return (
        identity.owner == witness.os_owner_id
        and identity.authentication_id == witness.authentication_id
        and identity.session_id == witness.session_id
    )


def _require_logon_time(logon: _Logon) -> None:
    if logon.logon_time is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)


def _same_desktop(before: WindowsDesktopObservation, after: WindowsDesktopObservation) -> bool:
    """Retain the WTS generation; lock transitions do not create another login."""
    return (
        before.session_id == after.session_id
        and before.os_owner_id == after.os_owner_id
        and before.logon_time == after.logon_time
    )


def capture_windows_login(process_handle: int, *, expected_owner: str) -> WindowsLoginBinding:
    """Bind a retained peer to the current native desktop's exact authentication.

    Other sessions and authentication contexts need an independent native
    association and are unavailable here. LSA and WTS timestamps describe
    different events and are never compared as an authentication proof.
    """
    if sys.platform != "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    import pywintypes
    import win32api
    import win32security

    try:
        open_token = cast(Callable[[int, int], int], win32security.OpenProcessToken)
        token = open_token(process_handle, 8)
        try:
            identity = _token_identity(token)
            logon = _logon(identity.authentication_id)
            if (
                identity.owner != expected_owner
                or identity.session_id <= 0
                or logon.kind not in (2, 10, 11, 12)
                or logon.session != identity.session_id
                or logon.owner != identity.owner
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            _require_logon_time(logon)
            witness = current_windows_desktop_logon()
            if not _matches_current_desktop(identity, witness):
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            observation = windows_desktop_observation(identity.session_id)
            if observation.os_owner_id != identity.owner:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            verified = windows_desktop_observation(identity.session_id)
            if (
                not _same_desktop(observation, verified)
                or observation.state not in (0, 4)
                or verified.state not in (0, 4)
                or _logon(identity.authentication_id) != logon
                or _token_identity(token) != identity
                or current_windows_desktop_logon() != witness
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            return WindowsLoginBinding(
                identity.owner, identity.authentication_id, identity.session_id, observation.logon_time
            )
        finally:
            win32api.CloseHandle(token)
    except (pywintypes.error, KeyError, TypeError, ValueError, OverflowError):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE) from None


def observe_windows_login(binding: WindowsLoginBinding, *, credential_facilities: Availability) -> OsLoginContext:
    """Revalidate logon existence and WTS generation on each authority observation.

    Credential readiness is separately supplied by the owning native-store
    capability. Desktop presence alone never claims that key custody is usable.
    """
    if sys.platform != "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    import pywintypes

    try:
        witness = current_windows_desktop_logon()
        logon = _logon(binding.authentication_id)
        _require_logon_time(logon)
        observation = windows_desktop_observation(binding.session_id)
        verified = windows_desktop_observation(binding.session_id)
        if (
            not _same_desktop(observation, verified)
            or _logon(binding.authentication_id) != logon
            or current_windows_desktop_logon() != witness
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        valid = (
            _matches_current_desktop(
                _TokenIdentity(binding.os_owner_id, binding.authentication_id, binding.session_id), witness
            )
            and logon.kind in (2, 10, 11, 12)
            and logon.session == binding.session_id
            and logon.owner == binding.os_owner_id
            and observation.os_owner_id == binding.os_owner_id
            and observation.logon_time == binding.desktop_logon_time
            and observation.state in (0, 4)
            and verified.state in (0, 4)
        )
        return OsLoginContext(
            login_id=binding.login_id,
            os_owner_id=binding.os_owner_id,
            active=valid,
            locked=not valid or verified.flags == 0,
            unattended=LoginEligibility.ELIGIBLE if valid else LoginEligibility.INELIGIBLE,
            credential_facilities=credential_facilities,
        )
    except (pywintypes.error, RuntimeRefusalError, KeyError, TypeError, ValueError, OverflowError):
        return OsLoginContext(
            login_id=binding.login_id,
            os_owner_id=binding.os_owner_id,
            active=False,
            locked=True,
            unattended=LoginEligibility.UNKNOWN,
            credential_facilities=Availability.UNAVAILABLE,
        )


def _logon_ids() -> tuple[int, ...]:
    """Validate the complete native LUID array before processing any rows."""
    import win32security

    raw: object = win32security.LsaEnumerateLogonSessions()
    if (
        not isinstance(raw, tuple)
        or len(raw) > _MAX_LOGONS
        or any(type(value) is not int or value == 0 or not -(2**63) <= value < 2**63 for value in raw)
        or len(set(raw)) != len(raw)
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    return tuple(sorted(int(value) for value in raw))


def _desktop_sessions() -> tuple[tuple[int, int], ...]:
    """Read the local WTS inventory under its native Query Information permission."""
    import win32ts

    raw: object = win32ts.WTSEnumerateSessions(win32ts.WTS_CURRENT_SERVER_HANDLE, 1, 0)
    if not isinstance(raw, tuple) or len(raw) > _MAX_LOGONS:
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    result: list[tuple[int, int]] = []
    for row in raw:
        if not isinstance(row, Mapping):
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        session, state = row.get("SessionId"), row.get("State")
        if type(session) is not int or not 0 <= session <= 0xFFFFFFFF or type(state) is not int or not 0 <= state <= 9:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        result.append((session, state))
    if len({session for session, _ in result}) != len(result):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    return tuple(sorted(result))


def windows_login_inventory(*, expected_owner: str) -> RuntimeLoginInventory:
    """Observe owner desktop incarnations without client or manager assumptions.

    Counts and processing time are bounded; individual native calls have no
    cancellable deadline. Unreadable rows never establish complete absence.
    Account lookup may contact the system's trusted domain controllers.
    """
    unknown = RuntimeLoginInventory((), False)
    if sys.platform != "win32" or not 1 <= len(expected_owner) <= 256:
        return unknown
    import pywintypes

    deadline = time.monotonic() + _INVENTORY_SECONDS
    try:
        before = _logon_ids()
        desktops_before = _desktop_sessions()
        witness = current_windows_desktop_logon()
        if witness.os_owner_id != expected_owner:
            return unknown
        desktop_ids = {session for session, _ in desktops_before}
        # Current-session association cannot prove absence if its own LUID
        # disappeared or was excluded. Unreadable/unsupported other rows also
        # remain incomplete, even when a positive current witness is available.
        complete = witness.authentication_id in before
        current_verified = False
        logins: list[WindowsLoginBinding] = []
        for authentication_id in before:
            if time.monotonic() >= deadline:
                return unknown
            try:
                logon = _logon(authentication_id)
                if logon.owner != expected_owner or logon.kind not in (2, 10, 11, 12) or logon.session == 0:
                    continue
                if not _matches_current_desktop(_TokenIdentity(logon.owner, authentication_id, logon.session), witness):
                    complete = False
                    continue
                _require_logon_time(logon)
                try:
                    observation = windows_desktop_observation(logon.session)
                except RuntimeRefusalError as error:
                    # Naked NOT_FOUND may hide missing native query permission.
                    # Exclude only when successful WTS bookends corroborate it.
                    if (
                        error.__dict__.get("_wts_error_code") == 7022
                        and logon.session not in desktop_ids
                        and _logon(authentication_id) == logon
                    ):
                        complete = False
                        continue
                    raise
                if (
                    observation.os_owner_id != expected_owner
                    or observation.state not in (0, 4)
                    or logon.session not in desktop_ids
                ):
                    complete = False
                    continue
                verified = windows_desktop_observation(logon.session)
                if (
                    _logon(authentication_id) != logon
                    or not _same_desktop(observation, verified)
                    or verified.state not in (0, 4)
                ):
                    complete = False
                    continue
                logins.append(
                    WindowsLoginBinding(expected_owner, authentication_id, logon.session, verified.logon_time)
                )
                current_verified = True
            except (pywintypes.error, RuntimeRefusalError, KeyError, TypeError, ValueError, OverflowError):
                complete = False
        if (
            _desktop_sessions() != desktops_before
            or _logon_ids() != before
            or current_windows_desktop_logon() != witness
            or time.monotonic() >= deadline
        ):
            return unknown
        return RuntimeLoginInventory(tuple(logins), complete and current_verified)
    except (pywintypes.error, RuntimeRefusalError, KeyError, TypeError, ValueError, OverflowError):
        return unknown
