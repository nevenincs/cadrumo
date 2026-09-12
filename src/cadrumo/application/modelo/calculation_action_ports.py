"""Application-owned capabilities required by Modelo calculation actions.

The calculation action coordinates several persisted authorities, but it must
not know which encrypted-storage adapters implement them.  Executable
composition roots construct one bundle per profile bucket and pass it through
the calculation call chain.  Keeping the less-common capabilities here also
keeps the action boundary honest: calculation cannot silently construct a
repository or resolve an implicit global store when a caller forgets a port.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...domain.bienes_inversion.register import BienesInversionIvaRegister
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..aggregation.inventory import InventoryLedgerRepositoryProtocol
from .verification_repository_ports import (
    CalculationObservationRepositoryProtocol,
    IvaWalletDecisionRepositoryProtocol,
)


class CalculationTransactionRepositoryProtocol(TransactionCatalogueRepositoryProtocol, Protocol):
    """Transaction authority with the IVA investment migration capability."""

    def migrate_iva_deduction_authority(
        self,
        *,
        asset_profile_id: str,
    ) -> BienesInversionIvaRegister:
        """Migrate and return the reciprocal capital-goods IVA authority."""
        ...


class CalculationIvaWalletDecisionRepositoryProtocol(IvaWalletDecisionRepositoryProtocol, Protocol):
    """IVA-wallet read capability plus the calculation decision write."""

    def save_decision(self, decision: object) -> None:
        """Persist the selected reconciliation decision."""
        ...


class CalculationBorradorSnapshotRepositoryProtocol(Protocol):
    """Read capability for a selected Modelo 100 draft snapshot."""

    def load(self, snapshot_id: str) -> object:
        """Return the addressed snapshot or raise its typed not-found error."""
        ...


class CalculationRevisionOverrideMigrationProtocol(Protocol):
    """Boundary capability for legacy relation-override migration."""

    def migrate(self, repository: CalculationRevisionCatalogueRepositoryProtocol) -> None:
        """Bring persisted calculation relation overrides to current keying."""
        ...


@dataclass(frozen=True, slots=True)
class CalculationActionPorts:
    """Required persisted authorities for one Modelo calculation invocation."""

    work_unit_repository: WorkUnitCatalogueRepositoryProtocol
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol
    bucket_event_repository: BucketEventHistoryRepositoryProtocol
    transaction_repository: CalculationTransactionRepositoryProtocol
    invoice_repository: InvoiceCatalogueRepositoryProtocol
    filing_repository: ModeloRecordCatalogueRepositoryProtocol
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol
    inventory_repository: InventoryLedgerRepositoryProtocol
    observation_repository: CalculationObservationRepositoryProtocol
    iva_compensation_decision_repository: CalculationIvaWalletDecisionRepositoryProtocol
    borrador_snapshot_repository: CalculationBorradorSnapshotRepositoryProtocol
    relation_override_migration: CalculationRevisionOverrideMigrationProtocol


class CalculationActionPortsFactory(Protocol):
    """Construct the calculation authorities for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> CalculationActionPorts:
        """Return the complete calculation bundle for ``bucket_id``."""
        ...


__all__ = [
    "CalculationActionPorts",
    "CalculationActionPortsFactory",
    "CalculationBorradorSnapshotRepositoryProtocol",
    "CalculationIvaWalletDecisionRepositoryProtocol",
    "CalculationRevisionOverrideMigrationProtocol",
    "CalculationTransactionRepositoryProtocol",
]
