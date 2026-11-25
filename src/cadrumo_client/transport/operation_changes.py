"""Wait for a session's operations to advance on the runtime's cue instead of a fixed interval."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from math import isfinite
from threading import Event, Lock
from types import TracebackType
from typing import Protocol, Self


class OperationCueSource(Protocol):
    """A connection that cues its subscribers when an operation it observes may have advanced."""

    def subscribe_operation_changes(self, receive: Callable[[], None]) -> Callable[[], None]:
        """Call ``receive`` on each cue, or when the connection is lost; returns the unsubscribe."""
        ...


class _OperationCueSubscription:
    """The client's operation cue, subscribed on first arm and held until closed."""

    def __init__(self, client: OperationCueSource) -> None:
        """Bind to the client whose operation cue the first arm subscribes to."""
        self._client = client
        self._unsubscribe: Callable[[], None] | None = None

    @property
    def armed(self) -> bool:
        """Whether the cue is subscribed, so a wait can end on it."""
        return self._unsubscribe is not None

    def close(self) -> None:
        """Stop receiving cues."""
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    def __enter__(self) -> Self:
        """Hold the subscription for a block."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release the subscription."""
        self.close()


class OperationChanges(_OperationCueSubscription):
    """Wake an observation loop when an operation its session observes may have advanced.

    Nothing is subscribed until :meth:`arm` first runs, so an operation already
    settled at its first observation costs no subscription. Arm before each
    later observation, then wait after it: a cue that arrives while that
    observation is in flight still ends the wait. A lost connection wakes the
    wait too, and the next observation is refused at once.
    """

    def __init__(self, client: OperationCueSource) -> None:
        """Bind to the client whose operation cue the first arm subscribes to."""
        super().__init__(client)
        self._changed = Event()

    def arm(self) -> None:
        """Subscribe on first use, then forget earlier cues; call before the observation the next wait follows."""
        if self._unsubscribe is None:
            self._unsubscribe = self._client.subscribe_operation_changes(self._changed.set)
        self._changed.clear()

    def wait(self, timeout: float) -> None:
        """Block until a cue since the last arm, or until ``timeout`` seconds pass; an unbounded wait has none."""
        self._changed.wait(timeout if isfinite(timeout) else None)


class AsyncOperationChanges(_OperationCueSubscription):
    """:class:`OperationChanges` for an event loop: the connection's reader thread wakes the loop.

    The first :meth:`arm` subscribes and binds the running loop, so it must
    run on the loop that later awaits :meth:`wait`.
    """

    def __init__(self, client: OperationCueSource) -> None:
        """Bind to the client whose operation cue the first arm subscribes to."""
        super().__init__(client)
        self._changed: asyncio.Event | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._guard = Lock()
        self._pending = False
        self._dirty = False

    def arm(self) -> None:
        """Subscribe on first use, then forget earlier cues; call before the observation the next wait follows."""
        loop = asyncio.get_running_loop()
        if self._loop is not None and self._loop is not loop:
            raise RuntimeError("operation changes belong to their original event loop")
        if self._changed is None:
            self._loop = loop
            self._changed = asyncio.Event()
        with self._guard:
            self._dirty = False
            self._changed.clear()
        if self._unsubscribe is None:
            self._unsubscribe = self._client.subscribe_operation_changes(self._wake)

    def _wake(self) -> None:
        with self._guard:
            loop = self._loop
            if loop is None:
                return
            self._dirty = True
            if self._pending:
                return
            self._pending = True
            try:
                loop.call_soon_threadsafe(self._deliver)
            except RuntimeError:
                # A closed loop has nobody left waiting.
                self._pending = False

    def _deliver(self) -> None:
        with self._guard:
            self._pending = False
            if self._dirty and self._changed is not None:
                self._dirty = False
                self._changed.set()

    async def wait(self, timeout: float) -> None:
        """Wait until a cue since the last arm, or until ``timeout`` seconds pass; an unbounded wait has none."""
        changed = self._changed
        if changed is None:
            raise RuntimeError("arm before waiting")
        with suppress(TimeoutError):
            await asyncio.wait_for(changed.wait(), timeout if isfinite(timeout) else None)
