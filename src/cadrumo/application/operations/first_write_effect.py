"""Announce an operation's possible effect only once its first write is about to begin.

An operation whose executor refuses or fails before writing anything settles
with no effect; one that has begun writing may have changed records, so its
effect is journaled as unknown before that first write rather than eagerly at
the start of execution.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from ...core.errors.hierarchy import InternalInvariantError
from ...core.operations import OperationEffect

if TYPE_CHECKING:
    from .owner import OperationExecutorContext


class FirstWriteEffectAnnouncement:
    """Journal a possible effect from the worker thread before an operation's first actual write.

    An operation whose ports admit every commit through :meth:`write` settles a
    refusal or failure raised before any write with no effect, and journals that
    records may have changed only once a write is about to begin.
    """

    def __init__(self, context: OperationExecutorContext, loop: asyncio.AbstractEventLoop) -> None:
        """Bind the running operation's events and the event loop that owns them."""
        self._context = context
        self._loop = loop
        self._lock = threading.Lock()
        self._began = False

    @property
    def began(self) -> bool:
        """Report whether any persistence commit was admitted."""
        with self._lock:
            return self._began

    def write(self, write: Callable[[], None]) -> None:
        """Announce the uncertain effect once, then run ``write``."""
        with self._lock:
            if not self._began:
                if _runs_on(self._loop):
                    raise InternalInvariantError("an operation write must run off the operation event loop")
                asyncio.run_coroutine_threadsafe(
                    self._context.events.effect(OperationEffect.UNKNOWN), self._loop
                ).result()
                self._began = True
        write()


def _runs_on(loop: asyncio.AbstractEventLoop) -> bool:
    """Report whether the calling thread is running ``loop``, which a blocking wait would deadlock."""
    try:
        return asyncio.get_running_loop() is loop
    except RuntimeError:
        return False


__all__ = ["FirstWriteEffectAnnouncement"]
