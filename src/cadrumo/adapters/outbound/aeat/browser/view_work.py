"""Settle background work a Sede view spawns so that no failure escapes its task."""

from __future__ import annotations

import logging
from collections.abc import Awaitable

from ..playwright import PlaywrightError


async def settle(work: Awaitable[object], log: logging.Logger) -> None:
    """Await *work*, logging only the exception type; a vanished browser is routine, anything else is an error."""
    try:
        await work
    except PlaywrightError as exc:
        log.debug("aeat view page work ended exc_type=%s", type(exc).__name__)
    except Exception as exc:
        log.error("aeat view page work failed exc_type=%s", type(exc).__name__)
