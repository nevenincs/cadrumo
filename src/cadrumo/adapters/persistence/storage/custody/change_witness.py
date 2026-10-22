"""Hold one custody observation until the OS reports a change to its directories.

Authority checks read custody at every boundary to see what another process has
published. Windows announces each change to a directory through a change
notification handle whose signaled state is read without touching the disk, so
a check reads custody again only when a watched directory changed, when the
observation is older than its maximum age, or when its owner invalidated it.
A directory that cannot be watched leaves every check reading custody itself.
"""

from __future__ import annotations

import sys
import time
import weakref
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from threading import Lock
from typing import Final, Protocol

MAXIMUM_OBSERVATION_AGE_SECONDS: Final = 0.5
"""The staleness Cadrumo already accepts for logons no OS notification covers."""

# FILE_NOTIFY_CHANGE_FILE_NAME | DIR_NAME | ATTRIBUTES | SIZE | LAST_WRITE | SECURITY
_CHANGES: Final = 0x001 | 0x002 | 0x004 | 0x008 | 0x010 | 0x100
_WAIT_OBJECT_0: Final = 0x000
_WAIT_TIMEOUT: Final = 0x102


@dataclass(frozen=True, slots=True)
class WatchedDirectory:
    """One directory whose changes invalidate the observation, with or without its subtree."""

    path: Path
    subtree: bool


class _ChangeNotifications(Protocol):
    def open(self, directory: WatchedDirectory) -> int | None: ...

    def signaled(self, handle: int) -> bool | None: ...

    def rearm(self, handle: int) -> bool: ...

    def close(self, handle: int) -> None: ...


class _WindowsChangeNotifications:
    """The kernel's directory change notification handles."""

    _first: Callable[[str, bool, int], int | None]
    _next: Callable[[int], int]
    _wait: Callable[[int, int], int]
    _close: Callable[[int], int]
    _invalid: int | None

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise OSError("directory change notifications are a Windows source")
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self._first = kernel.FindFirstChangeNotificationW
        self._first.argtypes, self._first.restype = (wintypes.LPCWSTR, wintypes.BOOL, wintypes.DWORD), wintypes.HANDLE
        self._next = kernel.FindNextChangeNotification
        self._next.argtypes, self._next.restype = (wintypes.HANDLE,), wintypes.BOOL
        self._wait = kernel.WaitForSingleObject
        self._wait.argtypes, self._wait.restype = (wintypes.HANDLE, wintypes.DWORD), wintypes.DWORD
        self._close = kernel.FindCloseChangeNotification
        self._close.argtypes, self._close.restype = (wintypes.HANDLE,), wintypes.BOOL
        self._invalid = wintypes.HANDLE(-1).value

    def open(self, directory: WatchedDirectory) -> int | None:
        handle = self._first(str(directory.path), directory.subtree, _CHANGES)
        return None if handle is None or handle == self._invalid else int(handle)

    def signaled(self, handle: int) -> bool | None:
        result = self._wait(handle, 0)
        if result == _WAIT_TIMEOUT:
            return False
        return True if result == _WAIT_OBJECT_0 else None

    def rearm(self, handle: int) -> bool:
        return bool(self._next(handle))

    def close(self, handle: int) -> None:
        self._close(handle)


@cache
def _platform_notifications() -> _ChangeNotifications | None:
    return _WindowsChangeNotifications() if sys.platform == "win32" else None


@dataclass(frozen=True, slots=True)
class _Held[T]:
    generation: int
    read_at: float
    value: T


class CustodyChangeWitness[T]:
    """Answer from the last read until a watched directory changes, the read ages out, or the owner invalidates it.

    Each notification is re-armed before the read it triggers, so a change made
    during that read signals again and the next check reads once more. A read
    that raises is never held. Failing to watch any directory, or to re-arm a
    notification, holds nothing: every check then reads, as before this witness.
    """

    def __init__(
        self,
        directories: Sequence[WatchedDirectory],
        *,
        maximum_age: float = MAXIMUM_OBSERVATION_AGE_SECONDS,
        monotonic: Callable[[], float] = time.monotonic,
        notifications: _ChangeNotifications | None = None,
    ) -> None:
        """Watch nothing until the first observation; the directories may not exist yet."""
        self._directories = tuple(directories)
        self._maximum_age = maximum_age
        self._monotonic = monotonic
        self._notifications = notifications if notifications is not None else _platform_notifications()
        self._lock = Lock()
        self._handles: tuple[int, ...] = ()
        # Shared with the finalizer, which releases whatever is open when the witness is collected unclosed.
        self._open: list[int] = []
        weakref.finalize(self, _close_handles, self._notifications, self._open)
        self._generation = 0
        self._held: _Held[T] | None = None
        self._closed = False

    def observe(self, read: Callable[[], T]) -> T:
        """Return the held observation while nothing changed, else read, hold and return a fresh one."""
        with self._lock:
            held = self._current()
            if held is not None:
                return held.value
            generation = self._generation
            watched = bool(self._handles)
        read_at = self._monotonic()
        value = read()
        if watched:
            with self._lock:
                # An invalidation or a change seen by another check during this read is newer than it.
                if generation == self._generation and not self._closed:
                    self._held = _Held(generation, read_at, value)
        return value

    def invalidate(self) -> None:
        """Forget the held observation; the owner published a change through its own write."""
        with self._lock:
            self._generation += 1
            self._held = None

    def close(self) -> None:
        """Release the notification handles; later checks read every time."""
        with self._lock:
            self._closed = True
            self._held = None
            self._release()

    def _current(self) -> _Held[T] | None:
        if self._closed or self._notifications is None:
            return None
        if not self._handles:
            self._watch()
            return None
        changed = False
        for handle in self._handles:
            signaled = self._notifications.signaled(handle)
            if signaled is None or (signaled and not self._notifications.rearm(handle)):
                self._release()
                return None
            changed = changed or signaled
        held = self._held
        if changed or held is None or self._monotonic() - held.read_at >= self._maximum_age:
            self._generation += 1
            self._held = None
            return None
        return held

    def _watch(self) -> None:
        """Open every notification; a directory the first read creates is watched from the next check."""
        notifications = self._notifications
        if notifications is None:
            return
        handles: list[int] = []
        for directory in self._directories:
            handle = notifications.open(directory)
            if handle is None:
                for opened in handles:
                    notifications.close(opened)
                return
            handles.append(handle)
        self._handles = tuple(handles)
        self._open[:] = handles
        self._generation += 1
        self._held = None

    def _release(self) -> None:
        self._handles = ()
        self._generation += 1
        _close_handles(self._notifications, self._open)


def _close_handles(notifications: _ChangeNotifications | None, handles: list[int]) -> None:
    opened, handles[:] = tuple(handles), []
    if notifications is not None:
        for handle in opened:
            notifications.close(handle)


__all__ = ["MAXIMUM_OBSERVATION_AGE_SECONDS", "CustodyChangeWitness", "WatchedDirectory"]
