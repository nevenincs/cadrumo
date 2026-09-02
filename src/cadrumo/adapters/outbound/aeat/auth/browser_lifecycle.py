"""Shared browser lifecycle primitives for AEAT authentication providers."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from .....application.auth.protocols import BrowserContextPort, BrowserSessionPort


class _CloseIntentBarrier:
    """Serialize closers and bar new work while any close intent exists."""

    def __init__(self) -> None:
        self._gate = asyncio.Lock()
        self._state_lock = asyncio.Lock()
        self._close_intents = 0
        self._no_close_intents = asyncio.Event()
        self._no_close_intents.set()

    @property
    def closing(self) -> bool:
        """Return whether one or more close callers are registered."""
        return self._close_intents > 0

    @property
    def close_intents(self) -> int:
        """Return the number of registered close callers."""
        return self._close_intents

    @asynccontextmanager
    async def work(self) -> AsyncGenerator[None]:
        """Enter ordinary work only when every registered closer has exited."""
        while True:
            await self._no_close_intents.wait()
            await self._gate.acquire()
            if not self.closing:
                break
            self._gate.release()
        try:
            yield
        finally:
            self._gate.release()

    @asynccontextmanager
    async def close(self) -> AsyncGenerator[None]:
        """Register one close intent and serialize its teardown sequence."""
        async with self._state_lock:
            self._close_intents += 1
            self._no_close_intents.clear()
        try:
            async with self._gate:
                yield
        finally:
            async with self._state_lock:
                self._close_intents -= 1
                if self._close_intents == 0:
                    self._no_close_intents.set()


async def close_owned_browser_context(
    context: BrowserContextPort | None,
    *,
    timeout_ms: int,
    logger: logging.Logger,
    owner: str,
) -> bool:
    """Close an owned browser context within ``timeout_ms`` and report completion."""
    if context is None:
        return True
    try:
        await asyncio.wait_for(
            context.close(),
            timeout=timeout_ms / 1000,
        )
    except TimeoutError:
        logger.warning(
            "%s: browser context close exceeded %d ms",
            owner,
            timeout_ms,
        )
        return False
    except Exception:
        logger.warning("%s: browser context close failed", owner, exc_info=True)
        return False
    return True


async def close_owned_browser_session(
    session: BrowserSessionPort | None,
    *,
    timeout_ms: int,
    logger: logging.Logger,
    owner: str,
) -> bool:
    """Close an owned browser session within ``timeout_ms``.

    Returns ``True`` when no session exists or teardown completes. A timeout or
    close failure is logged and returns ``False`` so the provider retains the
    session reference and a later
    :meth:`~cadrumo.application.auth.protocols.BrowserSessionPort.close`
    call can retry.
    """
    if session is None:
        return True
    try:
        await asyncio.wait_for(
            session.close(),
            timeout=timeout_ms / 1000,
        )
    except TimeoutError:
        logger.warning(
            "%s: browser session close exceeded %d ms",
            owner,
            timeout_ms,
        )
        return False
    except Exception:  # Browser-session teardown must not mask the primary auth failure.
        logger.warning("%s: browser session close failed", owner, exc_info=True)
        return False
    return True


__all__ = ["close_owned_browser_context", "close_owned_browser_session"]
