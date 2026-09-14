"""Application-owned capabilities for the capital-goods IVA register.

The register service and calculation/advisory paths consume this contract rather
than constructing the encrypted persistence adapter.  An executable composition
root binds one bucket-scoped implementation and supplies it explicitly to each
application path.
"""

from __future__ import annotations

from typing import Protocol

from ...domain.bienes_inversion.register import BienesInversionIvaRegister, BienInversionIvaRecord


class BienesInversionIvaRegisterRepositoryProtocol(Protocol):
    """Required bucket-bound read/write capability for capital-goods register state."""

    def load(self) -> BienesInversionIvaRegister:
        """Load the register, returning an empty register when no state exists."""
        ...

    def add(self, record: BienInversionIvaRecord) -> BienesInversionIvaRegister:
        """Atomically add one record and return the updated register."""
        ...


class BienesInversionIvaRegisterRepositoryFactory(Protocol):
    """Construct the register capability bound to one profile bucket."""

    def __call__(self, *, bucket_id: str) -> BienesInversionIvaRegisterRepositoryProtocol:
        """Return the required register capability for ``bucket_id``."""
        ...


__all__ = [
    "BienesInversionIvaRegisterRepositoryFactory",
    "BienesInversionIvaRegisterRepositoryProtocol",
]
