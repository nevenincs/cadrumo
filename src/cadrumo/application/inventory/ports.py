"""Application-owned capabilities for bucket-scoped inventory operations.

The inventory service coordinates ledger persistence and bucket-event emission,
but it does not know which encrypted repositories implement either capability.
An executable composition root supplies this complete bundle for each bucket.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.contribuyente.inventory.records import (
    InventoryClosingAuthorityRecord,
    InventoryLedger,
    InventoryLedgerDocument,
)


class InventoryLedgerServiceRepositoryProtocol(Protocol):
    """Complete ledger capability required by :class:`InventoryService`."""

    def load(self) -> InventoryLedgerDocument:
        """Load the bucket's inventory document."""
        ...

    def save(self, document: InventoryLedgerDocument) -> None:
        """Persist a validated inventory document."""
        ...

    def create(self, ledger: InventoryLedger) -> InventoryLedgerDocument:
        """Atomically create one activity/year ledger."""
        ...

    def record_closing_authority(
        self,
        actividad_id: str,
        authority_record: InventoryClosingAuthorityRecord,
        *,
        year: int,
    ) -> InventoryLedger:
        """Atomically record one closing-authority record."""
        ...

    def remove(self, actividad_id: str, *, year: int) -> InventoryLedger:
        """Atomically remove one activity/year ledger."""
        ...


InventoryRepositoryFactory = Callable[[str], InventoryLedgerServiceRepositoryProtocol]


@dataclass(frozen=True, slots=True)
class InventoryServicePorts:
    """Required persisted authorities for one inventory service instance."""

    inventory_repository_factory: InventoryRepositoryFactory
    bucket_event_repository: BucketEventHistoryRepositoryProtocol


class InventoryServicePortsFactory(Protocol):
    """Construct the complete inventory capability bundle for one bucket."""

    def __call__(self, *, bucket_id: str) -> InventoryServicePorts:
        """Return inventory capabilities bound to ``bucket_id``."""
        ...


__all__ = [
    "InventoryLedgerServiceRepositoryProtocol",
    "InventoryRepositoryFactory",
    "InventoryServicePorts",
    "InventoryServicePortsFactory",
]
