"""Answer an administration read within a bound, from work that may take longer.

A read such as the provider catalog or the provider status can take seconds:
the agent may still be building its catalog, and a provider's sign-in state is
read by running the provider's own program. The desktop waits a few seconds
for each answer, and an exchange left waiting also holds one of the service's
few administration slots. So the work runs on its own thread, once at a time,
and the request waits for it only up to its bound. A request that finds the
work unfinished at the bound is told the service is busy; the work goes on,
and the next request inside the freshness window is served its result at once.
Work that finishes within its request's bound is not kept: that request was
answered, and the next one reads afresh.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeoutError
from threading import Lock, Thread
from time import monotonic
from typing import Final, override

BUSY: Final = {"kind": "refused", "code": "busy"}
"""The answer to a request whose work did not finish within its bound."""


class Identity:
    """A key part that matches only the very object it holds, whether or not that object is hashable."""

    __slots__ = ("held",)

    def __init__(self, held: object) -> None:
        """Hold the object; it is compared by identity alone."""
        self.held = held

    @override
    def __eq__(self, other: object) -> bool:
        """Match only another holder of the same object."""
        return isinstance(other, Identity) and other.held is self.held

    @override
    def __hash__(self) -> int:
        """Hash by identity, consistently with equality."""
        return id(self.held)


class BoundedRead[T]:
    """One read's work, run at most once at a time and kept briefly for the requests that follow.

    A result is kept under the key the request named, and only a request naming
    the same key is served it: the key says what the result was computed for,
    such as the lease and the agent tree. A failure is never kept, and reaches
    the request that waited for it.
    """

    def __init__(self, compute: Callable[[], T], *, name: str, fresh_seconds: float) -> None:
        """Bind the work and how long its result stays fresh."""
        self._compute = compute
        self._name = name
        self._fresh_seconds = fresh_seconds
        self._lock = Lock()
        self._kept: tuple[Hashable, T, float] | None = None
        self._running: tuple[Hashable, Future[T]] | None = None
        self._outlived: set[Future[T]] = set()

    def answer(self, key: Hashable, *, within: float) -> T | dict[str, str]:
        """Return the work's result for ``key`` within ``within`` seconds, or :data:`BUSY`.

        Raises:
            Exception: Whatever the work raised, for the request that waited for it.
        """
        with self._lock:
            kept = self._kept
            if kept is not None and kept[0] == key and monotonic() - kept[2] < self._fresh_seconds:
                return kept[1]
            running = self._running
            if running is None or running[0] != key:
                future: Future[T] = Future()
                self._running = running = (key, future)
                Thread(target=self._run, args=(key, future), name=f"agent-service-{self._name}", daemon=True).start()
        try:
            return running[1].result(timeout=within)
        except FutureTimeoutError:
            with self._lock:
                if not running[1].done():
                    # Its result is kept for the request that comes back for it.
                    self._outlived.add(running[1])
                    return BUSY
            return running[1].result()

    def forget(self) -> None:
        """Drop the kept result: what it was computed from has changed.

        Work still running finishes for the requests waiting on it, but its
        result is not kept, and the next request starts the work afresh.
        """
        with self._lock:
            self._kept = None
            self._running = None
            self._outlived.clear()

    def _run(self, key: Hashable, future: Future[T]) -> None:
        try:
            value = self._compute()
        except BaseException as error:
            with self._lock:
                self._outlived.discard(future)
                if self._running is not None and self._running[1] is future:
                    self._running = None
                future.set_exception(error)
            return
        with self._lock:
            outlived = future in self._outlived
            self._outlived.discard(future)
            if self._running is not None and self._running[1] is future:
                self._running = None
                if outlived:
                    self._kept = (key, value, monotonic())
            future.set_result(value)
