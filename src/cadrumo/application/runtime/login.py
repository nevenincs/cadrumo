"""Trusted native login evidence supplied by the local transport owner."""

from dataclasses import dataclass
from typing import Protocol

from ..user_profile.access_contracts import Availability, LoginEligibility, OsLoginContext


class RuntimeLoginEvidence(Protocol):
    """Nonportable native provenance; never constructed from a client document."""

    @property
    def login_id(self) -> str:
        """Identify one non-reused native login incarnation."""
        ...

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Reobserve native lifetime and lock state independently of store readiness."""
        ...


@dataclass(frozen=True)
class RuntimeLoginInventory:
    """Fresh native owner witnesses; incomplete absence never proves logout.

    Trusted adapters supply eligible incarnations independently of credential
    facilities. Consumers must reobserve each witness before authorization.
    """

    logins: tuple[RuntimeLoginEvidence, ...]
    complete: bool

    @property
    def eligibility(self) -> LoginEligibility:
        """Distinguish a positive witness, proven absence and uncertain absence."""
        if self.logins:
            return LoginEligibility.ELIGIBLE
        return LoginEligibility.INELIGIBLE if self.complete else LoginEligibility.UNKNOWN
