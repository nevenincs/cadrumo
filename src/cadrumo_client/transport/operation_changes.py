"""Wait for a session's operations to advance on the runtime's cue instead of a fixed interval."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from math import isfinite
from threading import Event
from types import TracebackType
from typing import Protocol, Self


class OperationCueSource(Protocol):
    """A connection that cues its subscribers when an operation it observes may have advanced."""

    def subscribe_operation_changes(self, receive: Callable[[], None]) -> Callable[[], None]:
        """Call ``receive`` on each cue, or when the connection is lost; returns the unsubscribe."""
        ...


class OperationChanges:
    """Wake an observation loop when an operation its session observes may have advanced.

    Nothing is subscribed until :meth:`arm` first runs, so an operation already
    settled at its first observation costs no subscription. Arm before each
    later observation, then wait after it: a cue that arrives while that
    observation is in flight still ends the wait. A lost connection wakes the
    wait too, and the next observation is refused at once.
    """

    def __init__(self, client: OperationCueSource) -> None:
        """Bind to the client whose operation cue the first arm subscribes to."""
        self._client = client
        self._changed = Event()
        self._unsubscribe: Callable[[], None] | None = None

    @property
    def armed(self) -> bool:
        """Whether the cue is subscribed, so a wait can end on it."""
        return self._unsubscribe is not None

    def arm(self) -> None:
        """Subscribe on first use, then forget earlier cues; call before the observation the next wait follows."""
        if self._unsubscribe is None:
            self._unsubscribe = self._client.subscribe_operation_changes(self._changed.set)
        self._changed.clear()

    def wait(self, timeout: float) -> None:
        """Block until a cue since the last arm, or until ``timeout`` seconds pass; an unbounded wait has none."""
        self._changed.wait(timeout if isfinite(timeout) else None)

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


class AsyncOperationChanges:
    """:class:`OperationChanges` for an event loop: the connection's reader thread wakes the loop.

    The first :meth:`arm` subscribes and binds the running loop, so it must
    run on the loop that later awaits :meth:`wait`.
    """

    def __init__(self, client: OperationCueSource) -> None:
        """Bind to the client whose operation cue the first arm subscribes to."""
        self._client = client
        self._changed: asyncio.Event | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._unsubscribe: Callable[[], None] | None = None

    @property
    def armed(self) -> bool:
        """Whether the cue is subscribed, so a wait can end on it."""
        return self._unsubscribe is not None

    def arm(self) -> None:
        """Subscribe on first use, then forget earlier cues; call before the observation the next wait follows."""
        if self._changed is None:
            self._loop = asyncio.get_running_loop()
            self._changed = asyncio.Event()
            self._unsubscribe = self._client.subscribe_operation_changes(self._wake)
        self._changed.clear()

    def _wake(self) -> None:
        loop, changed = self._loop, self._changed
        if loop is None or changed is None:
            return
        # A closed loop has nobody left waiting.
        with suppress(RuntimeError):
            loop.call_soon_threadsafe(changed.set)

    async def wait(self, timeout: float) -> None:
        """Wait until a cue since the last arm, or until ``timeout`` seconds pass; an unbounded wait has none."""
        changed = self._changed
        if changed is None:
            raise RuntimeError("arm before waiting")
        with suppress(TimeoutError):
            await asyncio.wait_for(changed.wait(), timeout if isfinite(timeout) else None)

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
