"""Retryable cleanup owner used by requester cancellation paths."""

from __future__ import annotations

from collections.abc import Awaitable, Callable


class RequesterCleanup:
    """Keep failed cleanup owned until a cancellation-complete retry succeeds."""

    def __init__(self, close: Callable[[], Awaitable[None]], *, released: Callable[[], None]) -> None:
        """Retain the close operation and release callback after construction."""
        self._close = close
        self._released = released

    async def close(self) -> None:
        """Close the resource before removing this cleanup owner."""
        await self._close()
        self._released()
