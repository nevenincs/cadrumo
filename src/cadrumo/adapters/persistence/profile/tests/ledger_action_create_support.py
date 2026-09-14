"""Focused create-action fixtures and assertion expectations."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC as _UTC
from datetime import date, datetime
from decimal import Decimal as _Decimal

from cadrumo.adapters.persistence.profile.buckets import (
    BucketEventHistoryRepository as _BucketEventHistoryRepository,
)
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository as _InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import (
    CalculationRevisionCatalogueRepository as _CalculationRevisionCatalogueRepository,
)
from cadrumo.adapters.persistence.profile.modelos_work_units import (
    WorkUnitCatalogueRepository as _WorkUnitCatalogueRepository,
)
from cadrumo.adapters.persistence.profile.purchase_invoice_evidence import (
    LedgerEvidenceRepositoryAdapter as _LedgerEvidenceRepositoryAdapter,
)
from cadrumo.adapters.persistence.profile.transactions import (
    TransactionCatalogueRepository as _TransactionCatalogueRepository,
)
from cadrumo.adapters.persistence.profile.usage_ratios import load_usage_ratios as _load_usage_ratios
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore as _AttachmentStore
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository as _SecureObjectRepository
from cadrumo.application.ledger.action_ports import LedgerActionPorts as _LedgerActionPorts
from cadrumo.application.ledger.actions_manual import create_manual_transaction as _create_manual_transaction
from cadrumo.application.ledger.evidence import PurchaseInvoiceEvidence as _PurchaseInvoiceEvidence
from cadrumo.application.ledger.models import ManualLedgerTransactionCommand as _ManualLedgerTransactionCommand
from cadrumo.application.ledger.models import ManualLedgerTransactionResult as _ManualLedgerTransactionResult
from cadrumo.application.ledger.protocols import (
    BucketEventHistoryCoCommitWriterProtocol as _BucketEventHistoryCoCommitWriterProtocol,
)
from cadrumo.application.ledger.protocols import (
    InvoiceCatalogueCoCommitWriterProtocol as _InvoiceCatalogueCoCommitWriterProtocol,
)
from cadrumo.application.ledger.protocols import (
    TransactionCatalogueCoCommitWriterProtocol as _TransactionCatalogueCoCommitWriterProtocol,
)
from cadrumo.application.ledger.usage_ratio_repository import UsageRatioProfileLoader as _UsageRatioProfileLoader
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.domain.attachments.protocols import AttachmentStoreProtocol as _AttachmentStoreProtocol
from cadrumo.domain.buckets.event import BucketEvent as _BucketEvent
from cadrumo.domain.buckets.event import BucketEventType as _BucketEventType
from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation as _PinnedAuthorityOperation,
)
from cadrumo.domain.calculations.registry.authority import (
    bundled_indexed_authority as _bundled_indexed_authority,
)
from cadrumo.domain.invoices.models import InvoiceCatalogue as _InvoiceCatalogue
from cadrumo.domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol as _CalculationRevisionCatalogueRepositoryProtocol,
)
from cadrumo.domain.modelos.work_unit_repository import (
    WorkUnitCatalogueRepositoryProtocol as _WorkUnitCatalogueRepositoryProtocol,
)
from cadrumo.domain.transactions.enums import BusinessClassification as _BusinessClassification
from cadrumo.domain.transactions.enums import TransactionDirection
from cadrumo.domain.transactions.models import Transaction as _Transaction
from cadrumo.domain.usage_ratios.model import UsageRatioProfile as _UsageRatioProfile

from .ledger_action_persistence_support import _BUCKET_ID, _repositories, purchase_invoice


@contextmanager
def ledger_ports_for_test(
    *,
    bucket_id: str,
    objects: _SecureObjectRepository,
    transaction_repository: _TransactionCatalogueCoCommitWriterProtocol | None = None,
    bucket_event_repository: _BucketEventHistoryCoCommitWriterProtocol | None = None,
    invoice_repository: _InvoiceCatalogueCoCommitWriterProtocol | None = None,
    attachment_store: _AttachmentStoreProtocol | None = None,
    usage_ratio_profile: _UsageRatioProfile | None = None,
    usage_ratio_profile_loader: _UsageRatioProfileLoader | None = None,
    work_unit_repository: _WorkUnitCatalogueRepositoryProtocol | None = None,
    calculation_repository: _CalculationRevisionCatalogueRepositoryProtocol | None = None,
    purchase_invoice_evidence_records: tuple[_PurchaseInvoiceEvidence, ...] | None = None,
) -> Iterator[_LedgerActionPorts]:
    """Yield test ledger ports while the authority operation lease is live.

    ``bucket_id`` and ``objects`` are deliberately required so every default
    persistence adapter is bound to the caller's isolated secure store. The
    caller must keep this context open for the complete action under test;
    the yielded operation is valid only for that lifetime.
    """

    with _bundled_indexed_authority().operation() as operation:

        def load_pinned_usage_ratios(
            *,
            bucket_id: str,
            operation: _PinnedAuthorityOperation,
        ) -> _UsageRatioProfile:
            return _load_usage_ratios(bucket_id=bucket_id, operation=operation, objects=objects)

        resolved_transaction_repository: _TransactionCatalogueCoCommitWriterProtocol = (
            transaction_repository
            if transaction_repository is not None
            else _TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects)
        )
        resolved_bucket_event_repository: _BucketEventHistoryCoCommitWriterProtocol = (
            bucket_event_repository
            if bucket_event_repository is not None
            else _BucketEventHistoryRepository(objects=objects)
        )
        resolved_invoice_repository: _InvoiceCatalogueCoCommitWriterProtocol = (
            invoice_repository
            if invoice_repository is not None
            else _InvoiceCatalogueRepository(bucket_id=bucket_id, objects=objects)
        )
        resolved_attachment_store: _AttachmentStoreProtocol = (
            attachment_store if attachment_store is not None else _AttachmentStore(objects=objects, bucket_id=bucket_id)
        )
        resolved_usage_ratio_profile_loader: _UsageRatioProfileLoader = (
            usage_ratio_profile_loader if usage_ratio_profile_loader is not None else load_pinned_usage_ratios
        )
        resolved_usage_ratio_profile: _UsageRatioProfile = (
            usage_ratio_profile
            if usage_ratio_profile is not None
            else resolved_usage_ratio_profile_loader(bucket_id=bucket_id, operation=operation)
        )
        resolved_work_unit_repository: _WorkUnitCatalogueRepositoryProtocol = (
            work_unit_repository
            if work_unit_repository is not None
            else _WorkUnitCatalogueRepository(bucket_id=bucket_id, objects=objects)
        )
        resolved_calculation_repository: _CalculationRevisionCatalogueRepositoryProtocol = (
            calculation_repository
            if calculation_repository is not None
            else _CalculationRevisionCatalogueRepository(bucket_id=bucket_id, objects=objects)
        )
        resolved_purchase_invoice_evidence_records: tuple[_PurchaseInvoiceEvidence, ...] = (
            purchase_invoice_evidence_records
            if purchase_invoice_evidence_records is not None
            else _LedgerEvidenceRepositoryAdapter(objects=objects).load(bucket_id=bucket_id)
        )

        yield _LedgerActionPorts(
            operation=operation,
            transaction_repository=resolved_transaction_repository,
            bucket_event_repository=resolved_bucket_event_repository,
            invoice_repository=resolved_invoice_repository,
            attachment_store=resolved_attachment_store,
            usage_ratio_profile=resolved_usage_ratio_profile,
            usage_ratio_profile_loader=resolved_usage_ratio_profile_loader,
            work_unit_repository=resolved_work_unit_repository,
            calculation_repository=resolved_calculation_repository,
            purchase_invoice_evidence_records=resolved_purchase_invoice_evidence_records,
        )


__all__ = [
    "POST_UPDATE_EVENT_PAYLOADS",
    "PRESERVED_CREATE_AUDIT_FIELDS",
    "PROVENANCE_RAW_FIELD_EXPECTATIONS",
    "TAXABLE_IVA_EXPECTATIONS",
    "UPDATED_FIELD_EXPECTATIONS",
    "CreateManualOutcome",
    "drive_create_manual_transaction",
]


@dataclass(frozen=True, slots=True)
class CreateManualOutcome:
    """Bundle returned by the focused create-action scenario."""

    result: _ManualLedgerTransactionResult
    persisted: _Transaction
    events: tuple[_BucketEvent, ...]
    purchase_invoice_evidence_id: str


def drive_create_manual_transaction(secure_objects: _SecureObjectRepository) -> CreateManualOutcome:
    """Build and execute the canonical create-action scenario."""
    transaction_repository, event_repository = _repositories(secure_objects)
    invoice_repository = _InvoiceCatalogueRepository(objects=secure_objects)
    purchase_evidence = purchase_invoice()
    invoice_repository.save(_InvoiceCatalogue.from_invoices((purchase_evidence,)))
    command = _ManualLedgerTransactionCommand(
        bucket_id=_BUCKET_ID,
        booked_date=date(2026, 5, 2),
        value_date=date(2026, 5, 3),
        amount=_Decimal("121.00"),
        currency="EUR",
        direction=TransactionDirection.OUTGOING,
        counterparty="Proveedor SL",
        description="material oficina",
        business_classification=_BusinessClassification.BUSINESS,
        category_id="office-supplies",
        taxable_base=_Decimal("100.00"),
        iva_rate=_Decimal("0.21"),
        iva_amount=_Decimal("21.00"),
        purchase_invoice_evidence_id=purchase_evidence.invoice_id,
        actor="operator-A",
        source_command="aeat app ledger add",
        idempotency_key="cash-2026-05-02-001",
    )
    with ledger_ports_for_test(
        bucket_id=_BUCKET_ID,
        objects=secure_objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
    ) as ports:
        result = _create_manual_transaction(
            command,
            ports=ports,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=_UTC),
        )
    reloaded = transaction_repository.load()
    persisted = reloaded.get(result.ref.transaction_id)
    assert persisted is not None
    assert tuple(reloaded.transactions) == (result.ref.transaction_id,)
    events = event_repository.load().for_bucket(_BUCKET_ID)
    return CreateManualOutcome(
        result=result,
        persisted=persisted,
        events=tuple(events),
        purchase_invoice_evidence_id=purchase_evidence.invoice_id,
    )


_PROVENANCE_RAW_FIELD_EXPECTATIONS = (
    ("source_kind", BindingSourceKind.LEDGER_TRANSACTION.value),
    ("taxable_base", "100.00"),
)

_TAXABLE_IVA_EXPECTATIONS = (
    ("taxable_base", _Decimal("100.00")),
    ("iva_rate", _Decimal("0.21")),
    ("iva_amount", _Decimal("21.00")),
)

_UPDATED_FIELD_EXPECTATIONS = (
    ("raw.description", "corrected description"),
    ("business_classification", _BusinessClassification.MIXED),
    ("business_pct", _Decimal("0.50")),
)

_PRESERVED_CREATE_AUDIT_FIELDS = ("created_by", "source_command", "created_event_id")

_POST_UPDATE_EVENT_PAYLOADS = (
    (_BucketEventType.LEDGER_TRANSACTION_UPDATED, "mutation_kind", "edit"),
    (_BucketEventType.LEDGER_TRANSACTION_CLASSIFIED, "mutation_kind", "classification"),
    (_BucketEventType.LEDGER_TRANSACTION_ALLOCATED, "mutation_kind", "allocation"),
)

POST_UPDATE_EVENT_PAYLOADS = _POST_UPDATE_EVENT_PAYLOADS
PRESERVED_CREATE_AUDIT_FIELDS = _PRESERVED_CREATE_AUDIT_FIELDS
PROVENANCE_RAW_FIELD_EXPECTATIONS = _PROVENANCE_RAW_FIELD_EXPECTATIONS
TAXABLE_IVA_EXPECTATIONS = _TAXABLE_IVA_EXPECTATIONS
UPDATED_FIELD_EXPECTATIONS = _UPDATED_FIELD_EXPECTATIONS
