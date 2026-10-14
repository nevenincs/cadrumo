"""Bounded asynchronous condition polling through an injected pause port."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Protocol


class AsyncPausePort(Protocol):
    """A caller-owned asynchronous scheduler pause."""

    async def pause(self, delay: float) -> None:
        """Yield until the caller's scheduler has advanced by the delay."""
        ...


async def until(pilot: AsyncPausePort, condition: Callable[[], bool], *, seconds: float = 15) -> None:
    """Let the caller's scheduler run until the condition holds."""
    async with asyncio.timeout(seconds):
        while not condition():
            await pilot.pause(0.02)
