"""Leave every thread's stack on disk when a profile worker's event loop stops turning.

A worker that stops answering its channels is ended by the runtime, and the
log records it had queued die with it, so nothing says what it was doing.
``faulthandler`` writes stacks from its own native thread, which needs neither
the event loop nor the interpreter lock; Windows has no signal to trigger it
from outside. The loop therefore re-arms a one-shot ``faulthandler`` timer on
every tick. A loop that stops ticking for the stall bound lets the timer fire.

The dump is frames only: thread ids, file paths, function names and line
numbers, never a local or an argument. It goes to a file named for the worker's
process id in the diagnostic log directory, created owner-only (``0600`` where
the platform has modes; on Windows the log directory's own access list applies,
as it does to the log file). A worker that never stalls leaves no file. The
file stops being armed once it holds ``MAX_DUMP_BYTES``, and a new watchdog
keeps at most ``RETAINED_DUMP_FILES`` dump files in the directory.

``faulthandler`` has one such timer per process, so this is the only user of it
in a worker.
"""

from __future__ import annotations

import asyncio
import faulthandler
import logging
import os
import sys
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from io import FileIO
from pathlib import Path
from typing import Final

from cadrumo.core.diagnostic_log import diagnostic_error_fields, diagnostic_event
from cadrumo.core.logging import default_log_file_path, get_logger

_LOGGER = get_logger(__name__)

STALL_SECONDS: Final = 10.0
"""How long the loop may go without a tick before stacks are written; well inside the runtime's control budget."""
TICK_SECONDS: Final = 1.0
"""How often a healthy loop re-arms the timer."""
MAX_DUMP_BYTES: Final = 256 * 1024
"""Size at which the file takes no further dump; one dump of a worker is a few kilobytes."""
RETAINED_DUMP_FILES: Final = 8
"""Dump files, this worker's included, kept in the log directory."""
DUMP_NAME_PREFIX: Final = "profile-worker-stall-"
DUMP_NAME_SUFFIX: Final = ".txt"


class _StallWatchdog:
    """One worker's armed timer, its file and the loop callback that keeps it from firing."""

    def __init__(
        self,
        stream: FileIO,
        path: Path,
        loop: asyncio.AbstractEventLoop,
        *,
        stall_seconds: float,
        tick_seconds: float,
        max_bytes: int,
    ) -> None:
        self._stream = stream
        self._path = path
        self._loop = loop
        self._stall_seconds = stall_seconds
        self._tick_seconds = tick_seconds
        self._max_bytes = max_bytes
        self._size = 0
        self._ticked = time.monotonic()
        self._next: asyncio.TimerHandle | None = None

    @property
    def dump_file(self) -> str:
        return self._path.name

    def start(self) -> None:
        self._arm()
        self._next = self._loop.call_later(self._tick_seconds, self._tick)

    def stop(self) -> None:
        """Disarm, report a dump the loop was too late to see, and drop a file nothing was written to."""
        if self._next is not None:
            self._next.cancel()
            self._next = None
        faulthandler.cancel_dump_traceback_later()
        with suppress(OSError):
            self._report_new_dump()
        size = self._size
        with suppress(OSError):
            self._stream.close()
        if size == 0:
            with suppress(OSError):
                self._path.unlink()

    def _arm(self) -> None:
        faulthandler.dump_traceback_later(self._stall_seconds, repeat=False, file=self._stream)

    def _tick(self) -> None:
        self._next = None
        try:
            self._report_new_dump()
            if self._size < self._max_bytes:
                self._arm()
                self._next = self._loop.call_later(self._tick_seconds, self._tick)
        except (OSError, RuntimeError, ValueError) as error:
            self._abandon(error)
        self._ticked = time.monotonic()

    def _report_new_dump(self) -> None:
        """Log, once the loop turns again, that the timer wrote stacks while it was stalled."""
        size = os.fstat(self._stream.fileno()).st_size
        if size <= self._size:
            return
        self._size = size
        diagnostic_event(
            _LOGGER,
            "profile_worker_event_loop_stall_dumped",
            fields={
                "dump_file": self._path.name,
                "elapsed_seconds": round(max(0.0, time.monotonic() - self._ticked), 3),
                "timeout_seconds": self._stall_seconds,
                "outcome": "capped" if size >= self._max_bytes else "dumped",
            },
            level=logging.WARNING,
        )

    def _abandon(self, error: Exception) -> None:
        faulthandler.cancel_dump_traceback_later()
        diagnostic_event(
            _LOGGER,
            "profile_worker_stall_watchdog_unavailable",
            fields={**diagnostic_error_fields(error), "dump_file": self._path.name, "outcome": "abandoned"},
            level=logging.WARNING,
            primary_error=error,
        )


