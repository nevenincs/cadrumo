"""Wait for upgrade notices within their shared deadline."""

from __future__ import annotations

import time
from threading import Event

from cadrumo_client.contracts.transport import ConnectionContext

from .session_events import RuntimeSessionEvents


def flush_upgrade_notices(
    events: RuntimeSessionEvents, eligible: tuple[ConnectionContext, ...], deadline: float
) -> bool:
    """Wait for each delivered notice without exceeding the deadline."""
    pending: list[Event] = []
    for context in eligible:
        if time.monotonic() >= deadline:
            return False
        flushed = events.upgrade_pending(context)
        if flushed is not None:
            pending.append(flushed)
    return (
        all(flushed.wait(max(0.0, deadline - time.monotonic())) for flushed in pending) and time.monotonic() < deadline
    )
