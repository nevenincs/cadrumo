"""Keep a profile worker's warm public heap out of the cyclic collector's full passes.

Once a worker has walked its pinned generation's grounding index it holds about
a million long-lived objects of public registry content. Every full collection
re-traverses all of them and frees nothing; a Modelo form read triggers one,
spending about half a second of its time there. Frozen, they are skipped, and
objects created afterwards are collected exactly as before.

A freeze also covers whatever else is alive at that moment, including session
state, so it lasts only as long as the session: when a session ends, the heap is
unfrozen and every object again becomes collectable on the normal schedule.
Reference counting frees frozen objects regardless; only cyclic garbage waits.
"""

from __future__ import annotations

import gc
from threading import Lock

__all__ = ["WarmHeapFreeze"]


class WarmHeapFreeze:
    """Freeze the process heap after a warm load and unfreeze it when the session ends.

    The cyclic collector's permanent generation is process wide, so one worker
    process owns one instance, passed by its entry point.
    """

    def __init__(self) -> None:
        """Start unfrozen."""
        self._lock = Lock()
        self._frozen = False

    @property
    def frozen(self) -> bool:
        """Whether this owner currently holds the heap frozen."""
        return self._frozen

    def freeze(self) -> None:
        """Collect the garbage present now, then freeze every surviving object; a second call does nothing."""
        with self._lock:
            if self._frozen:
                return
            gc.collect()
            gc.freeze()
            self._frozen = True

    def release(self) -> None:
        """Return every frozen object to the collector; a call while unfrozen does nothing."""
        with self._lock:
            if not self._frozen:
                return
            gc.unfreeze()
            self._frozen = False
