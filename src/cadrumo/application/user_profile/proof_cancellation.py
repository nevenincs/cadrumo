"""Owned cancellation and synchronized wakeups for one profile proof attempt."""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from threading import Event, RLock

from ...core.errors.hierarchy import CadrumoError


class ProfileProofCancelledError(CadrumoError):
    """The exact proof owner withdrew its attempt; no credential failure occurred."""


class _Wakeup:
    def __init__(self, callback: Callable[[], None]) -> None:
        self._lock = RLock()
        self._callback: Callable[[], None] | None = callback

    def signal(self) -> None:
        with self._lock:
            if self._callback is not None:
                self._callback()

    def close(self) -> None:
        # An unsubscribed OS handle/pipe may be closed only after an already
        # selected callback has finished using it.
        with self._lock:
            self._callback = None


class ProfileProofCancellation:
    """One owner-controlled stop signal with lifetime-bound synchronous wakeups."""

    def __init__(self) -> None:
        """Create an unrequested stop signal with no retained wakeup resources."""
        self._cancelled = Event()
        self._lock = RLock()
        self._wakeups: set[_Wakeup] = set()

    def raise_if_cancelled(self) -> None:
        """Refuse work before it can consume or publish another proof phase."""
        if self._cancelled.is_set():
            raise ProfileProofCancelledError("profile proof attempt cancelled")

    def cancel(self) -> None:
        """Set the exact attempt's stop signal and wake every registered owner."""
        with self._lock:
            if self._cancelled.is_set():
                return
            self._cancelled.set()
            wakeups, self._wakeups = tuple(self._wakeups), set()
        failures: list[BaseException] = []
        for wakeup in wakeups:
            try:
                wakeup.signal()
            except BaseException as error:
                failures.append(error)
        if failures:
            raise BaseExceptionGroup("profile proof cancellation wakeup failed", failures)

    @contextmanager
    def watch(self, callback: Callable[[], None]) -> Generator[None]:
        """Wake on cancellation, joining any callback before its resources close."""
        wakeup = _Wakeup(callback)
        with self._lock:
            cancelled = self._cancelled.is_set()
            if not cancelled:
                self._wakeups.add(wakeup)
        try:
            if cancelled:
                wakeup.signal()
            yield
        finally:
            with self._lock:
                self._wakeups.discard(wakeup)
            wakeup.close()


__all__ = ["ProfileProofCancellation", "ProfileProofCancelledError"]
