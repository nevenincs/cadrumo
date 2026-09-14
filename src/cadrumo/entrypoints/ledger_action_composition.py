"""Outer composition for bucket-scoped ledger action persistence."""

from __future__ import annotations

from ..application.ledger.action_ports import LedgerActionPorts
from ..application.ledger.import_ports import LedgerImportPorts
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from ..domain.usage_ratios.model import UsageRatioProfile


def compose_ledger_action_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
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
    from .adapter_composition import build_ledger_evidence_ports

    settings = load_settings()
    objects = secure_object_repository_for_bucket(bucket_id, settings)
    evidence_records = build_ledger_evidence_ports(
        bucket_id=bucket_id,
    ).evidence_repository.load(bucket_id=bucket_id)

    def load_pinned_usage_ratios(
        *,
        bucket_id: str,
        operation: PinnedAuthorityOperation,
    ) -> UsageRatioProfile:
        return load_usage_ratios(bucket_id=bucket_id, operation=operation)

    return LedgerActionPorts(
        operation=operation,
        transaction_repository=TransactionCatalogueRepository(bucket_id=bucket_id),
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=bucket_id),
        attachment_store=resolve_attachment_store(None),
        usage_ratio_profile=load_pinned_usage_ratios(bucket_id=bucket_id, operation=operation),
        usage_ratio_profile_loader=load_pinned_usage_ratios,
        work_unit_repository=WorkUnitCatalogueRepository(bucket_id=bucket_id),
        calculation_repository=CalculationRevisionCatalogueRepository(bucket_id=bucket_id),
        purchase_invoice_evidence_records=evidence_records,
    )


def compose_ledger_import_ports() -> LedgerImportPorts:
    """Bind the concrete financial source and catalogue-location adapters."""
    from ..adapters.inbound.financial.ledger_import import build_ledger_import_ports

    return build_ledger_import_ports()


__all__ = ["compose_ledger_action_ports", "compose_ledger_import_ports"]
