"""Application-owned persistence capability for the own bank account register.

The register document and its invariants live in the transactions domain; the
encrypted store is supplied by an outer composition root through this narrow
protocol, so ledger operations and modelo exports read one register.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from ...domain.transactions.own_accounts import OwnAccountRegister


class OwnAccountRepositoryProtocol(Protocol):
    """Required bucket-bound operations on the own-account register singleton."""

    def load(self) -> OwnAccountRegister:
        """Load the register, or an empty one when none was ever written."""
        ...

    def mutate(self, change: Callable[[OwnAccountRegister], OwnAccountRegister]) -> OwnAccountRegister:
        """Apply ``change`` under the register's revision guard and return the stored result."""
        ...


class OwnAccountRepositoryFactory(Protocol):
    """Construct the register capability for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> OwnAccountRepositoryProtocol:
        """Return the capability bound to ``bucket_id``."""
        ...


__all__ = ["OwnAccountRepositoryFactory", "OwnAccountRepositoryProtocol"]
