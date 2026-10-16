"""Sign-in observation for the desktop shell: one line per change, read only when something moved.

The shell holds no runtime connection; this child does, unauthenticated and
for status only. It reads the selected profile's sign-in status once, then
again only when the runtime pushes a sign-in cue, the connection is lost,
the active-profile pointer changes, or the status's own deadline passes.
Each line is the whole current observation, written only when it differs
from the last one, or when the parent asks with a newline, as it does after a
sign-in or sign-out of its own. The child ends when its parent closes
standard input.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import sys
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from threading import Event, Lock, Thread
from uuid import UUID

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.sign_in import SignInPresence, SignInStatus
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.installed_client import open_installed_client

_RECONNECT_SECONDS = (1.0, 2.0, 5.0, 10.0, 30.0)
"""Waits between attempts while the runtime is unavailable; reconnection, not observation."""
_DEADLINE_MARGIN_SECONDS = 0.5
"""A coarse timer then wakes after a deadline, never just before it."""


class _Wakes:
    """Why the watch woke; each flag is set by its own source and taken once."""

    def __init__(self) -> None:
        self._guard = Lock()
        self._event = Event()
        self._cued = False
        self._pointer = False
        self._forced = False
        self.stopping = Event()

    def cue(self) -> None:
        with self._guard:
            self._cued = True
        self._event.set()

    def refresh(self) -> None:
        """The parent asks for a fresh line, written even if nothing changed."""
        with self._guard:
            self._cued = self._forced = True
        self._event.set()

    def take_forced(self) -> bool:
        with self._guard:
            forced, self._forced = self._forced, False
        return forced

    def pointer_moved(self) -> None:
        with self._guard:
            self._pointer = True
        self._event.set()

    def stop(self) -> None:
        self.stopping.set()
        self._event.set()

    def wait(self, timeout: float | None) -> tuple[bool, bool]:
        """Sleep until a wake or the timeout; return whether a cue and a pointer change arrived."""
        self._event.wait(timeout)
        with self._guard:
            self._event.clear()
            cued, pointer = self._cued, self._pointer
            self._cued = self._pointer = False
        return cued, pointer


def _emit(document: Mapping[str, object]) -> None:
    sys.stdout.write(json.dumps(document, separators=(",", ":")) + "\n")
    sys.stdout.flush()


class _PointerUnreadableError(Exception):
    """The active-profile pointer could not be read; its next change is the next reason to try."""


def _selection() -> tuple[UUID | None, str | None]:
    """The selected profile and its public label, read as ``config sign-in-status`` reads them."""
    from cadrumo.adapters.persistence.storage.errors import StorageValidationError
    from cadrumo.application.user_profile.profile_pointer import observe_active_profile_pointer
    from cadrumo.application.workflow.profile_bucket_scan import resolve_profile_bucket
    from cadrumo.core.config_state_root import FormerProductStateError
    from cadrumo.core.errors.hierarchy import CadrumoError

    try:
        bucket_id = observe_active_profile_pointer().bucket_id
    except (CadrumoError, OSError) as error:
        raise _PointerUnreadableError from error
    if bucket_id is None:
        return None, None
    try:
        bucket = resolve_profile_bucket(bucket_id)
    except (FormerProductStateError, StorageValidationError):
        bucket = None
    return UUID(bucket_id), None if bucket is None else bucket.label


def _observation(
    profile_id: UUID | None, label: str | None, status: SignInStatus | None, refusal: str | None
) -> dict[str, object]:
    presence = SignInPresence.UNKNOWN if status is None else status.presence
    return {
        "kind": "sign_in",
        "active_profile": label,
        "profile_id": None if profile_id is None else str(profile_id),
        "presence": presence.value,
        "refusal": refusal,
    }


def _refusal_code(error: BaseException) -> str:
    if isinstance(error, RefusalError):
        # A connection the runtime closed means the runtime is gone, as an absent endpoint does.
        reason = RefusalCode.UNAVAILABLE if error.reason is RefusalCode.CONNECTION_CLOSED else error.reason
        return reason.value
    if isinstance(error, FrontendRefusedError):
        return error.reason
    return RefusalCode.UNAVAILABLE.value


def _seconds_until_deadline(status: SignInStatus) -> float | None:
    deadlines = [deadline for deadline in (status.idle_deadline, status.absolute_deadline) if deadline is not None]
    if not deadlines:
        return None
    earliest: datetime = min(deadlines)
    return max(0.0, (earliest - now()).total_seconds()) + _DEADLINE_MARGIN_SECONDS


def _watch_pointer_directory(directory: Path, wakes: _Wakes) -> None:
    """Wake on each change of a file name or write time directly in the pointer's directory (Windows)."""
    if sys.platform != "win32":
        return
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    first = kernel.FindFirstChangeNotificationW
    first.argtypes, first.restype = (wintypes.LPCWSTR, wintypes.BOOL, wintypes.DWORD), wintypes.HANDLE
    following = kernel.FindNextChangeNotification
    following.argtypes, following.restype = (wintypes.HANDLE,), wintypes.BOOL
    wait = kernel.WaitForSingleObject
    wait.argtypes, wait.restype = (wintypes.HANDLE, wintypes.DWORD), wintypes.DWORD
    close = kernel.FindCloseChangeNotification
    close.argtypes, close.restype = (wintypes.HANDLE,), wintypes.BOOL
    # The pointer is replaced by rename, a name change; a write in place changes its write time.
    handle = first(str(directory), False, 0x00000001 | 0x00000010)
    if handle is None or handle == wintypes.HANDLE(-1).value:
        return
    try:
        while not wakes.stopping.is_set():
            if wait(handle, 0xFFFFFFFF) != 0:
                return
            wakes.pointer_moved()
            if not following(handle):
                return
    finally:
        close(handle)


