"""Authenticated, read-only censo acquisition from AEAT.

The returned observation is not adopted until the user-profile workflow reviews
and commits it through its separate canonical authority.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .session import active_verified_session

if TYPE_CHECKING:
    from ..user_profile.censal_observation import CensalObservation

LIVE_CENSAL_READ_OPERATION = "live-censal-read"


async def pull_censal_datos() -> CensalObservation:
    """Read the authenticated taxpayer's censo state without persisting or adopting it."""
    from ...adapters.outbound.aeat.sede import fetch_censal_datos

    session, settings = await active_verified_session(operation=LIVE_CENSAL_READ_OPERATION)
    return await fetch_censal_datos(session, taxpayer_nif=session.identity_nif, settings=settings)


__all__ = ["LIVE_CENSAL_READ_OPERATION", "pull_censal_datos"]
