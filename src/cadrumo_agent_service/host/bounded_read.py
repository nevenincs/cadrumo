"""Answer an administration read within a bound, from work that may take longer.

A read such as the provider catalog or the provider status can take seconds:
the agent may still be building its catalog, and a provider's sign-in state is
read by running the provider's own program. The desktop waits a few seconds
for each answer, and an exchange left waiting also holds one of the service's
few administration slots. So the work runs on its own thread, once at a time,
and the request waits for it only up to its bound. A request that finds the
work unfinished at the bound is told the service is busy; the work goes on,
and the next request inside the freshness window is served its outcome at once,
whether a result or a failure. Work that finishes within its request's bound is
not kept: that request was answered, and the next one reads afresh.

Work whose result was withdrawn, because what it read from changed or because
it reads for another key, is not an answer to the request, but it keeps the
work's slot until it ends. The request waits for it within the same bound and
then reads afresh: the service tells a request busy only when its bound runs
out, never because a change landed while earlier work was running.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from concurrent.futures import Future, wait
from enum import Enum
from threading import Lock, Thread
from time import monotonic
from typing import Final, override

BUSY: Final = {"kind": "refused", "code": "busy"}
"""The answer to a request whose work did not finish within its bound."""


class _Settled(Enum):
    """How the work a request waited for stood when the wait ended."""

    ANSWERED = "answered"
    """It ended in the request's generation, and its outcome answers the request."""
    UNFINISHED = "unfinished"
    """It was still running when the request's bound ran out."""
    WITHDRAWN = "withdrawn"
    """It ended, but its result was withdrawn while it ran."""


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
    such as the lease and the agent tree. A failure is kept the same way: the
    request that waited for it is answered with it, and so is the request that
    comes back for work that outlived its own request. Telling that request the
    service is busy instead would have it retry a read that already failed.
    """

    def __init__(self, compute: Callable[[], T], *, name: str, fresh_seconds: float) -> None:
        """Bind the work and how long its result stays fresh."""
        self._compute = compute
        self._name = name
        self._fresh_seconds = fresh_seconds
        self._lock = Lock()
        self._kept: tuple[Hashable, Future[T], float] | None = None
        self._running: tuple[Hashable, int, Future[T]] | None = None
        self._generation = 0
        self._outlived: set[Future[T]] = set()

    def answer(self, key: Hashable, *, within: float) -> T | dict[str, str]:
        """Return the work's result for ``key`` within ``within`` seconds, or :data:`BUSY`.

        Raises:
            Exception: Whatever the work raised, for the request that waited for
                it or, while the failure is kept, for a request that came back for it.
        """
        deadline = monotonic() + within
        while True:
            with self._lock:
                kept = self._kept
                if kept is not None and kept[0] == key and monotonic() - kept[2] < self._fresh_seconds:
                    # A kept outcome is settled, so reading it does not wait.
                    return kept[1].result()
                running = self._running
                withdrawn = running is not None and (running[0] != key or running[1] != self._generation)
                if running is None:
                    future: Future[T] = Future()
                    self._running = running = (key, self._generation, future)
                    try:
                        Thread(target=self._run, args=running, name=f"agent-service-{self._name}", daemon=True).start()
                    except BaseException:
                        self._running = None
                        raise
            if withdrawn:
                # Invalidation withdraws the result, not ownership of the work:
                # another provider probe must not start until this one ends.
                wait((running[2],), timeout=max(0.0, deadline - monotonic()))
                if not running[2].done():
                    return BUSY
                continue
            settled = self._await_running(running, deadline=deadline)
            if settled is _Settled.ANSWERED:
                return running[2].result()
            if settled is _Settled.UNFINISHED:
                return BUSY

    def _await_running(self, running: tuple[Hashable, int, Future[T]], *, deadline: float) -> _Settled:
        """Wait for this generation's work until ``deadline`` without releasing unfinished work ownership."""
        future = running[2]
        wait((future,), timeout=max(0.0, deadline - monotonic()))
        with self._lock:
            if not future.done():
                # Its outcome is kept for the request that comes back for it.
                if running[1] == self._generation:
                    self._outlived.add(future)
                return _Settled.UNFINISHED
            return _Settled.ANSWERED if running[1] == self._generation else _Settled.WITHDRAWN

    def forget(self) -> None:
        """Drop the kept result: what it was computed from has changed.

        Work still running retains its slot until it ends. No caller is given
        its result from the invalidated context: a caller waiting for it, and
        one that arrives meanwhile, waits for it to end within its own bound
        and then reads afresh.
        """
        with self._lock:
            self._kept = None
            self._generation += 1
            self._outlived.clear()

    def _run(self, key: Hashable, generation: int, future: Future[T]) -> None:
        try:
            value = self._compute()
        except BaseException as error:
            with self._lock:
                future.set_exception(error)
                # An interruption of the process is not an answer to a read.
                self._settle(key, generation, future, keep=isinstance(error, Exception))
            return
        with self._lock:
            future.set_result(value)
            self._settle(key, generation, future, keep=True)

    def _settle(self, key: Hashable, generation: int, future: Future[T], *, keep: bool) -> None:
        """Release the work's slot, and keep its outcome if a request outlived it.

        The caller holds the lock and has already settled ``future``. An outcome
        is kept only for the generation it was computed in, so a :meth:`forget`
        while the work ran withholds it.
        """
        outlived = future in self._outlived
        self._outlived.discard(future)
        if self._running is not None and self._running[2] is future:
            self._running = None
            if keep and outlived and generation == self._generation:
                self._kept = (key, future, monotonic())
