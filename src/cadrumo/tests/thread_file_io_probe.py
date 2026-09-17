"""Record the file I/O one thread performs, for gates that keep work off an event loop.

Python raises an audit event for every file open and directory listing. One
process-wide audit hook forwards those events to whichever recordings are
active for the thread that raised them, so a gate can prove that a call made on
an event-loop thread touched no file while the same call's worker threads did.

Opening a module's code during a first import also raises ``open``; those paths
are ignored, because a lazy import is not the storage access a gate is about.
"""

from __future__ import annotations

import sys
import threading
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import PurePath
from typing import Final

_FILE_EVENTS: Final[frozenset[str]] = frozenset(
    {"open", "os.listdir", "os.scandir", "os.remove", "os.rename", "os.replace", "os.mkdir"}
)
_CODE_SUFFIXES: Final[frozenset[str]] = frozenset({".py", ".pyc", ".pyd", ".so", ".dll"})

_recordings: dict[int, list[list[str]]] = {}
_recordings_lock = threading.Lock()
_hook_installed = False


def _audit(event: str, args: tuple[object, ...]) -> None:
    if event not in _FILE_EVENTS:
        return
    active = _recordings.get(threading.get_ident())
    if not active:
        return
    target = args[0] if args else None
    if isinstance(target, int) or target is None:
        return
    path = str(target)
    if PurePath(path).suffix.lower() in _CODE_SUFFIXES:
        return
    for recording in active:
        recording.append(f"{event}:{path}")


def _install_hook() -> None:
    global _hook_installed
    with _recordings_lock:
        if _hook_installed:
            return
        sys.addaudithook(_audit)
        _hook_installed = True


@contextmanager
def recording_file_io(thread_ident: int) -> Generator[list[str]]:
    """Yield the list of file accesses ``thread_ident`` performs inside the block."""
    _install_hook()
    recording: list[str] = []
    with _recordings_lock:
        _recordings.setdefault(thread_ident, []).append(recording)
    try:
        yield recording
    finally:
        with _recordings_lock:
            active = _recordings.get(thread_ident, [])
            active.remove(recording)
            if not active:
                _recordings.pop(thread_ident, None)


__all__ = ["recording_file_io"]
