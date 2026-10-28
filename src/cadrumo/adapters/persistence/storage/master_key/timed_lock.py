"""A reentrant lock that reports an outermost entry which waited, or held it, past a threshold."""

from __future__ import annotations

import inspect
import logging
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from threading import RLock, get_ident
from types import TracebackType
from typing import Final

from .....core.diagnostic_log import diagnostic_event
from .....core.errors.hierarchy import InternalInvariantError
from .....core.logging import get_logger

_log = get_logger(__name__)

SLOW_LOCK_SECONDS: Final = 0.5
"""A wait or a hold at least this long is reported."""

CUSTODY_LOCK_SLOW_EVENT: Final = "profile_worker_custody_lock_slow"
"""The record a lock reports unless its owner names another."""

_CALLER_LABEL_FRAMES: Final = 3
_TRANSPARENT_MODULES: Final = frozenset({__name__, "contextlib"})


@dataclass(frozen=True, slots=True)
class _Entry:
    """The outermost entry of a held lock, replaced as one reference so a waiter reads a consistent pair."""

    owner: int
    call_name: str
    acquired: float
    waited: float
    blocker: tuple[str, float] | None


def _caller_label() -> str:
    """Name the code that entered the lock, then the callers behind it, outside this module and ``contextlib``.

    Only fixed code identities are named, never a value a request carried.
    """
    names: list[str] = []
    frame = inspect.currentframe()
    try:
        while frame is not None and len(names) < _CALLER_LABEL_FRAMES:
            module = frame.f_globals.get("__name__")
            if module not in _TRANSPARENT_MODULES:
                names.append(f"{module}:{frame.f_code.co_qualname}")
            frame = frame.f_back
    finally:
        # A frame held in its own local would keep itself alive until the cycle collector ran.
        del frame
    return " < ".join(names)


class TimedRLock:
    """An ``RLock`` whose entries name their caller and report a slow outermost wait or hold.

    Entry by the thread that already holds the lock is counted, not timed, so
    reentrancy and exclusion are those of ``RLock``. ``held`` names its entry
    by a fixed label. ``acquire`` and the ``with`` statement name it by the
    code that made the entry, so every existing caller of an ``RLock`` is
    attributed without changing. A report carries only that name, the seconds
    waited and held, and, when the wait was slow, the name of the entry that
    was holding the lock then.
    """

    def __init__(self, *, slow_seconds: float | None = None, event: str = CUSTODY_LOCK_SLOW_EVENT) -> None:
        """Start unlocked; ``slow_seconds`` is the wait or hold that is reported, ``SLOW_LOCK_SECONDS`` by default."""
        self._lock = RLock()
        self._slow_seconds = SLOW_LOCK_SECONDS if slow_seconds is None else slow_seconds
        self._event = event
        # Written only by the thread holding the lock; a waiter reads it to name its blocker.
        self._holder: _Entry | None = None
        self._depth = 0

    @contextmanager
    def held(self, call_name: str) -> Generator[None]:
        """Hold the lock for the block; ``call_name`` is a fixed label, never a value derived from a request."""
        self._enter(call_name)
        try:
            yield
        finally:
            self.release()

    def owned(self) -> bool:
        """Whether the calling thread holds the lock at any depth."""
        entry = self._holder
        return entry is not None and entry.owner == get_ident()

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        """Acquire as ``RLock.acquire`` does, naming the entry by its calling code."""
        return self._enter(None, blocking, timeout)

    def release(self) -> None:
        """Release one level; the thread's last level reports a slow wait or hold."""
        entry = self._holder
        if entry is None or entry.owner != get_ident():
            raise InternalInvariantError("cannot release un-acquired lock")
        if self._depth > 1:
            self._depth -= 1
            self._lock.release()
            return
        released = time.monotonic()
        self._holder, self._depth = None, 0
        self._lock.release()
        self._report(entry.call_name, waited=entry.waited, held_for=released - entry.acquired, blocker=entry.blocker)

    def __enter__(self) -> bool:
        """Acquire, blocking, for the ``with`` statement."""
        return self._enter(None)

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        """Release the level ``__enter__`` acquired."""
        self.release()

    def _enter(self, call_name: str | None, blocking: bool = True, timeout: float = -1) -> bool:
        requested = time.monotonic()
        blocker: tuple[str, float] | None = None
        if blocking and (timeout == -1 or timeout > self._slow_seconds):
            if not self._lock.acquire(timeout=self._slow_seconds):
                observed = self._holder
                if observed is not None:
                    blocker = (observed.call_name, time.monotonic() - observed.acquired)
                if not self._lock.acquire(timeout=-1 if timeout == -1 else timeout - self._slow_seconds):
                    return False
        elif not self._lock.acquire(blocking, timeout):
            return False
        if self._depth:
            self._depth += 1
            return True
        acquired = time.monotonic()
        name = _caller_label() if call_name is None else call_name
        self._holder, self._depth = _Entry(get_ident(), name, acquired, acquired - requested, blocker), 1
        return True

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
            self._event,
            fields=fields,
            level=logging.WARNING,
            primary_error=sys.exception(),
        )
