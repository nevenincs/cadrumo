"""Exact-client acquisition and cleanup ownership for runtime login."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....core.async_cleanup import await_cancellation_complete

type RuntimeClientOpener = Callable[[UUID], Awaitable[RuntimeFrontendClient]]


async def open_to_completion(
    opener: RuntimeClientOpener, profile_id: UUID
) -> tuple[RuntimeFrontendClient, asyncio.CancelledError | None]:
    """Retain an acquired client even when the screen is cancelled during open."""

    async def invoke() -> RuntimeFrontendClient:
        return await opener(profile_id)

    opening = asyncio.create_task(invoke(), name="tui-runtime-login-open")
    cancellation: asyncio.CancelledError | None = None
    while not opening.done():
        try:
            await asyncio.shield(opening)
        except asyncio.CancelledError as caught:
            if cancellation is None:
                cancellation = caught
        except BaseException:
            break
    try:
        return opening.result(), cancellation
    except BaseException:
        if cancellation is not None:
            await await_cancellation_complete(opening, task_name="tui-runtime-login-open", cancellation=cancellation)
        raise


class LoginCleanup:
    """Keep one untransferred connection or failed admission until close succeeds."""

    def __init__(self, close: Callable[[], Awaitable[None]], *, released: Callable[[], None]) -> None:
        """Retain cleanup and invoke release only after a successful close."""
        self._close = close
        self._released = released

    async def close(self) -> None:
        """Close the resource, then release its owner registration."""
        await self._close()
        self._released()


@dataclass(slots=True)
class ResumeAttemptState:
    """Track recovery progress so failures preserve the original refusal boundary."""

    client: RuntimeFrontendClient | None = None
    dispatched: bool = False
    completed: bool = False
    primary_error: BaseException | None = None


@dataclass(slots=True)
class LoginAttemptState:
    """Track client custody and the primary error for one login attempt."""

    client: RuntimeFrontendClient | None = None
    transferred: bool = False
    primary_error: BaseException | None = None
    unsubscribe_notice: Callable[[], None] | None = None
