"""Wait for test child results without an elapsed completion ceiling.

Callers own process start, final join/exit assertions, and failure cleanup. A
short public Queue polling interval observes terminal owner failure; it never
limits how long a live owner may take to complete its correctness work.
"""

from __future__ import annotations

from collections.abc import Sequence
from multiprocessing.process import BaseProcess
from multiprocessing.queues import Queue
from queue import Empty

_OWNER_POLL_SECONDS = 0.1


def receive_process_result[T](results: Queue[T], *, owners: Sequence[BaseProcess]) -> T:
    """Receive a result, or fail when its actual owners can no longer produce it.

    Nonzero exit also fails while a sibling remains alive, so a crashed barrier
    participant cannot strand the caller. Always use the caller's finally to
    kill/reap any remaining children when this function raises.
    """
    if not owners:
        raise ValueError("a result queue requires at least one process owner")
    while True:
        try:
            return results.get(timeout=_OWNER_POLL_SECONDS)
        except Empty:
            exitcodes = tuple(owner.exitcode for owner in owners)
            if any(code is not None and code != 0 for code in exitcodes):
                raise AssertionError(f"child owner failed before a result; exitcodes={exitcodes}") from None
            if all(code is not None for code in exitcodes):
                # Owner exit and its feeder flush may have happened after the
                # timed poll. Drain that final message before declaring absence.
                try:
                    return results.get_nowait()
                except Empty:
                    raise AssertionError(f"child owners finished without a result; exitcodes={exitcodes}") from None
