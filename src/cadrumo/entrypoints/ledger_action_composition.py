"""Outer composition for bucket-scoped ledger action persistence."""

from __future__ import annotations

from ..application.ledger.action_ports import LedgerActionPorts


def compose_ledger_action_ports(*, bucket_id: str) -> LedgerActionPorts:
    """Build the complete explicit persistence bundle for ``bucket_id``."""
    from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ..adapters.persistence.profile.invoices import InvoiceCatalogueRepository
    from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
    from ..adapters.persistence.profile.usage_ratios import load_usage_ratios
    from ..adapters.persistence.storage.attachment import resolve_attachment_store
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ..core.config import load_settings
    from ..application.ledger.evidence import PurchaseInvoiceEvidenceRepository

    objects = secure_object_repository_for_bucket(bucket_id)
    evidence_document = PurchaseInvoiceEvidenceRepository(
        objects=secure_object_repository_for_bucket(bucket_id, load_settings())
    ).load(bucket_id)

    return LedgerActionPorts(
        transaction_repository=TransactionCatalogueRepository(bucket_id=bucket_id),
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=bucket_id),
        attachment_store=resolve_attachment_store(None),
        usage_ratio_profile=load_usage_ratios(bucket_id=bucket_id),
        work_unit_repository=WorkUnitCatalogueRepository(),
        calculation_repository=CalculationRevisionCatalogueRepository(),
        purchase_invoice_evidence_records=() if evidence_document is None else evidence_document.records,
    )


__all__ = ["compose_ledger_action_ports"]
