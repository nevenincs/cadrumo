"""Authenticated, read-only censo acquisition from AEAT.

The returned observation is not adopted until the user-profile workflow reviews
and commits it through its separate canonical authority.
"""

from __future__ import annotations

from ...adapters.outbound.aeat.sede import fetch_censal_datos
from .session import active_verified_session

LIVE_CENSAL_READ_OPERATION = "live-censal-read"


async def pull_censal_datos():
    """Read the authenticated taxpayer's censo state without persisting or adopting it."""
    session, settings = await active_verified_session(operation=LIVE_CENSAL_READ_OPERATION)
    return await fetch_censal_datos(session, taxpayer_nif=session.identity_nif, settings=settings)


__all__ = ["LIVE_CENSAL_READ_OPERATION", "pull_censal_datos"]
