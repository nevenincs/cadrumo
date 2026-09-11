"""Focused create-action fixtures and assertion expectations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC as _UTC
from datetime import date, datetime
from decimal import Decimal as _Decimal

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository as _InvoiceCatalogueRepository
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository as _SecureObjectRepository
from ....application.ledger.actions_manual import create_manual_transaction as _create_manual_transaction
from ....core.aggregation import BindingSourceKind
from ....domain.buckets.event import BucketEvent as _BucketEvent
from ....domain.buckets.event import BucketEventType as _BucketEventType
from ....domain.invoices.models import InvoiceCatalogue as _InvoiceCatalogue
from ....domain.transactions.enums import BusinessClassification as _BusinessClassification
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction as _Transaction
from ..models import ManualLedgerTransactionCommand as _ManualLedgerTransactionCommand
from ..models import ManualLedgerTransactionResult as _ManualLedgerTransactionResult
from .action_fixtures import _BUCKET_ID, _repositories, purchase_invoice

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
    result = _create_manual_transaction(
        command,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
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
