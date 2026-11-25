"""Owned recovery connections and their bounded opening contract."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Protocol

from cadrumo_client.contracts.deadline_budget import MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
from cadrumo_client.transport.frontend_client import FrontendClient


class RecoveryClientOpener(Protocol):
    """Open a fresh connection within the recovery operation's remaining budget."""

    async def __call__(self, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS) -> FrontendClient:
        """Return an owned connection before the supplied timeout."""
        ...


class RecoveryClientCleanup:
    """Retain one blocking connection until its native close succeeds."""

    def __init__(self, client: FrontendClient, *, released: Callable[[], None]) -> None:
        """Retain the client and its release notification."""
        self._client = client
        self._released = released

    async def close(self) -> None:
        """Close off-loop and report release only after closure succeeds."""
        await asyncio.to_thread(self._client.close)
        self._released()
