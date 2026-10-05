"""Process-owned final shutdown bound beyond fallible threads and callbacks."""

from __future__ import annotations

import os
from collections.abc import Callable
from threading import Event, Thread
from types import TracebackType
from typing import NoReturn, Self, override

from ...application.runtime.contracts import RuntimeExitReason


def terminate_runtime(reason: RuntimeExitReason) -> NoReturn:
    """Exit with ``reason`` without releasing singleton ownership ahead of remaining execution.

    This belongs only to the installed runtime process. Its native containment
    handles close with the process; cleanup callbacks cannot extend the bound.
    Journals remain available for honest lease/effect reconciliation afterwards.
    """
    os._exit(int(reason))


class RuntimeStop(Event):
    """Stop latch that keeps the first reason this runtime was asked to end for."""

    def __init__(self) -> None:
        """Start unset, with no reason recorded."""
        super().__init__()
        self._first: dict[str, RuntimeExitReason] = {}

    def request(self, reason: RuntimeExitReason) -> None:
        """Record ``reason`` unless an earlier request named one, then set the latch."""
        # dict.setdefault is one atomic step under the GIL, so a signal handler
        # that interrupts another request cannot overwrite the first reason.
        self._first.setdefault("reason", reason)
        self.set()

    @property
    def reason(self) -> RuntimeExitReason | None:
        """Return the first requested reason, or ``None`` when only ``set`` was called."""
        return self._first.get("reason")


def request_runtime_stop(stop: Event, reason: RuntimeExitReason) -> None:
    """Set ``stop``, recording ``reason`` when it is the runtime's own exit latch."""
    if isinstance(stop, RuntimeStop):
        stop.request(reason)
    else:
        stop.set()


class RuntimeShutdownEvent(Event):
    """Publish terminal native launcher disposition before local shutdown."""

    def __init__(self, *, before_stop: Callable[[], None]) -> None:
        """Bind native stop publication before the local Event is set."""
        super().__init__()
        self._before_stop = before_stop

    @override
    def set(self) -> None:
        """Latch intentional stop, including when later drain cannot finish."""
        try:
            self._before_stop()
        except BaseException:
            # An unreadable stop disposition must never become a crash retry.
            terminate_runtime(RuntimeExitReason.SUPERVISOR_STOP)
        super().set()


class RuntimeShutdownWatchdog:
    """Watch the real stop event independently of the serving thread.

    A manager stop or signal can arrive while native credential access, worker
    establishment, or a callback is blocked. A thread timeout is not termination;
    the installed process must die before another runtime may own its root.
    """

    def __init__(self, stop: Event, *, timeout: float) -> None:
        """Bind one process lifetime and a strictly positive shutdown budget."""
        if not 0 < timeout < float("inf"):
            raise ValueError("runtime shutdown deadline must be finite and positive")
        self._stop, self._timeout = stop, timeout
        self._finished = Event()
        self._thread = Thread(target=self._watch, name="runtime-shutdown-bound", daemon=True)

    def _watch(self) -> None:
        while not self._stop.wait(0.05):
            if self._finished.is_set():
                return
        if not self._finished.wait(self._timeout):
            terminate_runtime(RuntimeExitReason.DRAIN_WATCHDOG)

    def __enter__(self) -> Self:
        """Arm the bound before serving any clients or opening profile custody."""
        self._thread.start()
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, _traceback: TracebackType | None
    ) -> None:
        """Disarm after serving has settled or terminated the installed process."""
        self._finished.set()
        self._thread.join(timeout=1)