def _open_dump(path: Path) -> FileIO:
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_APPEND
    flags |= os.O_BINARY if sys.platform == "win32" else os.O_NOFOLLOW | os.O_CLOEXEC
    return FileIO(os.open(path, flags, 0o600), "a")


def _prune(directory: Path, keep: Path) -> None:
    """Remove the oldest dump files so that with ``keep`` at most ``RETAINED_DUMP_FILES`` remain."""
    found: list[tuple[float, Path]] = []
    with suppress(OSError), os.scandir(directory) as entries:
        for entry in entries:
            if entry.name.startswith(DUMP_NAME_PREFIX) and entry.name.endswith(DUMP_NAME_SUFFIX):
                path = Path(entry.path)
                if path != keep:
                    with suppress(OSError):
                        found.append((entry.stat().st_mtime, path))
    found.sort(reverse=True)
    # A file another worker still holds open cannot be removed on Windows; the refusal is not an error here.
    for _, path in found[RETAINED_DUMP_FILES - 1 :]:
        with suppress(OSError):
            path.unlink()


def _arm(
    loop: asyncio.AbstractEventLoop,
    directory: Path | None,
    *,
    stall_seconds: float,
    tick_seconds: float,
    max_bytes: int,
) -> _StallWatchdog | None:
    """Arm the timer for this process, or log why not; a diagnostic never keeps a worker from serving."""
    watchdog: _StallWatchdog | None = None
    try:
        target = default_log_file_path().parent if directory is None else directory
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"{DUMP_NAME_PREFIX}{os.getpid()}{DUMP_NAME_SUFFIX}"
        _prune(target, path)
        watchdog = _StallWatchdog(
            _open_dump(path), path, loop, stall_seconds=stall_seconds, tick_seconds=tick_seconds, max_bytes=max_bytes
        )
        # Logged before the timer starts: the first record may configure logging, and that is not a stall.
        diagnostic_event(
            _LOGGER,
            "profile_worker_stall_watchdog_armed",
            fields={"dump_file": watchdog.dump_file, "timeout_seconds": stall_seconds, "outcome": "armed"},
            level=logging.INFO,
        )
        watchdog.start()
    except Exception as error:
        if watchdog is not None:
            watchdog.stop()
        diagnostic_event(
            _LOGGER,
            "profile_worker_stall_watchdog_unavailable",
            fields={**diagnostic_error_fields(error), "outcome": "unavailable"},
            level=logging.WARNING,
            primary_error=error,
        )
        return None
    return watchdog


@asynccontextmanager
async def watch_event_loop(
    *,
    directory: Path | None = None,
    stall_seconds: float = STALL_SECONDS,
    tick_seconds: float = TICK_SECONDS,
    max_bytes: int = MAX_DUMP_BYTES,
) -> AsyncGenerator[None]:
    """Write all thread stacks to this process's dump file if the running loop stalls for ``stall_seconds``.

    ``directory`` defaults to the diagnostic log directory. Leaving the block
    disarms the timer, so nothing outlives the loop it watches.
    """
    watchdog = _arm(
        asyncio.get_running_loop(),
        directory,
        stall_seconds=stall_seconds,
        tick_seconds=tick_seconds,
        max_bytes=max_bytes,
    )
    try:
        yield
    finally:
        if watchdog is not None:
            watchdog.stop()
