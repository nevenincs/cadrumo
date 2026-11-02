"""Portable console snapshot reduction and stability checks."""

from __future__ import annotations

import ctypes
from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest

from cadrumo.application.user_profile.access_contracts import OsLockState

from .. import macos_console

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _snapshot() -> dict[str, Any]:
    return {
        "IOConsoleLocked": False,
        "IOConsoleUsers": [
            {
                "kCGSSessionUserIDKey": 501,
                "kCGSSessionAuditIDKey": 100022,
                "kCGSSessionOnConsoleKey": True,
                "kCGSessionLoginDoneKey": True,
            }
        ],
    }


def _state(snapshot: object, owner: str = "501", session_id: int = 100022) -> OsLockState:
    return macos_console.console_lock_state(snapshot, owner, session_id)


@pytest.mark.parametrize("locked,expected", [(False, OsLockState.UNLOCKED), (True, OsLockState.LOCKED)])
def test_explicit_root_lock_state(locked: bool, expected: OsLockState) -> None:
    snapshot = _snapshot()
    snapshot["IOConsoleLocked"] = locked
    assert _state(snapshot) is expected


def test_explicit_per_session_lock_overrides_unlocked_root() -> None:
    snapshot = _snapshot()
    snapshot["IOConsoleUsers"][0]["CGSSessionScreenIsLocked"] = True
    assert _state(snapshot) is OsLockState.LOCKED


@pytest.mark.parametrize("session_flag", [None, False])
def test_absent_root_lock_cannot_prove_unlock(session_flag: bool | None) -> None:
    snapshot = _snapshot()
    del snapshot["IOConsoleLocked"]
    if session_flag is not None:
        snapshot["IOConsoleUsers"][0]["CGSSessionScreenIsLocked"] = session_flag
    assert _state(snapshot) is OsLockState.UNKNOWN


@pytest.mark.parametrize("root_lock", [0, 1, "false", None])
def test_root_lock_must_be_bool(root_lock: object) -> None:
    snapshot = _snapshot()
    snapshot["IOConsoleLocked"] = root_lock
    assert _state(snapshot) is OsLockState.UNKNOWN


@pytest.mark.parametrize("session_lock", [0, 1, "false", None])
def test_session_lock_must_be_bool_if_present(session_lock: object) -> None:
    snapshot = _snapshot()
    snapshot["IOConsoleUsers"][0]["CGSSessionScreenIsLocked"] = session_lock
    assert _state(snapshot) is OsLockState.UNKNOWN


@pytest.mark.parametrize(
    "key,value",
    [
        ("kCGSSessionUserIDKey", 502),
        ("kCGSSessionUserIDKey", True),
        ("kCGSSessionUserIDKey", "501"),
        ("kCGSSessionAuditIDKey", 100023),
        ("kCGSSessionAuditIDKey", True),
        ("kCGSSessionAuditIDKey", "100022"),
        ("kCGSSessionOnConsoleKey", False),
        ("kCGSSessionOnConsoleKey", 1),
        ("kCGSessionLoginDoneKey", False),
        ("kCGSessionLoginDoneKey", 1),
    ],
)
def test_wrong_identity_or_nonconsole_session_cannot_unlock(key: str, value: object) -> None:
    snapshot = _snapshot()
    snapshot["IOConsoleUsers"][0][key] = value
    assert _state(snapshot) is OsLockState.UNKNOWN


def test_bool_identity_is_not_an_integer_identity() -> None:
    snapshot = _snapshot()
    snapshot["IOConsoleUsers"][0]["kCGSSessionUserIDKey"] = True
    snapshot["IOConsoleUsers"][0]["kCGSSessionAuditIDKey"] = True
    assert _state(snapshot, "1", 1) is OsLockState.UNKNOWN
    assert _state(_snapshot(), "501", True) is OsLockState.UNKNOWN
    assert _state(_snapshot(), "not-a-uid") is OsLockState.UNKNOWN


@pytest.mark.parametrize("session_id", [0, -1, 0xFFFFFFFE, 0xFFFFFFFF])
def test_reserved_session_ids_are_unknown(session_id: int) -> None:
    snapshot = _snapshot()
    snapshot["IOConsoleUsers"][0]["kCGSSessionAuditIDKey"] = session_id
    assert _state(snapshot, session_id=session_id) is OsLockState.UNKNOWN


def test_duplicate_matching_sessions_are_ambiguous() -> None:
    snapshot = _snapshot()
    snapshot["IOConsoleUsers"].append(deepcopy(snapshot["IOConsoleUsers"][0]))
    assert _state(snapshot) is OsLockState.UNKNOWN


