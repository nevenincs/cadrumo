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
from ...domain.contribuyente.inventory.closing_authority_records import InventoryClosingAuthorityRecord
from ...domain.contribuyente.inventory.records import InventoryLedger, InventoryLedgerDocument, MovementRecord


class InventoryLedgerServiceRepositoryProtocol(Protocol):
    """Complete ledger capability required by :class:`InventoryService`."""

    def load(self) -> InventoryLedgerDocument:
        """Load the bucket's inventory document."""
        ...

    def create(self, ledger: InventoryLedger) -> InventoryLedgerDocument:
        """Atomically create one activity/year ledger."""
        ...

    def record_movement(
        self,
        actividad_id: str,
        movement: MovementRecord,
        *,
        year: int,
        validate_candidate: Callable[[InventoryLedger], None],
    ) -> InventoryLedger:
        """Append one movement after validating the latest guarded candidate."""
        ...

    def record_closing_authority(
        self,
        actividad_id: str,
        authority_record: InventoryClosingAuthorityRecord,
        *,
        year: int,
        validate_candidate: Callable[[InventoryLedger], InventoryLedger],
    ) -> InventoryClosingAuthorityWrite:
        """Validate and atomically record one latest-candidate closing authority."""
        ...

    def apply_ledger_change(
        self,
        actividad_id: str,
        *,
        year: int,
        change: Callable[[InventoryLedgerDocument, InventoryLedger], InventoryLedger],
    ) -> InventoryLedgerWrite:
        """Apply one domain change to the latest ledger inside the revision guard."""
        ...


@dataclass(frozen=True, slots=True)
class InventoryClosingAuthorityWrite:
    """Actual closing-authority state returned by the revision-guarded repository."""

    ledger: InventoryLedger
    changed: bool


@dataclass(frozen=True, slots=True)
class InventoryLedgerWrite:
    """The ledger as stored and whether this call changed it; false is an exact replay."""

    ledger: InventoryLedger
    changed: bool


InventoryRepositoryFactory = Callable[[str], InventoryLedgerServiceRepositoryProtocol]


@dataclass(frozen=True, slots=True)
class InventoryServicePorts:
    """Required persisted authorities for one inventory service instance."""

    inventory_repository_factory: InventoryRepositoryFactory
    bucket_event_repository: BucketEventHistoryRepositoryProtocol
    document_file_name: Callable[[str], str | None]
    """The name a held document arrived under, by digest; ``None`` when none is held."""


class InventoryServicePortsFactory(Protocol):
    """Construct the complete inventory capability bundle for one bucket."""

    def __call__(self, *, bucket_id: str) -> InventoryServicePorts:
        """Return inventory capabilities bound to ``bucket_id``."""
        ...


__all__ = [
    "InventoryClosingAuthorityWrite",
    "InventoryLedgerServiceRepositoryProtocol",
    "InventoryLedgerWrite",
    "InventoryRepositoryFactory",
    "InventoryServicePorts",
    "InventoryServicePortsFactory",
]
