"""Explicit ports required by a bucket-scoped ledger action.

The bundle is data, not a resolver: an entrypoint composition root builds it
for one bucket and passes its members to the public action it invokes.
"""

from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True)
class LedgerActionPorts:
    """All persistence ports one ledger action may need for one bucket."""

    transaction_repository: TransactionCatalogueCoCommitWriterProtocol
    bucket_event_repository: BucketEventHistoryCoCommitWriterProtocol
    invoice_repository: InvoiceCatalogueCoCommitWriterProtocol
    attachment_store: AttachmentStoreProtocol
    usage_ratio_profile: UsageRatioProfile
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol
    purchase_invoice_evidence_records: tuple[PurchaseInvoiceEvidence, ...]


__all__ = ["LedgerActionPorts"]
