"""Application-owned capability for an authenticated censal read.

The live censo use case owns the observation it returns and the application
error boundary it exposes.  Browser navigation, Sede parsing, and their
provider-specific failures are supplied by an outer composition root through
this narrow port.
"""

from __future__ import annotations

from typing import Protocol

from ...core.config import Settings
from ..auth.session_types import AeatSession
from ..user_profile.censal_observation import CensalObservation


class CensalFetchPort(Protocol):
    """Read the authenticated taxpayer's application-owned censo observation."""

    async def __call__(
        self,
        session: AeatSession,
        *,
        taxpayer_nif: str,
        settings: Settings,
    ) -> CensalObservation:
        """Return one translated censal observation.

        The outer implementation translates Sede DTOs and failures into the
        application contract before returning or raising.  In particular, no
        Sede exception or adapter-owned record type crosses this port.
        """
        ...


__all__ = ["CensalFetchPort"]
