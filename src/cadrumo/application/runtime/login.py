"""Trusted native login evidence supplied by the local transport owner."""

from typing import Protocol

from ..user_profile.access_contracts import Availability, OsLoginContext


class RuntimeLoginEvidence(Protocol):
    """Nonportable native provenance; never constructed from a client document."""

    @property
    def login_id(self) -> str:
        """Identify one non-reused native login incarnation."""
        ...

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Reobserve native lifetime and lock state independently of store readiness."""
        ...
