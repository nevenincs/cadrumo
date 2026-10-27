"""A reentrant lock that reports an outermost entry which waited, or held it, past a threshold."""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from threading import RLock
from typing import Final

from .....core.diagnostic_log import diagnostic_event
from .....core.logging import get_logger

_log = get_logger(__name__)

SLOW_LOCK_SECONDS: Final = 0.5
"""A wait or a hold at least this long is reported."""


class TimedRLock:
    """An ``RLock`` whose entries name their caller and report a slow outermost wait or hold.

    Entry by the thread that already holds the lock is counted, not timed, so
    reentrancy and exclusion are those of ``RLock``. A report carries only the
    caller's fixed label, the seconds waited and held, and, when the wait was
    slow, the label of the entry that was holding the lock then.
    """

    def __init__(self, *, slow_seconds: float | None = None) -> None:
        """Start unlocked; ``slow_seconds`` is the wait or hold that is reported, ``SLOW_LOCK_SECONDS`` by default."""
        self._lock = RLock()
        self._slow_seconds = SLOW_LOCK_SECONDS if slow_seconds is None else slow_seconds
        # Written only by the thread holding the lock; a waiter reads the pair to name its blocker.
        self._holder: tuple[str, float] | None = None
        self._depth = 0

    @contextmanager
    def held(self, call_name: str) -> Generator[None]:
        """Hold the lock for the block; ``call_name`` is a fixed label, never a value derived from a request."""
        requested = blocker_seen = time.monotonic()
        blocker: tuple[str, float] | None = None
        if not self._lock.acquire(timeout=self._slow_seconds):
            blocker = self._holder
            blocker_seen = time.monotonic()
            self._lock.acquire()
        acquired = time.monotonic()
        outermost = self._depth == 0
        self._depth += 1
        if outermost:
            self._holder = (call_name, acquired)
        try:
            yield
        finally:
            self._depth -= 1
            released = time.monotonic()
            if outermost:
                self._holder = None
            self._lock.release()
            if outermost:
                self._report(
                    call_name,
                    waited=acquired - requested,
                    held_for=released - acquired,
                    blocker=None if blocker is None else (blocker[0], blocker_seen - blocker[1]),
                )

    def _report(self, call_name: str, *, waited: float, held_for: float, blocker: tuple[str, float] | None) -> None:
        if waited < self._slow_seconds and held_for < self._slow_seconds:
            return
        fields: dict[str, str | float] = {
            "call_name": call_name,
            "wait_seconds": round(waited, 3),
            "hold_seconds": round(held_for, 3),
        }
        if blocker is not None:
            fields["held_call_name"], fields["held_elapsed_seconds"] = blocker[0], round(max(0.0, blocker[1]), 3)
        diagnostic_event(
            _log,
            "profile_worker_custody_lock_slow",
            fields=fields,
            level=logging.WARNING,
            primary_error=sys.exception(),
        )
