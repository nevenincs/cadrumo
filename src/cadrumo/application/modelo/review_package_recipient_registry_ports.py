"""Application-owned persistence capability for trusted recipients.

Recipient registration is separate from recipient encryption: this capability
stores and retrieves the taxpayer's trusted-public-key register, while the
recipient-encryption capability seals and opens package bytes.  The executable
composition root supplies this required bucket-scoped capability; storage
namespaces, secure-object repositories, and their failures remain outward.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .review_package_recipient_registry import RecipientFingerprintRegister


@runtime_checkable
class RecipientFingerprintRegistryRepositoryPort(Protocol):
    """Load and save the complete trusted-recipient register for one bucket."""

    def load(self) -> RecipientFingerprintRegister:
        """Return the current register, or an empty register when absent."""
        ...

    def save(self, register: RecipientFingerprintRegister) -> None:
        """Persist one validated register as the bucket's current state."""
        ...


@dataclass(frozen=True, slots=True)
class RecipientFingerprintRegistryPorts:
    """Required trusted-recipient authority for one bucket-scoped call."""

    registry_repository: RecipientFingerprintRegistryRepositoryPort


class RecipientFingerprintRegistryPortsFactory(Protocol):
    """Construct the trusted-recipient capability for one bucket."""

    def __call__(self, *, bucket_id: str) -> RecipientFingerprintRegistryPorts:
        """Return the registry capability bound to ``bucket_id``."""
        ...


__all__ = [
    "RecipientFingerprintRegistryPorts",
    "RecipientFingerprintRegistryPortsFactory",
    "RecipientFingerprintRegistryRepositoryPort",
]
