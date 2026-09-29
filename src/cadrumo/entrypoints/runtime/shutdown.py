"""Process-owned final shutdown bound beyond fallible threads and callbacks."""

from __future__ import annotations

import os
from threading import Event, Thread
from types import TracebackType
from typing import NoReturn, Self


def terminate_runtime() -> NoReturn:
    """Exit without releasing singleton ownership ahead of remaining execution.

    This belongs only to the installed runtime process. Its native containment
    handles close with the process; cleanup callbacks cannot extend the bound.
    Journals remain available for honest lease/effect reconciliation afterwards.
    """
    os._exit(2)


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
            terminate_runtime()

    def __enter__(self) -> Self:
        """Arm the bound before serving any clients or opening profile custody."""
        self._thread.start()
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        """Disarm after serving has settled or terminated the installed process."""
        self._finished.set()
        self._thread.join(timeout=1)
