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
from typing import TYPE_CHECKING, Protocol

from ...domain.bienes_inversion.register import BienesInversionIvaRegister
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..aggregation.inventory import InventoryLedgerRepositoryProtocol
from ..aggregation.percepciones_observations_repository import PercepcionObservationPorts
from ..aggregation.retencion_observations_repository import RetencionObservationPorts
from ..bienes_inversion.ports import BienesInversionIvaRegisterRepositoryProtocol
from ..calculations.iva_compensation_history_ports import IvaCompensationHistoryRepositoryProtocol
from ..invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from ..invoices.source_resolver_ports import InvoiceSourceResolverPorts
from ..ledger.usage_ratio_repository import UsageRatioProfileLoader
from ..live.borrador_100 import Borrador100SnapshotRepository
from ..prorrata_register.ports import ProrrataRegisterServiceRepositoryProtocol
from ..user_profile.profile_read_ports import ProfileReadPorts
from .verification_repository_ports import (
    CalculationObservationRepositoryProtocol,
    IvaWalletDecisionRepositoryProtocol,
)
from .work_lifecycle_ports import WorkLifecyclePorts

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


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


class CalculationRevisionOverrideMigrationProtocol(Protocol):
    """Boundary capability for legacy relation-override migration."""

    def migrate(
        self,
        repository: CalculationRevisionCatalogueRepositoryProtocol,
        *,
        operation: PinnedAuthorityOperation,
    ) -> None:
        """Bring persisted calculation relation overrides to current keying."""
        ...


@dataclass(frozen=True, slots=True)
class CalculationActionPorts:
    """Required persisted authorities for one Modelo calculation invocation."""

    operation: PinnedAuthorityOperation
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol
    work_lifecycle_ports: WorkLifecyclePorts
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol
    bucket_event_repository: BucketEventHistoryRepositoryProtocol
    transaction_repository: CalculationTransactionRepositoryProtocol
    usage_ratio_profile_loader: UsageRatioProfileLoader
    profile_read_ports: ProfileReadPorts
    invoice_repository: InvoiceCatalogueRepositoryProtocol
    invoice_catalogue_read_ports: InvoiceCatalogueReadPorts
    filing_repository: ModeloRecordCatalogueRepositoryProtocol
    prorrata_register_repository: ProrrataRegisterServiceRepositoryProtocol
    bienes_inversion_repository: BienesInversionIvaRegisterRepositoryProtocol
    inventory_repository: InventoryLedgerRepositoryProtocol
    observation_repository: CalculationObservationRepositoryProtocol
    invoice_source_ports: InvoiceSourceResolverPorts
    percepciones_observation_ports: PercepcionObservationPorts
    iva_compensation_history_repository: IvaCompensationHistoryRepositoryProtocol
    iva_compensation_decision_repository: CalculationIvaWalletDecisionRepositoryProtocol
    borrador_snapshot_repository: Borrador100SnapshotRepository
    retencion_observation_ports: RetencionObservationPorts
    relation_override_migration: CalculationRevisionOverrideMigrationProtocol


class CalculationActionPortsFactory(Protocol):
    """Construct the calculation authorities for one profile bucket."""

    def __call__(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> CalculationActionPorts:
        """Return the complete calculation bundle for ``bucket_id``."""
        ...


__all__ = [
    "CalculationActionPorts",
    "CalculationActionPortsFactory",
    "CalculationIvaWalletDecisionRepositoryProtocol",
    "CalculationRevisionOverrideMigrationProtocol",
    "CalculationTransactionRepositoryProtocol",
]
