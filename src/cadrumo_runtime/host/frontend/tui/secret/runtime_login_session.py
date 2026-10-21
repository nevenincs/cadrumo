"""Exact-client acquisition and cleanup ownership for runtime login."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from cadrumo.core.async_cleanup import await_cancellation_complete
from cadrumo_client.transport.frontend_client import FrontendClient

type RuntimeClientOpener = Callable[[UUID], Awaitable[FrontendClient]]


async def open_to_completion(
    opener: RuntimeClientOpener, profile_id: UUID
) -> tuple[FrontendClient, asyncio.CancelledError | None]:
    """Retain an acquired client even when the screen is cancelled during open."""

    async def invoke() -> FrontendClient:
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

    client: FrontendClient | None = None
    dispatched: bool = False
    completed: bool = False
    primary_error: BaseException | None = None


@dataclass(slots=True)
class LoginAttemptState:
    """Track client custody and the primary error for one login attempt."""

    client: FrontendClient | None = None
    transferred: bool = False
    primary_error: BaseException | None = None
    unsubscribe_notice: Callable[[], None] | None = None
