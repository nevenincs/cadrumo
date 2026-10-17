"""Wait for a session's operations to advance on the runtime's cue instead of a fixed interval."""

from __future__ import annotations

from collections.abc import Callable
from math import isfinite
from threading import Event
from types import TracebackType
from typing import Self

from .frontend_client import FrontendClient


class OperationChanges:
    """Wake an observation loop when an operation its session observes may have advanced.

    Nothing is subscribed until :meth:`arm` first runs, so an operation already
    settled at its first observation costs no subscription. Arm before each
    later observation, then wait after it: a cue that arrives while that
    observation is in flight still ends the wait. A lost connection wakes the
    wait too, and the next observation is refused at once.
    """

    def __init__(self, client: FrontendClient) -> None:
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
