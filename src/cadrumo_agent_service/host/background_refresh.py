"""Run a slow read on its own thread, one at a time, so the requests that want it never wait for it.

A provider's sign-in state and the agent's sign-in capabilities are read by
running the agent, which can take tens of seconds on a cold start. A request
serves what was last read and asks for a refresh; a refresh asked for while one
runs is folded into at most one more run, made only if the read is still due
once the running one ends.
"""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock, Thread

from cadrumo.core.logging import get_logger

_LOGGER = get_logger(__name__)


class BackgroundRefresh:
    """One read's refresh: at most one run at a time, and at most one more queued behind it."""

    def __init__(self, work: Callable[[], None], *, due: Callable[[], bool], name: str) -> None:
        """Bind the work and the predicate that says whether it needs to run."""
        self._work = work
        self._due = due
        self._name = name
        self._lock = Lock()
        self._running = False
        self._again = False

    def request(self) -> None:
        """Start the work when it is due and none runs; while one runs, ask for one more run after it."""
        if not self._due():
            return
        with self._lock:
            if self._running:
                self._again = True
                return
            self._running = True
        try:
            Thread(target=self._run, name=f"agent-service-{self._name}", daemon=True).start()
        except BaseException:
            with self._lock:
                self._running = False
            raise

    def _run(self) -> None:
        while True:
            try:
                self._work()
            except Exception as error:
                # The next request asks again; only the error's kind is logged, never what it carried.
                _LOGGER.warning("agent service %s refresh failed: %s", self._name, type(error).__name__)
            if self._ends():
                return
            # A request made while the work ran asked for one more run; it is made only if still due.
            while not self._still_due():
                if self._ends():
                    return

    def _ends(self) -> bool:
        """Release the run unless a request asked for another; say whether it was released."""
        with self._lock:
            if self._again:
                self._again = False
                return False
            self._running = False
            return True

    def _still_due(self) -> bool:
        try:
            return self._due()
        except Exception:
            return False
