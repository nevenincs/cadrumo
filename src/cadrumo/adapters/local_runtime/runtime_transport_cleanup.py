"""Retained native transport ownership and retryable failure cleanup."""

from __future__ import annotations

import asyncio
import time
from threading import RLock
from typing import Protocol

from ...application.runtime.contracts import (
    RuntimeRefusalCode,
    RuntimeRefusalError,
)
from ...core.async_cleanup import AsyncResourceCleanupError, attach_async_cleanup_error


class RuntimeTransportResource(Protocol):
    """Native transport ownership with synchronous release."""

    def close(self) -> None:
        """Release the owned channel, connection or listener."""
        ...


class RuntimeTransportCleanup:
    """Retain native transport release, with success-only close bookkeeping."""

    def __init__(self, resource: RuntimeTransportResource) -> None:
        """Keep native transport ownership until its release succeeds."""
        self.resource = resource
        self._released = False
        self._close_guard = RLock()

    def close_now(self, *, deadline: float | None = None) -> None:
        """Release synchronously at the owning native failure boundary."""
        if deadline is None:
            self._close_guard.acquire()
        elif not self._close_guard.acquire(timeout=max(0.0, deadline - time.monotonic())):
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        try:
            if not self._released:
                self.resource.close()
                self._released = True
        finally:
            self._close_guard.release()

    @property
    def released(self) -> bool:
        """Report successful release for its enclosing connection owner."""
        return self._released

    async def close(self) -> None:
        """Keep blocking native release off the event loop, including retries."""
        await asyncio.to_thread(self.close_now)


def close_runtime_transport_after_failure(resource: RuntimeTransportResource, error: BaseException) -> None:
    """Preserve a primary refusal and retain its failed native release for retry."""
    retained = error.__dict__.get("_runtime_transport_cleanup")
    if isinstance(retained, RuntimeTransportCleanup) and retained.resource is resource:
        return
    owner = RuntimeTransportCleanup(resource)
    error.__dict__["_runtime_transport_cleanup"] = owner
    try:
        owner.close_now()
    except BaseException as cleanup_failure:
        cleanup_error = AsyncResourceCleanupError(
            (owner,), (cleanup_failure,), retry_task_name="runtime-transport-cleanup", close_attempts=1
        )
        attach_async_cleanup_error(
            error,
            cleanup_error,
            note="Transport cleanup also failed; retry through the attached async_cleanup_error",
        )
