"""Native logon provenance and fresh desktop-session observations for local authority."""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Mapping
from dataclasses import dataclass

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.user_profile.access_contracts import Availability, LoginEligibility, OsLoginContext


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
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        if not buffer.value or count.value != ctypes.sizeof(_SessionInformation):
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        information = _SessionInformation.from_buffer_copy(ctypes.string_at(buffer, count.value))
        data = information.data
        if information.level != 1 or data.session_id != session_id or data.logon_time <= 0 or data.flags not in (0, 1):
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        return WindowsDesktopObservation(int(data.session_id), int(data.state), int(data.flags), int(data.logon_time))
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


def _logon(authentication_id: int) -> _Logon:
    if sys.platform != "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    import win32security

    # The installed binding returns a mapping; some stub versions declare a
    # tuple. Validate the native boundary instead of trusting either annotation.
    raw: object = win32security.LsaGetLogonSessionData(authentication_id)
    if not isinstance(raw, Mapping):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    kind, session, sid = raw.get("LogonType"), raw.get("Session"), raw.get("Sid")
    sid_type = type(win32security.CreateWellKnownSid(win32security.WinNullSid, None))
    if type(kind) is not int or type(session) is not int or not isinstance(sid, sid_type):
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    return _Logon(kind, session, win32security.ConvertSidToStringSid(sid))


def capture_windows_login(process_handle: int, *, expected_owner: str) -> WindowsLoginBinding:
    """Prove interactive logon provenance without enumerating another user's sessions."""
    if sys.platform != "win32":
        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
    import pywintypes
    import win32api
    import win32security

    try:
        token = win32security.OpenProcessToken(process_handle, 8)
        try:
            sid, _ = win32security.GetTokenInformation(token, win32security.TokenUser)
            owner = win32security.ConvertSidToStringSid(sid)
            statistics = win32security.GetTokenInformation(token, win32security.TokenStatistics)
            authentication_id = int(statistics["AuthenticationId"])
            session_id = int(win32security.GetTokenInformation(token, win32security.TokenSessionId))
            logon = _logon(authentication_id)
            if (
                owner != expected_owner
                or logon.kind not in (2, 10, 11, 12)
                or logon.session != session_id
                or session_id <= 0
                or logon.owner != owner
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            observation = windows_desktop_observation(session_id)
            if observation.state not in (0, 4):
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            return WindowsLoginBinding(owner, authentication_id, session_id, observation.logon_time)
        finally:
            win32api.CloseHandle(token)
    except (pywintypes.error, KeyError, TypeError, ValueError):
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
        logon = _logon(binding.authentication_id)
        observation = windows_desktop_observation(binding.session_id)
        valid = (
            logon.kind in (2, 10, 11, 12)
            and logon.session == binding.session_id
            and logon.owner == binding.os_owner_id
            and observation.logon_time == binding.desktop_logon_time
            and observation.state in (0, 4)
        )
        return OsLoginContext(
            login_id=binding.login_id,
            os_owner_id=binding.os_owner_id,
            active=valid,
            locked=not valid or observation.flags == 0,
            unattended=LoginEligibility.ELIGIBLE if valid else LoginEligibility.INELIGIBLE,
            credential_facilities=credential_facilities,
        )
    except (pywintypes.error, RuntimeRefusalError, KeyError, TypeError, ValueError):
        return OsLoginContext(
            login_id=binding.login_id,
            os_owner_id=binding.os_owner_id,
            active=False,
            locked=True,
            unattended=LoginEligibility.UNKNOWN,
            credential_facilities=Availability.UNAVAILABLE,
        )
