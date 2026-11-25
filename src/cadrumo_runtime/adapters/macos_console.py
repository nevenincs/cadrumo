"""Fresh kernel console-lock evidence bound to one macOS audit session.

Apple XNU IOService::updateConsoleUsers publishes IOConsoleLocked and
IOConsoleUsers on the registry root; IOResources::setProperties requires
administrator privilege or the system entitlement. These are private schema
keys read through public IOKit APIs: missing or changed schema fails closed.
An absent per-session lock key is never itself evidence of unlock.
"""

from __future__ import annotations

import ctypes
import logging
import plistlib
import sys
from collections.abc import Callable
from typing import Any

from cadrumo.application.user_profile.access_contracts import OsLockState
from cadrumo.core.diagnostic_log import diagnostic_event
from cadrumo.core.logging import get_logger

_MAX_PROPERTY_BYTES = 1024 * 1024
_log = get_logger(__name__)


def _unavailable(reason: str) -> OsLockState:
    diagnostic_event(
        _log,
        "macos_console_observation_unavailable",
        fields={"reason_code": reason},
        level=logging.DEBUG,
    )
    return OsLockState.UNKNOWN


def _well_formed_query(value: object, owner: str, session_id: int) -> dict[Any, Any] | None:
    if (
        not isinstance(value, dict)
        or not owner.isdecimal()
        or type(session_id) is not int
        or not 0 < session_id < 0xFFFFFFFE
    ):
        return None
    return value


def _console_users(registry: dict[Any, Any]) -> list[Any] | None:
    users = registry.get("IOConsoleUsers")
    if not isinstance(users, list) or not users or len(users) > 256:
        return None
    return users


def _own_session(users: list[Any], owner: int, session_id: int) -> dict[Any, Any] | None:
    """Return the one console-user row of this owner and audit session, or ``None`` when it is not exactly one."""
    matches = [
        row
        for row in users
        if isinstance(row, dict)
        and type(row.get("kCGSSessionUserIDKey")) is int
        and row["kCGSSessionUserIDKey"] == owner
        and type(row.get("kCGSSessionAuditIDKey")) is int
        and row["kCGSSessionAuditIDKey"] == session_id
    ]
    return matches[0] if len(matches) == 1 else None


def _console_session_state(registry: dict[Any, Any], users: list[Any], selected: dict[Any, Any]) -> OsLockState:
    # Unlock is a property of the current console, not any background GUI or
    # SSH session of the same account. Ambiguous console membership refuses.
    console = [row for row in users if isinstance(row, dict) and row.get("kCGSSessionOnConsoleKey") is True]
    if len(console) != 1 or console[0] is not selected or selected.get("kCGSessionLoginDoneKey") is not True:
        return OsLockState.UNKNOWN
    locked = registry.get("IOConsoleLocked")
    if type(locked) is not bool:
        return OsLockState.UNKNOWN
    return OsLockState.LOCKED if locked else OsLockState.UNLOCKED


def _resolved_session(
    value: object, owner: str, session_id: int
) -> tuple[dict[Any, Any], list[Any], dict[Any, Any]] | None:
    """Return the registry, its console users and the owner's one session row, or ``None`` when any is unusable."""
    registry = _well_formed_query(value, owner, session_id)
    if registry is None:
        return None
    users = _console_users(registry)
    if users is None:
        return None
    selected = _own_session(users, int(owner), session_id)
    return None if selected is None else (registry, users, selected)


def console_lock_state(value: object, owner: str, session_id: int) -> OsLockState:
    """Reduce a native registry snapshot without accepting inferred unlock."""
    resolved = _resolved_session(value, owner, session_id)
    if resolved is None:
        return OsLockState.UNKNOWN
    registry, users, selected = resolved
    if selected.get("CGSSessionScreenIsLocked") is True:
        return OsLockState.LOCKED
    if "CGSSessionScreenIsLocked" in selected and type(selected["CGSSessionScreenIsLocked"]) is not bool:
        return OsLockState.UNKNOWN
    return _console_session_state(registry, users, selected)


def _release_native_owners(
    release: Callable[[ctypes.c_void_p], None],
    release_entry: Callable[[int], int],
    *,
    error: ctypes.c_void_p,
    data: ctypes.c_void_p | None,
    document: ctypes.c_void_p,
    root: int,
) -> None:
    """Release every native owner that was acquired, the error object first."""
    if error.value is not None:
        release(error)
    if data:
        release(data)
    if document.value is not None:
        release(document)
    if root:
        release_entry(root)


def registry_snapshot() -> object:
    """Copy a bounded registry-root property list; release every native owner."""
    iokit = ctypes.CDLL("/System/Library/Frameworks/IOKit.framework/IOKit")
    cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    pointer = ctypes.c_void_p
    root_entry = iokit.IORegistryGetRootEntry
    root_entry.argtypes, root_entry.restype = (ctypes.c_uint32,), ctypes.c_uint32
    properties = iokit.IORegistryEntryCreateCFProperties
    properties.argtypes = (ctypes.c_uint32, ctypes.POINTER(pointer), pointer, ctypes.c_uint32)
    properties.restype = ctypes.c_int32
    release_entry = iokit.IOObjectRelease
    release_entry.argtypes, release_entry.restype = (ctypes.c_uint32,), ctypes.c_int32
    encode = cf.CFPropertyListCreateData
    encode.argtypes = (pointer, pointer, ctypes.c_long, ctypes.c_ulong, ctypes.POINTER(pointer))
    encode.restype = pointer
    length = cf.CFDataGetLength
    length.argtypes, length.restype = (pointer,), ctypes.c_long
    bytes_pointer = cf.CFDataGetBytePtr
    bytes_pointer.argtypes, bytes_pointer.restype = (pointer,), pointer
    release = cf.CFRelease
    release.argtypes, release.restype = (pointer,), None
    root, document, data, error = 0, pointer(), None, pointer()
    try:
        root = root_entry(0)  # kIOMainPortDefault
        if not root or properties(root, ctypes.byref(document), None, 0) != 0 or document.value is None:
            return None
        data = encode(None, document, 200, 0, ctypes.byref(error))  # binary plist v1
        if not data:
            return None
        size = length(data)
        address = bytes_pointer(data)
        if not address or not 0 < size <= _MAX_PROPERTY_BYTES:
            return None
        return plistlib.loads(ctypes.string_at(address, size))
    finally:
        _release_native_owners(release, release_entry, error=error, data=data, document=document, root=root)


def observe_console_lock(owner: str, session_id: int) -> OsLockState:
    """Read twice, refusing any intervening console identity/state change."""
    if sys.platform != "darwin":
        return OsLockState.UNKNOWN
    try:
        first = registry_snapshot()
        second = registry_snapshot()
        if not isinstance(first, dict) or not isinstance(second, dict):
            return _unavailable("console_snapshot_unavailable")
        keys = ("IOConsoleLocked", "IOConsoleUsers")
        # Property-list encoding preserves Boolean/integer distinctions that
        # Python's ordinary dictionary equality erases (False == 0).
        before = plistlib.dumps({key: first.get(key) for key in keys}, fmt=plistlib.FMT_BINARY)
        after = plistlib.dumps({key: second.get(key) for key in keys}, fmt=plistlib.FMT_BINARY)
        if before != after:
            return _unavailable("console_snapshot_changed")
        state = console_lock_state(second, owner, session_id)
        if state is OsLockState.UNKNOWN:
            return _unavailable("console_identity_or_lock_unknown")
        return state
    except (AttributeError, OSError, ValueError, TypeError, plistlib.InvalidFileException):
        return _unavailable("console_snapshot_error")
