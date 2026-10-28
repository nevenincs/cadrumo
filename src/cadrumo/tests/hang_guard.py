"""Waiting for diagnostics without a speed expectation of the machine that runs them.

A wait in a test is for something that has to happen: a delivery, a drain, a
worker reaching the point where it is held. How long that takes depends on what
else the machine is doing, so no test asserts it. The bound here only turns a
step that can never complete into a failure.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from threading import Event, Thread

HANG_GUARD_SECONDS = 60.0
"""What only a hung step reaches; it is never a duration a healthy step is expected to approach."""

PROCESS_HANG_GUARD_SECONDS = HANG_GUARD_SECONDS * 3
"""What only a hung child process reaches: past the guarded waits inside it, so those fail first and say why."""


def finishes[T](step: Callable[[], T], *, what: str, within: float = HANG_GUARD_SECONDS) -> T:
    """Run ``step`` on a thread of its own and return its result, failing with ``what`` if it never ends.

    A step that must finish while a resource stays held, such as producers
    logging behind a blocked sink, cannot be timed on a loaded machine. Running
    it apart lets a defect that makes it wait on the held resource fail the test
    instead of hanging it. The thread is a daemon, so a step that never ends
    does not keep the process alive.
    """
    outcome: list[T] = []
    failure: list[BaseException] = []
    done = Event()

    def run() -> None:
        try:
            outcome.append(step())
        except BaseException as error:
            failure.append(error)
        finally:
            done.set()

    Thread(target=run, name="step-under-hold", daemon=True).start()
    if not done.wait(within):
        raise AssertionError(f"{what} did not finish within the {within:g} s hang guard")
    if failure:
        raise failure[0]
    return outcome[0]


def eventually(
    condition: Callable[[], bool], *, what: str, within: float = HANG_GUARD_SECONDS, interval: float = 0.01
) -> None:
    """Poll ``condition`` until it holds, failing with ``what`` only if it never does within the hang guard.

    For something that has to happen whose time is the machine's to decide, such
    as a line from a drain thread reaching the log file. Success is the
    condition holding, never the time it took.
    """
    deadline = time.monotonic() + within
    while not condition():
        if time.monotonic() >= deadline:
            raise AssertionError(f"{what} did not happen within the {within:g} s hang guard")
        time.sleep(interval)
