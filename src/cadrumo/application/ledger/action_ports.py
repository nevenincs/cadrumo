"""Explicit ports required by a bucket-scoped ledger action.

The bundle is data, not a resolver: an entrypoint composition root builds it
for one bucket and passes its members to the public action it invokes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from ...domain.attachments.protocols import AttachmentStoreProtocol
from ...domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ...domain.usage_ratios.model import UsageRatioProfile
from .evidence import PurchaseInvoiceEvidence
from .protocols import (
    BucketEventHistoryCoCommitWriterProtocol,
    InvoiceCatalogueCoCommitWriterProtocol,
    TransactionCatalogueCoCommitWriterProtocol,
)
from .usage_ratio_repository import UsageRatioProfileLoader

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


@dataclass(frozen=True)
class LedgerActionPorts:
    """All persistence ports one ledger action may need for one bucket."""

    operation: PinnedAuthorityOperation
    transaction_repository: TransactionCatalogueCoCommitWriterProtocol
    bucket_event_repository: BucketEventHistoryCoCommitWriterProtocol
    invoice_repository: InvoiceCatalogueCoCommitWriterProtocol
    attachment_store: AttachmentStoreProtocol
    usage_ratio_profile: UsageRatioProfile
    usage_ratio_profile_loader: UsageRatioProfileLoader
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol
    purchase_invoice_evidence_records: tuple[PurchaseInvoiceEvidence, ...]


class LedgerActionPortsFactory(Protocol):
    """Compose one profile's existing ledger services under the retained authority."""

    def __call__(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
        """Return the service ports bound to ``bucket_id`` and ``operation``."""
        ...


__all__ = ["LedgerActionPorts", "LedgerActionPortsFactory"]
