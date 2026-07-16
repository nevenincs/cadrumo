"""Shared browser-session teardown for Cl@ve auth providers."""

from __future__ import annotations

import asyncio
import logging

from ._authenticator_types import BrowserSessionLike


async def close_owned_browser_session(
    session: BrowserSessionLike | None,
    *,
    timeout_ms: int,
    logger: logging.Logger,
    owner: str,
) -> bool:
    """Close an owned browser session within ``timeout_ms``.

    Returns ``True`` when no session exists or teardown completes. A timeout or
    close failure is logged and returns ``False`` so the provider retains the
    session reference and a later :meth:`close` call can retry.
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


__all__ = ["close_owned_browser_session"]