def _watch_parent(stdin_fd: int, wakes: _Wakes) -> None:
    """Each newline from the parent asks for a fresh line; the end of its input ends the watch."""
    with contextlib.suppress(OSError):
        while byte := os.read(stdin_fd, 1):
            if byte == b"\n":
                wakes.refresh()
    wakes.stop()


type _Publish = Callable[[dict[str, object]], None]


def _observe(client: FrontendClient, profile_id: UUID, label: str | None, wakes: _Wakes, publish: _Publish) -> bool:
    """Follow one profile on one connection; return whether its connection was lost."""
    try:
        status = client.watch_sign_in(wakes.cue).status
    except (RefusalError, FrontendRefusedError, OSError) as error:
        publish(_observation(profile_id, label, None, _refusal_code(error)))
        return True
    publish(_observation(profile_id, label, status, None))
    while not wakes.stopping.is_set():
        cued, pointer = wakes.wait(_seconds_until_deadline(status))
        if wakes.stopping.is_set():
            return False
        if pointer:
            try:
                moved = _selection() != (profile_id, label)
            except _PointerUnreadableError:
                moved = True
            if moved:
                return False
        if pointer and not cued:
            continue
        try:
            status = client.sign_in_status().status
        except (RefusalError, FrontendRefusedError, OSError) as error:
            publish(_observation(profile_id, label, None, _refusal_code(error)))
            return True
        publish(_observation(profile_id, label, status, None))
    return False


def _watch(wakes: _Wakes) -> int:
    previous: list[dict[str, object]] = []

    def publish(observation: dict[str, object]) -> None:
        if wakes.take_forced() or previous != [observation]:
            previous[:] = [observation]
            _emit(observation)

    attempt = 0
    while not wakes.stopping.is_set():
        try:
            profile_id, label = _selection()
        except _PointerUnreadableError:
            publish(_observation(None, None, None, "active_profile_unreadable"))
            wakes.wait(None)
            continue
        if profile_id is None:
            publish(_observation(None, None, SignInStatus(presence=SignInPresence.ABSENT), None))
            wakes.wait(None)
            continue
        try:
            client = asyncio.run(open_installed_client(profile_id=profile_id, frontend=OperationFrontendProjection.CLI))
        except (RefusalError, FrontendRefusedError, OSError) as error:
            publish(_observation(profile_id, label, None, _refusal_code(error)))
            wakes.wait(_RECONNECT_SECONDS[min(attempt, len(_RECONNECT_SECONDS) - 1)])
            attempt += 1
            continue
        try:
            lost = _observe(client, profile_id, label, wakes, publish)
        finally:
            client.close()
        attempt = attempt + 1 if lost else 0
        if lost:
            wakes.wait(_RECONNECT_SECONDS[min(attempt - 1, len(_RECONNECT_SECONDS) - 1)])
    return 0


def main(arguments: list[str] | None = None) -> int:
    """Write the selected profile's sign-in status on every change until standard input closes."""
    parser = argparse.ArgumentParser(prog="cadrumo-runtime session watch", allow_abbrev=False)
    parser.parse_args(arguments)
    from cadrumo.adapters.persistence.storage.profile_persistence_composition import (
        composed_profile_persistence_ports,
    )
    from cadrumo.core.bucket_pointer import pointer_path
    from cadrumo.core.paths import effective_storage_root

    wakes = _Wakes()
    Thread(target=_watch_parent, args=(sys.stdin.fileno(), wakes), name="watch-parent", daemon=True).start()
    with composed_profile_persistence_ports():
        directory = pointer_path(effective_storage_root()).parent
        Thread(target=_watch_pointer_directory, args=(directory, wakes), name="watch-pointer", daemon=True).start()
        return _watch(wakes)
