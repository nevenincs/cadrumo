"""Shared support for manual ledger transaction application tests."""

# ruff: noqa: F401

from __future__ import annotations

import csv
import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest

from ....adapters.persistence.storage import StorageValidationError
from ....adapters.persistence.storage.attachment import AttachmentStore
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....application.export import ExportSerializationFormat
from ....core.aggregation import AggregationSourceKind
from ....domain.attachments import Attachment, AttachmentKind, AttachmentSource
from ....domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
)
from ....domain.categories import SpendingCategory
from ....domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    InvoiceLine,
    IvaRate,
    PaymentStatus,
)
from ....domain.iva import InvoiceKind
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos._codes import ModeloCode
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.modelos._work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionLifecycleState,
    TransactionNotFoundError,
    TransactionValidationError,
)
from ....domain.usage_ratios import UsageRatioProfile
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    LedgerExportCommand,
    LedgerReviewQuery,
    LedgerSourceImportCommand,
    ManualLedgerTransactionCommand,
    ManualLedgerTransactionPatch,
    ManualLedgerTransactionResult,
    archive_manual_transaction,
    attach_manual_transaction_evidence,
    create_manual_transaction,
    export_ledger_transactions,
    get_manual_transaction,
    import_ledger_source,
    import_ledger_transactions,
    ledger_transaction_review_status,
    list_manual_transactions,
    query_ledger_review_rows,
    remove_manual_transaction,
    reset_ledger_catalogue,
    restore_manual_transaction,
    stash_manual_transaction,
    summarize_manual_transactions,
    update_manual_transaction,
    update_manual_transaction_fields,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="bucket-a") as profile:
        yield profile.repository


def _repositories(objects: SecureObjectRepository, *, bucket_id: str = "bucket-a"):
    return (
        TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects),
        BucketEventHistoryRepository(objects=objects),
    )


def _purchase_invoice() -> Invoice:
    line = InvoiceLine(
        description="Material oficina",
        quantity=Decimal("1"),
        unit_price=Decimal("100.00"),
        subtotal=Decimal("100.00"),
        iva_rate=IvaRate.RATE_21,
        iva_amount=Decimal("21.00"),
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.RECEIVED,
            "bucket_id": "bucket-a",
            "invoice_number": "P-2026-001",
            "issued_at": date(2026, 5, 2),
            "counterparty_name": "Proveedor SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
        }
    )


def _raw_import_transaction(
    *,
    transaction_id: str = "provider-row-1",
    amount: Decimal = Decimal("-80.00"),
    description: str = "provider import row",
) -> RawTransaction:
    return RawTransaction(
        transaction_id=transaction_id,
        booked_date=date(2026, 5, 1),
        value_date=date(2026, 5, 1),
        amount=amount,
        currency="EUR",
        counterparty="Proveedor SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": description},
    )


def _persist_verified_revision_citing_transaction(
    objects: SecureObjectRepository, *, transaction_id: str, bucket_id: str = "bucket-a"
) -> None:
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period="1T",
        revision_id="2009-y-siguientes",
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        inputs_snapshot={"01": "1"},
        binding_overrides={},
        casilla_values={"01": Decimal("1")},
        source_transaction_ids=(transaction_id,),
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2026,
        period="1T",
        revision_id="2009-y-siguientes",
        name="303-2026-1T",
        created_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 2, 8, 0, tzinfo=UTC),
        current_calculation_revision_id=revision_id,
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        inputs_snapshot={"01": "1"},
        binding_overrides={},
        source_transaction_ids=(transaction_id,),
        casilla_values={"01": Decimal("1")},
        created_at=datetime(2026, 5, 2, 8, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 2, 9, 0, tzinfo=UTC),
        verified_at=datetime(2026, 5, 2, 9, 0, tzinfo=UTC),
        verified_by="operator-A",
    )
    WorkUnitCatalogueRepository(objects=objects).save(WorkUnitCatalogue.from_work_units((work_unit,)))
    CalculationRevisionCatalogueRepository(objects=objects).save(
        CalculationRevisionCatalogue(revisions={revision_id: revision})
    )


@dataclass(frozen=True, slots=True)
class _CreateManualOutcome:
    """Bundle returned by _drive_create_manual_transaction so the focused tests share setup.

    Captures every state slice the focused per-contract tests
    inspect: the create result, the reloaded persisted transaction,
    the loaded bucket events, and the purchase-invoice evidence id
    threaded through the command.
    """

    result: ManualLedgerTransactionResult
    persisted: Transaction
    events: tuple[BucketEvent, ...]
    purchase_invoice_evidence_id: str


def _drive_create_manual_transaction(secure_objects: SecureObjectRepository) -> _CreateManualOutcome:
    """Build + execute the canonical create_manual_transaction scenario.

    Shared by every test_create_manual_transaction_* in this
    section so each focused test runs against an identical state
    bundle without duplicating the 25-line command/evidence
    plumbing. Storage setup is paid per test (function-scoped
    ``secure_objects`` fixture); the trade-off favours diagnosability
    over throughput.
    """
    transaction_repository, event_repository = _repositories(secure_objects)
    invoice_repository = InvoiceCatalogueRepository(objects=secure_objects)
    purchase_evidence = _purchase_invoice()
    invoice_repository.save(InvoiceCatalogue.from_invoices((purchase_evidence,)))
    command = ManualLedgerTransactionCommand(
        bucket_id="bucket-a",
        booked_date=date(2026, 5, 2),
        value_date=date(2026, 5, 3),
        amount=Decimal("-121.00"),
        currency="EUR",
        direction=TransactionDirection.OUTGOING,
        counterparty="Proveedor SL",
        description="material oficina",
        business_classification=BusinessClassification.BUSINESS,
        category_id="office-supplies",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
        purchase_invoice_evidence_id=purchase_evidence.invoice_id,
        actor="operator-A",
        source_command="aeat app ledger add",
        idempotency_key="cash-2026-05-02-001",
    )
    result = create_manual_transaction(
        command,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    reloaded = transaction_repository.load()
    persisted = reloaded.get(result.ref.transaction_id)
    assert persisted is not None
    assert tuple(reloaded.transactions) == (result.ref.transaction_id,)
    events = event_repository.load().for_bucket("bucket-a")
    return _CreateManualOutcome(
        result=result,
        persisted=persisted,
        events=tuple(events),
        purchase_invoice_evidence_id=purchase_evidence.invoice_id,
    )


_PROVENANCE_RAW_FIELD_EXPECTATIONS = (
    ("source_kind", AggregationSourceKind.LEDGER_TRANSACTION.value),
    ("taxable_base", "100.00"),
)

_TAXABLE_IVA_EXPECTATIONS = (
    ("taxable_base", Decimal("100.00")),
    ("iva_rate", Decimal("0.21")),
    ("iva_amount", Decimal("21.00")),
)

_UPDATED_FIELD_EXPECTATIONS = (
    ("raw.description", "corrected description"),
    ("business_classification", BusinessClassification.MIXED),
    ("business_pct", Decimal("0.50")),
)

_PRESERVED_CREATE_AUDIT_FIELDS = ("created_by", "source_command", "created_event_id")

_POST_UPDATE_EVENT_PAYLOADS = (
    (1, "mutation_kind", "edit"),
    (2, "mutation_kind", "classification"),
    (3, "mutation_kind", "allocation"),
)