def test_multiple_console_users_are_ambiguous() -> None:
    snapshot = _snapshot()
    other = deepcopy(snapshot["IOConsoleUsers"][0])
    other["kCGSSessionAuditIDKey"] = 100023
    snapshot["IOConsoleUsers"].append(other)
    assert _state(snapshot) is OsLockState.UNKNOWN


@pytest.mark.parametrize("users", [None, {}, "users", [], [None], ["user"], [None] * 257])
def test_malformed_user_lists_are_unknown(users: object) -> None:
    snapshot = _snapshot()
    snapshot["IOConsoleUsers"] = users
    assert _state(snapshot) is OsLockState.UNKNOWN


@pytest.mark.parametrize("snapshot", [None, [], "snapshot", 0, {}])
def test_malformed_snapshots_are_unknown(snapshot: object) -> None:
    assert _state(snapshot) is OsLockState.UNKNOWN


def test_two_equal_snapshots_return_console_state(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshots = iter([_snapshot(), _snapshot()])
    monkeypatch.setattr(macos_console.sys, "platform", "darwin")
    monkeypatch.setattr(macos_console, "_registry_snapshot", lambda: next(snapshots))
    assert macos_console.observe_console_lock("501", 100022) is OsLockState.UNLOCKED


@pytest.mark.parametrize("change", ["lock", "session", "lock-type", "nested-type"])
def test_changed_snapshots_are_unknown(change: str, monkeypatch: pytest.MonkeyPatch) -> None:
    first, second = _snapshot(), _snapshot()
    if change == "lock":
        first["IOConsoleLocked"] = True
    elif change == "session":
        first["IOConsoleUsers"][0]["kCGSSessionAuditIDKey"] = 100023
    elif change == "lock-type":
        first["IOConsoleLocked"] = 0
    else:
        first["IOConsoleUsers"][0]["kCGSessionLoginDoneKey"] = 1
    snapshots = iter([first, second])
    monkeypatch.setattr(macos_console.sys, "platform", "darwin")
    monkeypatch.setattr(macos_console, "_registry_snapshot", lambda: next(snapshots))
    assert macos_console.observe_console_lock("501", 100022) is OsLockState.UNKNOWN


@pytest.mark.parametrize("first,second", [(None, {}), ({}, None), ([], {})])
def test_missing_snapshots_are_unknown(first: object, second: object, monkeypatch: pytest.MonkeyPatch) -> None:
    snapshots = iter([first, second])
    monkeypatch.setattr(macos_console.sys, "platform", "darwin")
    monkeypatch.setattr(macos_console, "_registry_snapshot", lambda: next(snapshots))
    assert macos_console.observe_console_lock("501", 100022) is OsLockState.UNKNOWN


@pytest.mark.parametrize("error", [OSError, ValueError, TypeError, AttributeError])
def test_native_snapshot_errors_are_unknown(error: type[Exception], monkeypatch: pytest.MonkeyPatch) -> None:
    def fail() -> None:
        raise error("unavailable")

    monkeypatch.setattr(macos_console.sys, "platform", "darwin")
    monkeypatch.setattr(macos_console, "_registry_snapshot", fail)
    assert macos_console.observe_console_lock("501", 100022) is OsLockState.UNKNOWN


def test_registry_snapshot_releases_error_document_and_root_on_encode_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class NativeFunction:
        def __init__(self, result: Any = None) -> None:
            self.result = result
            self.calls: list[tuple[Any, ...]] = []

        def __call__(self, *args: Any) -> Any:
            self.calls.append(args)
            return self.result(*args) if callable(self.result) else self.result

    def properties(_root: int, document: object, _allocator: object, _options: int) -> int:
        ctypes.cast(document, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.c_void_p(11)
        return 0

    def encode(_allocator: object, _document: object, _format: int, _options: int, error: object) -> None:
        ctypes.cast(error, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.c_void_p(22)
        return None

    iokit = SimpleNamespace(
        IORegistryGetRootEntry=NativeFunction(7),
        IORegistryEntryCreateCFProperties=NativeFunction(properties),
        IOObjectRelease=NativeFunction(),
    )
    cf = SimpleNamespace(
        CFPropertyListCreateData=NativeFunction(encode),
        CFDataGetLength=NativeFunction(),
        CFDataGetBytePtr=NativeFunction(),
        CFRelease=NativeFunction(),
    )
    monkeypatch.setattr(macos_console.ctypes, "CDLL", lambda path: iokit if "IOKit" in path else cf)
    assert macos_console._registry_snapshot() is None
    assert [args[0].value for args in cf.CFRelease.calls] == [22, 11]
    assert iokit.IOObjectRelease.calls == [(7,)]
