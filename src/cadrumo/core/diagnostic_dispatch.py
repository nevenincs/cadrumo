"""Bounded, best-effort work queues for diagnostic processing and output."""

from __future__ import annotations

import math
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from queue import Empty, Full, Queue
from threading import Condition, Event, Lock, Thread, current_thread


@dataclass(frozen=True, slots=True)
class DispatchStatus:
    """Non-private delivery counters; reading them never enters an output sink."""

    accepted: int
    completed: int
    dropped: int
    failed: int
    pending: int
    active_seconds: float
    retained_weight: int


class DiagnosticDispatch[T]:
    """Run diagnostic work on one daemon, with bounded admission and drain.

    Callbacks, rendering and I/O never execute under the admission lock. A
    stuck callback costs this queue's delivery, not the calling application.
    """

    def __init__(
        self,
        consume: Callable[[T], None],
        *,
        name: str,
        capacity: int = 1024,
        maximum_weight: int = 32 * 1024 * 1024,
        finish: Callable[[], None] | None = None,
    ) -> None:
        """Allocate an idle queue; the first admission starts its only daemon."""
        if capacity < 1 or maximum_weight < 1:
            raise ValueError("diagnostic queues require positive finite bounds")
        self._consume = consume
        self._name = name
        self._capacity = capacity
        self._maximum_weight = maximum_weight
        self._finish = finish
        self._pid = os.getpid()
        self._reset()

    def _reset(self) -> None:
        self._queue: Queue[tuple[T, int]] = Queue(maxsize=self._capacity)
        self._guard = Lock()
        self._finished = Condition(self._guard)
        self._available = Event()
        self._stopped = Event()
        self._thread: Thread | None = None
        self._closing = False
        self._accepted = self._completed = self._dropped = self._failed = 0
        self._active_since: float | None = None
        self._retained_weight = 0

    def _require_process(self) -> None:
        if self._pid != os.getpid():
            # A fork inherits neither a functioning daemon nor usable lock ownership.
            self._pid = os.getpid()
            self._reset()

    def submit(self, item: T, *, weight: int = 1) -> bool:
        """Admit without waiting for queue space, callback completion or I/O."""
        self._require_process()
        with self._guard:
            if self._closing or weight < 1 or self._retained_weight + weight > self._maximum_weight:
                self._dropped += 1
                return False
            try:
                self._queue.put_nowait((item, weight))
            except Full:
                self._dropped += 1
                return False
            self._accepted += 1
            self._retained_weight += weight
            if self._thread is None:
                self._thread = Thread(target=self._run, name=self._name, daemon=True)
                try:
                    self._thread.start()
                except Exception:
                    self._thread = None
                    self._queue.get_nowait()
                    self._retained_weight -= weight
                    self._dropped += 1
                    self._completed += 1
                    self._failed += 1
                    return False
            self._available.set()
        return True

    def status(self) -> DispatchStatus:
        """Return counters without borrowing callback or sink ownership."""
        self._require_process()
        with self._guard:
            return DispatchStatus(
                accepted=self._accepted,
                completed=self._completed,
                dropped=self._dropped,
                failed=self._failed,
                pending=self._accepted - self._completed,
                active_seconds=0.0 if self._active_since is None else time.monotonic() - self._active_since,
                retained_weight=self._retained_weight,
            )

    def discard(self) -> None:
        """Count a rejected diagnostic without retaining or rendering its contents."""
        self._require_process()
        with self._guard:
            self._dropped += 1

    def flush(self, *, timeout: float = 2.0) -> bool:
        """Await the work already admitted, within one explicit finite bound."""
        self._require_process()
        if current_thread() is self._thread:
            return False
        with self._finished:
            target = self._accepted
            bound = max(0.0, timeout) if math.isfinite(timeout) else 0.0
            return self._finished.wait_for(lambda: self._completed >= target, timeout=bound)

    def close(self, *, timeout: float = 2.0) -> bool:
        """Stop accepting, attempt the pending work, and bound the join."""
        self._require_process()
        deadline = time.monotonic() + (max(0.0, timeout) if math.isfinite(timeout) else 0.0)
        with self._guard:
            self._closing = True
            thread = self._thread
            self._available.set()
        if thread is None:
            return True
        if current_thread() is thread:
            return False
        if not self._stopped.wait(max(0.0, deadline - time.monotonic())):
            return False
        thread.join(timeout=max(0.0, deadline - time.monotonic()))
        return not thread.is_alive()

    def _run(self) -> None:
        try:
            while True:
                try:
                    item, weight = self._queue.get_nowait()
                except Empty:
                    with self._guard:
                        if self._closing:
                            return
                        self._available.clear()
                        # Check again while admission is excluded, avoiding a lost wake.
                        if not self._queue.empty():
                            continue
                    self._available.wait()
                    continue
                with self._guard:
                    self._active_since = time.monotonic()
                try:
                    self._consume(item)
                except BaseException:
                    # Never recursively log the failure, including a broken formatter.
                    with self._guard:
                        self._failed += 1
                finally:
                    with self._guard:
                        self._completed += 1
                        self._retained_weight -= weight
                        self._active_since = None
                        self._finished.notify_all()
        finally:
            if self._finish is not None:
                try:
                    self._finish()
                except BaseException:
                    with self._guard:
                        self._failed += 1
            self._stopped.set()
