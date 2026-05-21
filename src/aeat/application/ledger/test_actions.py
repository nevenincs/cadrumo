"""Tests for manual ledger transaction application services."""

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
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from ...adapters.persistence.storage import EphemeralMasterKeyProvider
from ...adapters.persistence.storage.attachment import AttachmentStore
from ...adapters.persistence.storage.sql import SecureObjectRepository, create_engine_from_settings
from ...adapters.persistence.storage.sql._orm import Base
from ...adapters.persistence.storage.sql.engine import dispose_engine
from ...application.export import ExportSerializationFormat
from ...core.config import Settings
from ...domain.attachments import Attachment, AttachmentKind, AttachmentSource
from ...domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
)
from ...domain.categories import SpendingCategory
from ...domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    InvoiceKind,
    InvoiceLine,
    IvaRate,
    PaymentStatus,
)
from ...domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ...domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ...domain.modelos._codes import ModeloCode
from ...domain.modelos._repository import WorkUnitCatalogueRepository
from ...domain.modelos._work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ...domain.transactions import (
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
from ...domain.usage_ratios import UsageRatioProfile
from . import (
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
    stash_manual_transaction,
    summarize_manual_transactions,
    update_manual_transaction,
    update_manual_transaction_fields,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def secure_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    database_url = f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}"
    monkeypatch.setenv("AEAT_DATABASE_URL", database_url)
    dispose_engine()
    provider = EphemeralMasterKeyProvider()
    with provider:
        engine = create_engine_from_settings(Settings(aeat_database_url=database_url))
        Base.metadata.create_all(engine)
        try:
            yield engine
        finally:
            engine.dispose()
            dispose_engine()


def _repositories(engine: Engine, *, bucket_id: str = "bucket-a"):
    objects = SecureObjectRepository(engine=engine)
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


def _persist_verified_revision_citing_transaction(engine: Engine, *, transaction_id: str, bucket_id: str = "bucket-a"):
    objects = SecureObjectRepository(engine=engine)
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


def _drive_create_manual_transaction(secure_engine: Engine) -> _CreateManualOutcome:
    """Build + execute the canonical create_manual_transaction scenario.

    Shared by every test_create_manual_transaction_* in this
    section so each focused test runs against an identical state
    bundle without duplicating the 25-line command/evidence
    plumbing. Engine setup is paid per test (function-scoped
    ``secure_engine`` fixture) — the trade-off favours diagnosability
    over throughput.
    """
    transaction_repository, event_repository = _repositories(secure_engine)
    invoice_repository = InvoiceCatalogueRepository(objects=SecureObjectRepository(engine=secure_engine))
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


def test_create_manual_transaction_returns_bucket_ref(secure_engine: Engine) -> None:
    outcome = _drive_create_manual_transaction(secure_engine)
    assert outcome.result.ref.bucket_id == "bucket-a"


_PROVENANCE_RAW_FIELD_EXPECTATIONS = (
    ("source_kind", "ledger_transaction"),
    ("taxable_base", "100.00"),
)


def test_create_manual_transaction_persists_source_provenance(secure_engine: Engine) -> None:
    outcome = _drive_create_manual_transaction(secure_engine)
    assert outcome.persisted.raw.provenance.source_format is SourceFormat.MANUAL
    assert outcome.persisted.raw.provenance.provider_name == "manual-ledger"


@pytest.mark.parametrize(("field", "expected"), _PROVENANCE_RAW_FIELD_EXPECTATIONS)
def test_create_manual_transaction_persists_raw_field(secure_engine: Engine, field: str, expected: str) -> None:
    outcome = _drive_create_manual_transaction(secure_engine)
    assert outcome.persisted.raw.raw_fields[field] == expected


def test_create_manual_transaction_persists_purchase_invoice_evidence_in_raw_fields(secure_engine: Engine) -> None:
    outcome = _drive_create_manual_transaction(secure_engine)
    assert (
        outcome.persisted.raw.raw_fields["purchase_invoice_evidence_id"] == outcome.purchase_invoice_evidence_id
    )


_TAXABLE_IVA_EXPECTATIONS = (
    ("taxable_base", Decimal("100.00")),
    ("iva_rate", Decimal("0.21")),
    ("iva_amount", Decimal("21.00")),
)


@pytest.mark.parametrize(("attribute", "expected"), _TAXABLE_IVA_EXPECTATIONS)
def test_create_manual_transaction_persists_taxable_iva(
    secure_engine: Engine, attribute: str, expected: Decimal
) -> None:
    outcome = _drive_create_manual_transaction(secure_engine)
    assert getattr(outcome.persisted, attribute) == expected


def test_create_manual_transaction_links_purchase_invoice_evidence(secure_engine: Engine) -> None:
    outcome = _drive_create_manual_transaction(secure_engine)
    assert outcome.persisted.purchase_invoice_evidence_id == outcome.purchase_invoice_evidence_id


def test_create_manual_transaction_records_audit_actor_and_command(secure_engine: Engine) -> None:
    outcome = _drive_create_manual_transaction(secure_engine)
    assert outcome.persisted.created_by == "operator-A"
    assert outcome.persisted.source_command == "aeat app ledger add"
    assert outcome.persisted.created_event_id == outcome.result.bucket_event_ids[0]


def test_create_manual_transaction_persists_evidence_provenance(secure_engine: Engine) -> None:
    outcome = _drive_create_manual_transaction(secure_engine)
    provenance = outcome.persisted.evidence_provenance[0]
    assert provenance.evidence_id == outcome.purchase_invoice_evidence_id
    assert provenance.evidence_kind == "purchase_invoice_evidence"
    assert provenance.actor == "operator-A"
    assert provenance.bucket_event_id == outcome.result.bucket_event_ids[0]


def test_create_manual_transaction_classifies_as_business(secure_engine: Engine) -> None:
    outcome = _drive_create_manual_transaction(secure_engine)
    assert outcome.persisted.business_classification is BusinessClassification.BUSINESS
    assert outcome.persisted.classified_by == "manual"


def test_create_manual_transaction_emits_bucket_event_chain(secure_engine: Engine) -> None:
    outcome = _drive_create_manual_transaction(secure_engine)
    assert [event.event_id for event in outcome.events] == list(outcome.result.bucket_event_ids)
    first = outcome.events[0]
    assert first.event_type is BucketEventType.LEDGER_TRANSACTION_CREATED
    assert first.object_type is BucketEventObjectType.LEDGER_TRANSACTION
    assert first.object_id == outcome.result.ref.transaction_id
    assert first.payload["source_command"] == "aeat app ledger add"


def test_create_manual_transaction_validates_and_persists_usage_ratio_reference(
    secure_engine: Engine,
) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    category = SpendingCategory.TELEFONIA_MOVIL
    profile = UsageRatioProfile(ratios={category: Decimal("0.60")})

    result = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 2),
            amount=Decimal("-50.00"),
            direction=TransactionDirection.OUTGOING,
            description="telefono movil",
            business_classification=BusinessClassification.MIXED,
            business_pct=Decimal("0.60"),
            category_id=category.value,
            usage_ratio_id=category.value,
            idempotency_key="phone-usage-ratio",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        usage_ratio_profile=profile,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )

    persisted = transaction_repository.load().get(result.ref.transaction_id)
    assert persisted is not None
    assert persisted.usage_ratio_id == category.value
    assert persisted.business_pct == Decimal("0.60")
    assert persisted.raw.raw_fields["usage_ratio_id"] == category.value
    events = event_repository.load().for_bucket("bucket-a")
    assert events[0].payload["usage_ratio_id"] == category.value
    assert events[0].payload["business_pct"] == "0.60"


def test_import_ledger_transactions_persists_rows_and_emits_import_events(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    first_raw = _raw_import_transaction()
    # A genuinely distinct movement: import dedup keys on the movement
    # identity (date + amount + normalised narrative), so the second
    # row must differ in one of those — not merely in the provider id.
    second_raw = _raw_import_transaction(
        transaction_id="provider-row-2",
        amount=Decimal("-48.40"),
        description="second provider import row",
    )

    first_import = import_ledger_transactions(
        bucket_id="bucket-a",
        raw_transactions=(first_raw, second_raw),
        direction_resolver=lambda _: TransactionDirection.OUTGOING,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        actor="operator-A",
        source_command="aeat app ledger import",
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    duplicate_import = import_ledger_transactions(
        bucket_id="bucket-a",
        raw_transactions=(first_raw,),
        direction_resolver=lambda _: TransactionDirection.OUTGOING,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        actor="operator-A",
        source_command="aeat app ledger import",
        occurred_at=datetime(2026, 5, 4, 9, 31, tzinfo=UTC),
    )

    assert first_import.summary.imported == 2
    assert first_import.summary.skipped == 0
    assert len(first_import.bucket_event_ids) == 2
    assert duplicate_import.summary.imported == 0
    assert duplicate_import.summary.skipped == 1
    assert duplicate_import.bucket_event_ids == ()
    persisted = transaction_repository.load()
    assert tuple(sorted(persisted.transactions)) == tuple(
        sorted(ref.transaction_id for ref in first_import.summary.imported_refs)
    )
    events = event_repository.load().for_bucket("bucket-a")
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_IMPORTED,
        BucketEventType.LEDGER_TRANSACTION_IMPORTED,
    ]
    assert {event.object_id for event in events} == {ref.transaction_id for ref in first_import.summary.imported_refs}
    assert all(event.object_type is BucketEventObjectType.LEDGER_TRANSACTION for event in events)
    assert {event.payload["source_row_index"] for event in events} == {"1"}
    assert {event.payload["provider_name"] for event in events} == {"CSV provider"}


def test_import_ledger_source_owns_provider_validation_ingest_and_persistence(
    secure_engine: Engine,
    tmp_path: Path,
) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    statement = tmp_path / "bank.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n"
        "2026-04-16,SaaS Vendor,Subscription,-48.40,EUR,n26-002\n",
        encoding="utf-8",
    )

    dry_run = import_ledger_source(
        LedgerSourceImportCommand(path=statement, provider="csv", dry_run=True, verify=True, source=statement),
    )
    persisted = import_ledger_source(
        LedgerSourceImportCommand(bucket_id="bucket-a", path=statement, provider="csv", actor="operator-A"),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )

    assert dry_run.dry_run is True
    assert dry_run.rows == 2
    # A dry run previews the real outcome: against an empty catalogue
    # both parsed rows would be imported. A flat zero was the defect.
    assert dry_run.imported == 2
    assert dry_run.skipped == 0
    assert dry_run.source.sha256 is not None
    assert persisted.bucket_id == "bucket-a"
    assert persisted.imported == 2
    assert persisted.skipped == 0
    assert persisted.import_batch_id is not None
    assert dry_run.diagnostics
    assert len(persisted.imported_transaction_refs) == 2
    assert len(persisted.bucket_event_ids) == 2
    assert len(transaction_repository.load().transactions) == 2


def test_import_ledger_source_missing_file_raises_localised_error(tmp_path: Path) -> None:
    """A missing source file raises a tr()-localised error, not naked English.

    Regression guard for the CLI persona testimonial finding: the ledger
    import error must carry the ``translated_message`` tr-key and render
    in the operator's locale (Spanish by default), not a hardcoded
    English sentence.
    """
    from ...core.errors import resolve_error_message

    missing = tmp_path / "no-such-statement.csv"
    with pytest.raises(TransactionValidationError) as excinfo:
        import_ledger_source(
            LedgerSourceImportCommand(
                path=missing, provider="csv", dry_run=True, verify=False, source=missing
            ),
        )

    error = excinfo.value
    assert error.translated_message == "errors.financial.source_file_not_found"
    assert error.context == {"path": str(missing)}
    rendered = resolve_error_message(error)
    assert "El archivo de origen no existe" in rendered
    assert str(missing) in rendered


def test_export_ledger_transactions_serializes_active_bucket_rows_and_emits_event(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    first = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 2),
            amount=Decimal("-121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            business_classification=BusinessClassification.BUSINESS,
            category_id="office-supplies",
            taxable_base=Decimal("100.00"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("21.00"),
            idempotency_key="export-first",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    second = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("250.00"),
            direction=TransactionDirection.INCOMING,
            description="client payment",
            business_classification=BusinessClassification.BUSINESS,
            idempotency_key="export-second",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 31, tzinfo=UTC),
    )

    result = export_ledger_transactions(
        LedgerExportCommand(
            bucket_id="bucket-a",
            export_format=ExportSerializationFormat.CSV,
            actor="operator-A",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    parsed = tuple(csv.DictReader(StringIO(result.payload.decode("utf-8"))))
    assert result.row_count == 2
    assert result.media_type == "text/csv"
    assert result.byte_size == len(result.payload)
    assert len(result.sha256) == 64
    assert [row["transaction_id"] for row in parsed] == [second.ref.transaction_id, first.ref.transaction_id]
    assert parsed[1]["taxable_base"] == "100.00"
    assert parsed[1]["purchase_invoice_evidence_id"] == ""
    assert transaction_repository.load().get(first.ref.transaction_id) is not None
    events = event_repository.load().for_bucket("bucket-a")
    assert events[-1].event_type is BucketEventType.LEDGER_TRANSACTION_EXPORTED
    assert events[-1].object_type is BucketEventObjectType.LEDGER_EXPORT
    assert events[-1].object_id == result.export_id
    assert events[-1].payload["row_count"] == "2"
    assert events[-1].payload["sha256"] == result.sha256
    assert events[-1].payload["first_transaction_id"] == second.ref.transaction_id
    assert events[-1].payload["last_transaction_id"] == first.ref.transaction_id
    assert len(events[-1].payload["transaction_ids_sha256"]) == 64


def test_export_ledger_transactions_excludes_inactive_rows_by_default(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    active = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("250.00"),
            direction=TransactionDirection.INCOMING,
            description="client payment",
            idempotency_key="export-active",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    inactive = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 2),
            amount=Decimal("-25.00"),
            direction=TransactionDirection.OUTGOING,
            description="stashed payment",
            idempotency_key="export-inactive",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 31, tzinfo=UTC),
    )
    stash_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=inactive.ref.transaction_id,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 9, 0, tzinfo=UTC),
    )

    active_only = export_ledger_transactions(
        LedgerExportCommand(bucket_id="bucket-a"),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )
    with_inactive = export_ledger_transactions(
        LedgerExportCommand(bucket_id="bucket-a", include_inactive=True),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 10, 1, tzinfo=UTC),
    )

    assert tuple(row.transaction_id for row in active_only.rows) == (active.ref.transaction_id,)
    assert tuple(row.transaction_id for row in with_inactive.rows) == (
        active.ref.transaction_id,
        inactive.ref.transaction_id,
    )
    assert with_inactive.rows[1].lifecycle_state == "STASHED"


def test_export_ledger_transactions_event_payload_stays_bounded_for_large_exports(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    for index in range(12):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, index + 1),
                amount=Decimal("-25.00"),
                direction=TransactionDirection.OUTGOING,
                description=f"export row {index:02d}",
                idempotency_key=f"export-bulk-{index:02d}",
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    result = export_ledger_transactions(
        LedgerExportCommand(bucket_id="bucket-a"),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    assert result.row_count == 12
    event = event_repository.load().for_bucket("bucket-a")[-1]
    assert event.event_type is BucketEventType.LEDGER_TRANSACTION_EXPORTED
    assert "transaction_ids" not in event.payload
    assert event.payload["row_count"] == "12"
    assert len(event.payload["transaction_ids_sha256"]) == 64
    assert all(len(value) <= 500 for value in event.payload.values())


def test_export_ledger_transactions_reads_requested_bucket_only(secure_engine: Engine) -> None:
    repo_a, event_repo_a = _repositories(secure_engine, bucket_id="bucket-a")
    repo_b, event_repo_b = _repositories(secure_engine, bucket_id="bucket-b")
    first = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-25.00"),
            direction=TransactionDirection.OUTGOING,
            description="bucket a row",
            idempotency_key="shared-key",
        ),
        transaction_repository=repo_a,
        bucket_event_repository=event_repo_a,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-b",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-25.00"),
            direction=TransactionDirection.OUTGOING,
            description="bucket b row",
            idempotency_key="shared-key",
        ),
        transaction_repository=repo_b,
        bucket_event_repository=event_repo_b,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )

    result = export_ledger_transactions(
        LedgerExportCommand(bucket_id="bucket-a", export_format=ExportSerializationFormat.JSONL),
        transaction_repository=repo_a,
        bucket_event_repository=event_repo_a,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    assert result.row_count == 1
    assert result.rows[0].bucket_id == "bucket-a"
    assert result.rows[0].transaction_id == first.ref.transaction_id
    assert b"bucket b row" not in result.payload
    assert [event.event_type for event in event_repo_b.load().for_bucket("bucket-b")] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED
    ]


def test_export_ledger_transactions_writes_output_before_export_event(
    secure_engine: Engine,
    tmp_path: Path,
) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-25.00"),
            direction=TransactionDirection.OUTGOING,
            description="export row",
            idempotency_key="export-output-before-event",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    with pytest.raises(OSError):
        export_ledger_transactions(
            LedgerExportCommand(bucket_id="bucket-a", output_path=tmp_path),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 2, 9, 0, tzinfo=UTC),
        )

    assert [event.event_type for event in event_repository.load().for_bucket("bucket-a")] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED
    ]


def test_create_manual_transaction_rejects_usage_ratio_reference_missing_from_profile(
    secure_engine: Engine,
) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    category = SpendingCategory.TELEFONIA_MOVIL

    with pytest.raises(TransactionValidationError, match="not configured"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 2),
                amount=Decimal("-50.00"),
                direction=TransactionDirection.OUTGOING,
                description="telefono movil",
                business_classification=BusinessClassification.MIXED,
                business_pct=Decimal("0.60"),
                category_id=category.value,
                usage_ratio_id=category.value,
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            usage_ratio_profile=UsageRatioProfile(),
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    assert transaction_repository.load().transactions == {}
    assert event_repository.load().events == {}


def test_create_manual_transaction_rejects_usage_ratio_alias_and_category_mismatch(
    secure_engine: Engine,
) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    category = SpendingCategory.TELEFONIA_MOVIL
    profile = UsageRatioProfile(ratios={category: Decimal("0.60")})

    with pytest.raises(TransactionValidationError, match="concrete eligible spending category"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 2),
                amount=Decimal("-50.00"),
                direction=TransactionDirection.OUTGOING,
                description="telefono movil",
                business_classification=BusinessClassification.MIXED,
                business_pct=Decimal("0.60"),
                category_id=category.value,
                usage_ratio_id="home_office_area",
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            usage_ratio_profile=profile,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    with pytest.raises(TransactionValidationError, match="must match"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 2),
                amount=Decimal("-50.00"),
                direction=TransactionDirection.OUTGOING,
                description="telefono movil",
                business_classification=BusinessClassification.MIXED,
                business_pct=Decimal("0.60"),
                category_id=SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ.value,
                usage_ratio_id=category.value,
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            usage_ratio_profile=profile,
            occurred_at=datetime(2026, 5, 4, 9, 31, tzinfo=UTC),
        )

    assert transaction_repository.load().transactions == {}
    assert event_repository.load().events == {}


def test_create_manual_transaction_rejects_usage_ratio_business_pct_drift(
    secure_engine: Engine,
) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    category = SpendingCategory.TELEFONIA_MOVIL
    profile = UsageRatioProfile(ratios={category: Decimal("0.60")})

    with pytest.raises(TransactionValidationError, match="does not match"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 2),
                amount=Decimal("-50.00"),
                direction=TransactionDirection.OUTGOING,
                description="telefono movil",
                business_classification=BusinessClassification.MIXED,
                business_pct=Decimal("0.50"),
                category_id=category.value,
                usage_ratio_id=category.value,
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            usage_ratio_profile=profile,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    assert transaction_repository.load().transactions == {}
    assert event_repository.load().events == {}


def test_list_and_get_manual_transactions_read_the_requested_bucket_only(secure_engine: Engine) -> None:
    repo_a, event_repo = _repositories(secure_engine, bucket_id="bucket-a")
    repo_b, event_repo_b = _repositories(secure_engine, bucket_id="bucket-b")
    first = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-25.00"),
            direction=TransactionDirection.OUTGOING,
            description="first bucket row",
            idempotency_key="first",
        ),
        transaction_repository=repo_a,
        bucket_event_repository=event_repo,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-b",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-25.00"),
            direction=TransactionDirection.OUTGOING,
            description="other bucket row",
            idempotency_key="first",
        ),
        transaction_repository=repo_b,
        bucket_event_repository=event_repo_b,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    listed = list_manual_transactions(bucket_id="bucket-a", transaction_repository=repo_a)
    fetched = get_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=first.ref.transaction_id,
        transaction_repository=repo_a,
    )

    assert [item.ref.transaction_id for item in listed] == [first.ref.transaction_id]
    assert fetched.transaction.raw.description == "first bucket row"
    with pytest.raises(TransactionNotFoundError):
        get_manual_transaction(
            bucket_id="bucket-a",
            transaction_id="0" * 64,
            transaction_repository=repo_a,
        )


def test_summarize_manual_transactions_reports_bucket_status_and_readiness(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine, bucket_id="bucket-a")
    ready = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-121.00"),
            direction=TransactionDirection.OUTGOING,
            description="ready row",
            business_classification=BusinessClassification.BUSINESS,
            category_id="office-supplies",
            taxable_base=Decimal("100.00"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("21.00"),
            idempotency_key="ready-status",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    pending = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 2),
            amount=Decimal("-25.00"),
            direction=TransactionDirection.OUTGOING,
            description="pending row",
            idempotency_key="pending-status",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 8, 0, tzinfo=UTC),
    )
    stash_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=pending.ref.transaction_id,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 3, 8, 0, tzinfo=UTC),
    )

    report = summarize_manual_transactions(
        bucket_id="bucket-a",
        period="2026-05",
        transaction_repository=transaction_repository,
    )

    assert ledger_transaction_review_status(ready.transaction) == "reviewed"
    assert report.total_count == 2
    assert report.active_count == 1
    assert report.stashed_count == 1
    assert report.reviewed_count == 1
    assert report.pending_review_count == 0
    assert report.checked_transaction_count == 1
    assert report.readiness_issue_count == 0
    assert report.ready is True


def test_query_ledger_review_rows_filters_exact_period_and_projects_rows(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine, bucket_id="bucket-a")
    may = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-25.00"),
            direction=TransactionDirection.OUTGOING,
            description="may row",
            idempotency_key="review-may",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 6, 1),
            amount=Decimal("-25.00"),
            direction=TransactionDirection.OUTGOING,
            description="june row",
            idempotency_key="review-june",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 6, 1, 8, 0, tzinfo=UTC),
    )

    listed = query_ledger_review_rows(
        LedgerReviewQuery(bucket_id="bucket-a", period="2026-05", status="pending"),
        transaction_repository=transaction_repository,
    )
    single = query_ledger_review_rows(
        LedgerReviewQuery(bucket_id="bucket-a", transaction_id=may.ref.transaction_id),
        transaction_repository=transaction_repository,
    )
    single_filtered_out = query_ledger_review_rows(
        LedgerReviewQuery(bucket_id="bucket-a", period="2026-06", transaction_id=may.ref.transaction_id),
        transaction_repository=transaction_repository,
    )

    assert [row.description for row in listed.rows] == ["may row"]
    assert listed.filters == ("period=2026-05", "status=pending")
    assert single.rows[0].id == may.ref.transaction_id
    assert single.rows[0].transaction is not None
    assert single_filtered_out.rows == ()


def test_query_ledger_review_rows_filters_quarter_import_and_issue_events(
    secure_engine: Engine,
    tmp_path: Path,
) -> None:
    transaction_repository, event_repository = _repositories(secure_engine, bucket_id="bucket-a")
    statement = tmp_path / "bank.csv"
    statement.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-15,Client SL,Invoice 1,121.00,EUR,n26-001\n"
        "2026-06-16,SaaS Vendor,Subscription,-48.40,EUR,n26-002\n",
        encoding="utf-8",
    )

    first_import = import_ledger_source(
        LedgerSourceImportCommand(
            bucket_id="bucket-a",
            path=statement,
            provider="csv",
            verify=True,
            source=statement,
            actor="operator-A",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )
    duplicate_import = import_ledger_source(
        LedgerSourceImportCommand(
            bucket_id="bucket-a",
            path=statement,
            provider="csv",
            verify=True,
            actor="operator-A",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )

    assert first_import.import_batch_id is not None
    assert duplicate_import.import_batch_id is not None
    assert first_import.imported == 2
    assert duplicate_import.skipped == 2
    assert {diagnostic.kind for diagnostic in duplicate_import.diagnostics} == {"duplicate", "gap"}
    assert BucketEventType.LEDGER_IMPORT_DIAGNOSTIC_RECORDED in {
        event.event_type for event in event_repository.load().for_bucket("bucket-a")
    }

    quarter_rows = query_ledger_review_rows(
        LedgerReviewQuery(bucket_id="bucket-a", period="2026Q2"),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )
    imported_rows = query_ledger_review_rows(
        LedgerReviewQuery(bucket_id="bucket-a", import_id=first_import.import_batch_id),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )
    duplicate_rows = query_ledger_review_rows(
        LedgerReviewQuery(bucket_id="bucket-a", issue="duplicate", import_id=duplicate_import.import_batch_id),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )
    gap_rows = query_ledger_review_rows(
        LedgerReviewQuery(bucket_id="bucket-a", issue="gap", import_id=first_import.import_batch_id),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    )

    assert [row.description for row in quarter_rows.rows] == ["Invoice 1", "Subscription"]
    assert [row.description for row in imported_rows.rows] == ["Invoice 1", "Subscription"]
    assert [row.description for row in duplicate_rows.rows] == ["Invoice 1", "Subscription"]
    assert [row.description for row in gap_rows.rows] == ["Invoice 1", "Subscription"]
    assert duplicate_rows.filters == (
        "issue=duplicate",
        f"import={duplicate_import.import_batch_id}",
    )


@dataclass(frozen=True, slots=True)
class _UpdateManualOutcome:
    """Bundle returned by _drive_update_manual_transaction.

    Captures the create + update results, the post-update catalogue
    state, and the loaded bucket events for the focused tests to
    share without duplicating the two-command scenario.
    """

    created: ManualLedgerTransactionResult
    updated: ManualLedgerTransactionResult
    reloaded: TransactionCatalogue
    events: tuple[BucketEvent, ...]


def _drive_update_manual_transaction(secure_engine: Engine) -> _UpdateManualOutcome:
    """Run the canonical create -> update scenario and bundle the observable state."""
    transaction_repository, event_repository = _repositories(secure_engine)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-50.00"),
            direction=TransactionDirection.OUTGOING,
            description="draft description",
            idempotency_key="cash-row",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    updated = update_manual_transaction(
        transaction_id=created.ref.transaction_id,
        command=ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-60.00"),
            direction=TransactionDirection.OUTGOING,
            description="corrected description",
            business_classification=BusinessClassification.MIXED,
            business_pct=Decimal("0.50"),
            notes="corrected cash amount",
            actor="operator-B",
            source_command="aeat app ledger update",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )
    reloaded = transaction_repository.load()
    events = tuple(event_repository.load().for_bucket("bucket-a"))
    return _UpdateManualOutcome(created=created, updated=updated, reloaded=reloaded, events=events)


def test_update_manual_transaction_retires_previous_transaction_id_from_catalogue(
    secure_engine: Engine,
) -> None:
    outcome = _drive_update_manual_transaction(secure_engine)
    assert outcome.created.ref.transaction_id not in outcome.reloaded.transactions


def test_update_manual_transaction_persists_replacement_transaction_id(secure_engine: Engine) -> None:
    outcome = _drive_update_manual_transaction(secure_engine)
    assert outcome.updated.ref.transaction_id in outcome.reloaded.transactions


_UPDATED_FIELD_EXPECTATIONS = (
    ("raw.description", "corrected description"),
    ("business_classification", BusinessClassification.MIXED),
    ("business_pct", Decimal("0.50")),
    ("notes", "corrected cash amount"),
)


@pytest.mark.parametrize(("attr_path", "expected"), _UPDATED_FIELD_EXPECTATIONS)
def test_update_manual_transaction_replaces_field(
    secure_engine: Engine, attr_path: str, expected: object
) -> None:
    outcome = _drive_update_manual_transaction(secure_engine)
    actual: object = outcome.updated.transaction
    for segment in attr_path.split("."):
        actual = getattr(actual, segment)
    assert actual == expected


_PRESERVED_CREATE_AUDIT_FIELDS = ("created_by", "source_command", "created_event_id")


@pytest.mark.parametrize("attr", _PRESERVED_CREATE_AUDIT_FIELDS)
def test_update_manual_transaction_preserves_original_audit_field(secure_engine: Engine, attr: str) -> None:
    outcome = _drive_update_manual_transaction(secure_engine)
    assert getattr(outcome.updated.transaction, attr) == getattr(outcome.created.transaction, attr)


def test_update_manual_transaction_records_edit_lineage_entry(secure_engine: Engine) -> None:
    outcome = _drive_update_manual_transaction(secure_engine)
    entry = outcome.updated.transaction.edit_lineage[-1]
    assert entry.previous_transaction_id == outcome.created.ref.transaction_id
    assert entry.actor == "operator-B"
    assert entry.source_command == "aeat app ledger update"
    assert entry.bucket_event_id == outcome.updated.bucket_event_ids[0]


def test_update_manual_transaction_emits_expected_event_chain(secure_engine: Engine) -> None:
    outcome = _drive_update_manual_transaction(secure_engine)
    assert [event.event_type for event in outcome.events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_UPDATED,
        BucketEventType.LEDGER_TRANSACTION_CLASSIFIED,
        BucketEventType.LEDGER_TRANSACTION_ALLOCATED,
    ]


def test_update_manual_transaction_links_update_events_to_result(secure_engine: Engine) -> None:
    outcome = _drive_update_manual_transaction(secure_engine)
    assert [event.event_id for event in outcome.events[1:]] == list(outcome.updated.bucket_event_ids)


_POST_UPDATE_EVENT_PAYLOADS = (
    (1, "mutation_kind", "edit"),
    (2, "mutation_kind", "classification"),
    (3, "mutation_kind", "allocation"),
)


@pytest.mark.parametrize(("event_index", "payload_key", "expected"), _POST_UPDATE_EVENT_PAYLOADS)
def test_update_manual_transaction_event_payload_marks_mutation_kind(
    secure_engine: Engine, event_index: int, payload_key: str, expected: str
) -> None:
    outcome = _drive_update_manual_transaction(secure_engine)
    assert outcome.events[event_index].payload[payload_key] == expected


def test_update_manual_transaction_edit_event_references_previous_transaction(secure_engine: Engine) -> None:
    outcome = _drive_update_manual_transaction(secure_engine)
    assert outcome.events[1].payload["previous_transaction_id"] == outcome.created.ref.transaction_id


def test_update_manual_transaction_post_update_events_target_new_transaction_id(secure_engine: Engine) -> None:
    outcome = _drive_update_manual_transaction(secure_engine)
    assert {event.object_id for event in outcome.events[1:]} == {outcome.updated.ref.transaction_id}


def test_update_manual_transaction_fields_applies_typed_patch_through_backend(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-75.00"),
            direction=TransactionDirection.OUTGOING,
            description="pending row",
            idempotency_key="typed-patch",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    updated = update_manual_transaction_fields(
        bucket_id="bucket-a",
        transaction_id=created.ref.transaction_id,
        patch=ManualLedgerTransactionPatch(
            description="classified row",
            business_classification=BusinessClassification.BUSINESS,
            category_id="office-supplies",
            taxable_base=Decimal("60.00"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("12.60"),
        ),
        actor="operator-C",
        source_command="aeat app ledger classify",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    assert updated.transaction.raw.description == "classified row"
    assert updated.transaction.business_classification is BusinessClassification.BUSINESS
    assert updated.transaction.category_id == "office-supplies"
    assert updated.transaction.taxable_base == Decimal("60.00")
    assert updated.transaction.edit_lineage[-1].source_command == "aeat app ledger classify"
    events = event_repository.load().for_bucket("bucket-a")
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_UPDATED,
        BucketEventType.LEDGER_TRANSACTION_CLASSIFIED,
    ]


def test_update_manual_transaction_fields_clears_tax_facts_for_personal_reclassification(
    secure_engine: Engine,
) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-121.00"),
            direction=TransactionDirection.OUTGOING,
            description="office supplies",
            business_classification=BusinessClassification.BUSINESS,
            category_id="office-supplies",
            taxable_base=Decimal("100.00"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("21.00"),
            irpf_category="activity-expense",
            prorrata_reference="iva-prorrata-2026",
            idempotency_key="personal-reclassification",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    updated = update_manual_transaction_fields(
        bucket_id="bucket-a",
        transaction_id=created.ref.transaction_id,
        patch=ManualLedgerTransactionPatch(business_classification=BusinessClassification.PERSONAL),
        actor="operator-C",
        source_command="aeat app ledger classify",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    assert updated.transaction.business_classification is BusinessClassification.PERSONAL
    assert updated.transaction.business_pct is None
    assert updated.transaction.category_id is None
    assert updated.transaction.taxable_base is None
    assert updated.transaction.iva_rate is None
    assert updated.transaction.iva_amount is None
    assert updated.transaction.irpf_category is None
    assert updated.transaction.usage_ratio_id is None
    assert updated.transaction.prorrata_reference is None
    events = event_repository.load().for_bucket("bucket-a")
    assert [event.event_type for event in events[1:]] == [
        BucketEventType.LEDGER_TRANSACTION_UPDATED,
        BucketEventType.LEDGER_TRANSACTION_CLASSIFIED,
        BucketEventType.LEDGER_TRANSACTION_ALLOCATED,
    ]


def test_update_manual_transaction_emits_purchase_evidence_attachment_event(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    invoice_repository = InvoiceCatalogueRepository(objects=SecureObjectRepository(engine=secure_engine))
    purchase_evidence = _purchase_invoice()
    invoice_repository.save(InvoiceCatalogue.from_invoices((purchase_evidence,)))
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            idempotency_key="evidence-attach",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    updated = update_manual_transaction(
        transaction_id=created.ref.transaction_id,
        command=ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            purchase_invoice_evidence_id=purchase_evidence.invoice_id,
            actor="operator-B",
            source_command="aeat app ledger attach",
            idempotency_key="evidence-attach",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    assert updated.transaction.purchase_invoice_evidence_id == purchase_evidence.invoice_id
    assert updated.transaction.evidence_provenance[-1].evidence_id == purchase_evidence.invoice_id
    assert updated.transaction.evidence_provenance[-1].bucket_event_id == updated.bucket_event_ids[0]
    events = event_repository.load().for_bucket("bucket-a")
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED,
    ]
    assert events[-1].object_type is BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE
    assert events[-1].object_id == purchase_evidence.invoice_id
    assert events[-1].payload["transaction_id"] == updated.ref.transaction_id
    assert events[-1].payload["mutation_kind"] == "purchase_invoice_evidence_attached"


def test_attach_manual_transaction_evidence_delegates_to_validated_backend_patch(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    invoice_repository = InvoiceCatalogueRepository(objects=SecureObjectRepository(engine=secure_engine))
    purchase_evidence = _purchase_invoice()
    invoice_repository.save(InvoiceCatalogue.from_invoices((purchase_evidence,)))
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            idempotency_key="evidence-helper-attach",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    attached = attach_manual_transaction_evidence(
        bucket_id="bucket-a",
        transaction_id=created.ref.transaction_id,
        purchase_invoice_evidence_id=purchase_evidence.invoice_id,
        actor="operator-B",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    assert attached.transaction.purchase_invoice_evidence_id == purchase_evidence.invoice_id
    assert attached.transaction.evidence_provenance[-1].evidence_kind == "purchase_invoice_evidence"
    events = event_repository.load().for_bucket("bucket-a")
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED,
    ]


def test_update_manual_transaction_mixed_edit_and_evidence_lineage_uses_evidence_event(
    secure_engine: Engine,
) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    invoice_repository = InvoiceCatalogueRepository(objects=SecureObjectRepository(engine=secure_engine))
    purchase_evidence = _purchase_invoice()
    invoice_repository.save(InvoiceCatalogue.from_invoices((purchase_evidence,)))
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            idempotency_key="mixed-evidence-attach",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    updated = update_manual_transaction(
        transaction_id=created.ref.transaction_id,
        command=ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina corrected",
            business_classification=BusinessClassification.BUSINESS,
            category_id="office-supplies",
            purchase_invoice_evidence_id=purchase_evidence.invoice_id,
            actor="operator-B",
            source_command="aeat app ledger attach",
            idempotency_key="mixed-evidence-attach",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    events = event_repository.load().for_bucket("bucket-a")
    attach_event = next(
        event for event in events if event.event_type is BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED
    )
    assert updated.transaction.edit_lineage[-1].bucket_event_id != attach_event.event_id
    assert updated.transaction.evidence_provenance[-1].bucket_event_id == attach_event.event_id


def test_archive_manual_transaction_records_lifecycle_lineage_and_event(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-50.00"),
            direction=TransactionDirection.OUTGOING,
            description="wrong account import",
            idempotency_key="archive-row",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    archived = archive_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        reason="wrong account import",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    persisted = transaction_repository.load().get(created.ref.transaction_id)
    assert persisted is not None
    assert persisted.lifecycle_state is TransactionLifecycleState.ARCHIVED
    assert persisted.lifecycle_lineage[-1].previous_state is TransactionLifecycleState.ACTIVE
    assert persisted.lifecycle_lineage[-1].state is TransactionLifecycleState.ARCHIVED
    assert persisted.lifecycle_lineage[-1].reason == "wrong account import"
    assert persisted.lifecycle_lineage[-1].bucket_event_id == archived.bucket_event_ids[0]
    events = event_repository.load().for_bucket("bucket-a")
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_ARCHIVED,
    ]
    assert events[-1].payload["previous_lifecycle_state"] == "ACTIVE"
    assert events[-1].payload["lifecycle_state"] == "ARCHIVED"
    assert events[-1].payload["reason"] == "wrong account import"


def test_update_manual_transaction_rejects_archived_row_without_reactivating_it(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-50.00"),
            direction=TransactionDirection.OUTGOING,
            description="wrong account import",
            idempotency_key="archived-edit-refusal",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    archived = archive_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        reason="wrong account import",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    with pytest.raises(TransactionValidationError, match="can be edited"):
        update_manual_transaction(
            transaction_id=created.ref.transaction_id,
            command=ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 1),
                amount=Decimal("-60.00"),
                direction=TransactionDirection.OUTGOING,
                description="attempt to edit archived row",
                actor="operator-B",
                source_command="aeat app ledger update",
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 3, 10, 0, tzinfo=UTC),
        )

    persisted = transaction_repository.load().get(created.ref.transaction_id)
    assert persisted is not None
    assert persisted.lifecycle_state is TransactionLifecycleState.ARCHIVED
    assert persisted.lifecycle_lineage[-1].bucket_event_id == archived.bucket_event_ids[0]
    assert [event.event_type for event in event_repository.load().for_bucket("bucket-a")] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_ARCHIVED,
    ]


def test_stash_manual_transaction_records_lifecycle_lineage_and_event(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-50.00"),
            direction=TransactionDirection.OUTGOING,
            description="hold for later classification",
            idempotency_key="stash-row",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    stashed = stash_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        reason="needs supporting statement",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    persisted = transaction_repository.load().get(created.ref.transaction_id)
    assert persisted is not None
    assert persisted.lifecycle_state is TransactionLifecycleState.STASHED
    assert persisted.lifecycle_lineage[-1].state is TransactionLifecycleState.STASHED
    assert persisted.lifecycle_lineage[-1].bucket_event_id == stashed.bucket_event_ids[0]
    events = event_repository.load().for_bucket("bucket-a")
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_STASHED,
    ]
    assert events[-1].payload["lifecycle_state"] == "STASHED"


def test_archive_and_stash_refuse_invalid_lifecycle_transitions(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-50.00"),
            direction=TransactionDirection.OUTGOING,
            description="wrong account import",
            idempotency_key="archive-stash-refusal",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    archive_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
    )

    with pytest.raises(TransactionValidationError, match="already archived"):
        archive_manual_transaction(
            bucket_id="bucket-a",
            transaction_id=created.ref.transaction_id,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 3, 10, 0, tzinfo=UTC),
        )
    with pytest.raises(TransactionValidationError, match="cannot be stashed"):
        stash_manual_transaction(
            bucket_id="bucket-a",
            transaction_id=created.ref.transaction_id,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 3, 10, 0, tzinfo=UTC),
        )

    assert [event.event_type for event in event_repository.load().for_bucket("bucket-a")] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_ARCHIVED,
    ]


def test_remove_manual_transaction_deletes_row_detaches_purchase_evidence_and_emits_events(
    secure_engine: Engine,
) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    invoice_repository = InvoiceCatalogueRepository(objects=SecureObjectRepository(engine=secure_engine))
    purchase_evidence = _purchase_invoice()
    invoice_repository.save(InvoiceCatalogue.from_invoices((purchase_evidence,)))
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 2),
            amount=Decimal("-121.00"),
            direction=TransactionDirection.OUTGOING,
            description="material oficina",
            business_classification=BusinessClassification.BUSINESS,
            category_id="office-supplies",
            purchase_invoice_evidence_id=purchase_evidence.invoice_id,
            idempotency_key="remove-linked-row",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    invoice_repository.save(
        InvoiceCatalogue.from_invoices(
            (purchase_evidence.model_copy(update={"linked_transaction_ids": (created.ref.transaction_id,)}),)
        )
    )

    removed = remove_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        reason="wrong account import",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    assert removed.removed is True
    assert removed.cascaded_purchase_invoice_evidence_ids == (purchase_evidence.invoice_id,)
    assert transaction_repository.load().transactions == {}
    detached = invoice_repository.load().get(purchase_evidence.invoice_id)
    assert detached is not None
    assert detached.linked_transaction_ids == ()
    events = event_repository.load().for_bucket("bucket-a")
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED,
        BucketEventType.LEDGER_TRANSACTION_REMOVED,
    ]
    assert events[-1].payload["purchase_invoice_evidence_ids"] == purchase_evidence.invoice_id
    assert events[-1].payload["reason"] == "wrong account import"


def test_remove_manual_transaction_dry_run_reports_without_mutation(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 2),
            amount=Decimal("-25.00"),
            direction=TransactionDirection.OUTGOING,
            description="dry run row",
            idempotency_key="remove-dry-run",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )

    report = remove_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        dry_run=True,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    assert report.dry_run is True
    assert report.removed is False
    assert transaction_repository.load().get(created.ref.transaction_id) is not None
    assert [event.event_type for event in event_repository.load().for_bucket("bucket-a")] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED
    ]


def test_remove_manual_transaction_refuses_finalized_modelo_reference(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 2),
            amount=Decimal("-25.00"),
            direction=TransactionDirection.OUTGOING,
            description="modelo source row",
            idempotency_key="remove-blocked",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    _persist_verified_revision_citing_transaction(secure_engine, transaction_id=created.ref.transaction_id)

    dry_run = remove_manual_transaction(
        bucket_id="bucket-a",
        transaction_id=created.ref.transaction_id,
        actor="operator-A",
        dry_run=True,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        work_unit_repository=WorkUnitCatalogueRepository(objects=SecureObjectRepository(engine=secure_engine)),
        calculation_repository=CalculationRevisionCatalogueRepository(
            objects=SecureObjectRepository(engine=secure_engine)
        ),
    )

    assert dry_run.blocking_modelo_references[0].modelo == "303"
    with pytest.raises(TransactionValidationError, match="finalized modelo"):
        remove_manual_transaction(
            bucket_id="bucket-a",
            transaction_id=created.ref.transaction_id,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            work_unit_repository=WorkUnitCatalogueRepository(objects=SecureObjectRepository(engine=secure_engine)),
            calculation_repository=CalculationRevisionCatalogueRepository(
                objects=SecureObjectRepository(engine=secure_engine)
            ),
        )
    assert transaction_repository.load().get(created.ref.transaction_id) is not None


def test_update_manual_transaction_refuses_finalized_modelo_reference(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 2),
            amount=Decimal("-25.00"),
            direction=TransactionDirection.OUTGOING,
            description="modelo source row",
            idempotency_key="update-blocked",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    _persist_verified_revision_citing_transaction(secure_engine, transaction_id=created.ref.transaction_id)

    with pytest.raises(TransactionValidationError, match="finalized modelo"):
        update_manual_transaction(
            transaction_id=created.ref.transaction_id,
            command=ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 2),
                amount=Decimal("-35.00"),
                direction=TransactionDirection.OUTGOING,
                description="mutated modelo source row",
                idempotency_key="update-blocked",
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            work_unit_repository=WorkUnitCatalogueRepository(objects=SecureObjectRepository(engine=secure_engine)),
            calculation_repository=CalculationRevisionCatalogueRepository(
                objects=SecureObjectRepository(engine=secure_engine)
            ),
            occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
        )

    assert tuple(transaction_repository.load().transactions) == (created.ref.transaction_id,)
    assert [event.event_type for event in event_repository.load().for_bucket("bucket-a")] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED
    ]


def test_lifecycle_change_refuses_finalized_modelo_reference(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 2),
            amount=Decimal("-25.00"),
            direction=TransactionDirection.OUTGOING,
            description="modelo source row",
            idempotency_key="lifecycle-blocked",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    _persist_verified_revision_citing_transaction(secure_engine, transaction_id=created.ref.transaction_id)

    with pytest.raises(TransactionValidationError, match="finalized modelo"):
        archive_manual_transaction(
            bucket_id="bucket-a",
            transaction_id=created.ref.transaction_id,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            work_unit_repository=WorkUnitCatalogueRepository(objects=SecureObjectRepository(engine=secure_engine)),
            calculation_repository=CalculationRevisionCatalogueRepository(
                objects=SecureObjectRepository(engine=secure_engine)
            ),
            occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
        )

    persisted = transaction_repository.load().get(created.ref.transaction_id)
    assert persisted is not None
    assert persisted.lifecycle_state is TransactionLifecycleState.ACTIVE
    assert [event.event_type for event in event_repository.load().for_bucket("bucket-a")] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED
    ]


def test_remove_manual_transaction_refuses_finalized_reference_to_prior_edit_id(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 2),
            amount=Decimal("-25.00"),
            direction=TransactionDirection.OUTGOING,
            description="modelo source row",
            idempotency_key="prior-id",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    updated = update_manual_transaction(
        transaction_id=created.ref.transaction_id,
        command=ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 2),
            amount=Decimal("-35.00"),
            direction=TransactionDirection.OUTGOING,
            description="modelo source row corrected",
            idempotency_key="prior-id",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )
    _persist_verified_revision_citing_transaction(secure_engine, transaction_id=created.ref.transaction_id)

    with pytest.raises(TransactionValidationError, match="finalized modelo"):
        remove_manual_transaction(
            bucket_id="bucket-a",
            transaction_id=updated.ref.transaction_id,
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            work_unit_repository=WorkUnitCatalogueRepository(objects=SecureObjectRepository(engine=secure_engine)),
            calculation_repository=CalculationRevisionCatalogueRepository(
                objects=SecureObjectRepository(engine=secure_engine)
            ),
        )

    assert transaction_repository.load().get(updated.ref.transaction_id) is not None


def test_reset_ledger_catalogue_clears_bucket_when_unblocked_and_emits_event(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    invoice_repository = InvoiceCatalogueRepository(objects=SecureObjectRepository(engine=secure_engine))
    purchase_evidence = _purchase_invoice()
    invoice_repository.save(InvoiceCatalogue.from_invoices((purchase_evidence,)))
    first = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 2),
            amount=Decimal("-25.00"),
            direction=TransactionDirection.OUTGOING,
            description="first reset row",
            purchase_invoice_evidence_id=purchase_evidence.invoice_id,
            idempotency_key="reset-first",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    second = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 3),
            amount=Decimal("-30.00"),
            direction=TransactionDirection.OUTGOING,
            description="second reset row",
            idempotency_key="reset-second",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 31, tzinfo=UTC),
    )
    invoice_repository.save(
        InvoiceCatalogue.from_invoices(
            (purchase_evidence.model_copy(update={"linked_transaction_ids": (first.ref.transaction_id,)}),)
        )
    )

    report = reset_ledger_catalogue(
        bucket_id="bucket-a",
        actor="operator-A",
        reason="contaminated import batch",
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        invoice_repository=invoice_repository,
        occurred_at=datetime(2026, 5, 5, 10, 0, tzinfo=UTC),
    )

    assert report.reset is True
    assert report.removed_transaction_ids == tuple(sorted((first.ref.transaction_id, second.ref.transaction_id)))
    assert report.cascaded_purchase_invoice_evidence_ids == (purchase_evidence.invoice_id,)
    assert transaction_repository.load().transactions == {}
    detached = invoice_repository.load().get(purchase_evidence.invoice_id)
    assert detached is not None
    assert detached.linked_transaction_ids == ()
    events = event_repository.load().for_bucket("bucket-a")
    assert [event.event_type for event in events] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED,
        BucketEventType.LEDGER_TRANSACTION_REMOVED,
        BucketEventType.LEDGER_TRANSACTION_REMOVED,
        BucketEventType.LEDGER_CATALOGUE_RESET,
    ]
    assert events[-1].event_type is BucketEventType.LEDGER_CATALOGUE_RESET
    assert events[-1].payload["removed_transaction_count"] == "2"
    assert events[-1].payload["reason"] == "contaminated import batch"


def test_reset_ledger_catalogue_refuses_finalized_modelo_reference(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 2),
            amount=Decimal("-25.00"),
            direction=TransactionDirection.OUTGOING,
            description="modelo source row",
            idempotency_key="reset-blocked",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
    )
    _persist_verified_revision_citing_transaction(secure_engine, transaction_id=created.ref.transaction_id)

    dry_run = reset_ledger_catalogue(
        bucket_id="bucket-a",
        actor="operator-A",
        dry_run=True,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        work_unit_repository=WorkUnitCatalogueRepository(objects=SecureObjectRepository(engine=secure_engine)),
        calculation_repository=CalculationRevisionCatalogueRepository(
            objects=SecureObjectRepository(engine=secure_engine)
        ),
    )

    assert dry_run.blocking_modelo_references[0].modelo == "303"
    with pytest.raises(TransactionValidationError, match="finalized modelo"):
        reset_ledger_catalogue(
            bucket_id="bucket-a",
            actor="operator-A",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            work_unit_repository=WorkUnitCatalogueRepository(objects=SecureObjectRepository(engine=secure_engine)),
            calculation_repository=CalculationRevisionCatalogueRepository(
                objects=SecureObjectRepository(engine=secure_engine)
            ),
        )

    assert transaction_repository.load().get(created.ref.transaction_id) is not None
    assert [event.event_type for event in event_repository.load().for_bucket("bucket-a")] == [
        BucketEventType.LEDGER_TRANSACTION_CREATED
    ]


def test_update_manual_transaction_rejects_usage_ratio_drift_without_event_or_save(
    secure_engine: Engine,
) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    category = SpendingCategory.TELEFONIA_MOVIL
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-50.00"),
            direction=TransactionDirection.OUTGOING,
            description="telefono movil",
            idempotency_key="usage-ratio-update",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )
    profile = UsageRatioProfile(ratios={category: Decimal("0.60")})

    with pytest.raises(TransactionValidationError, match="does not match"):
        update_manual_transaction(
            transaction_id=created.ref.transaction_id,
            command=ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 1),
                amount=Decimal("-50.00"),
                direction=TransactionDirection.OUTGOING,
                description="telefono movil corrected",
                business_classification=BusinessClassification.MIXED,
                business_pct=Decimal("0.50"),
                category_id=category.value,
                usage_ratio_id=category.value,
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            usage_ratio_profile=profile,
            occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
        )

    reloaded = transaction_repository.load()
    assert tuple(reloaded.transactions) == (created.ref.transaction_id,)
    events = event_repository.load().for_bucket("bucket-a")
    assert [event.event_type for event in events] == [BucketEventType.LEDGER_TRANSACTION_CREATED]


def test_update_manual_transaction_rejects_provenance_only_correction(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id="bucket-a",
            booked_date=date(2026, 5, 1),
            amount=Decimal("-50.00"),
            direction=TransactionDirection.OUTGOING,
            description="same row",
            idempotency_key="same-row",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
    )

    with pytest.raises(TransactionValidationError, match="must change at least one ledger field"):
        update_manual_transaction(
            transaction_id=created.ref.transaction_id,
            command=ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 1),
                amount=Decimal("-50.00"),
                direction=TransactionDirection.OUTGOING,
                description="same row",
                idempotency_key="same-row",
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 2, 10, 0, tzinfo=UTC),
        )


def test_create_manual_transaction_rejects_missing_purchase_evidence(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    invoice_repository = InvoiceCatalogueRepository(objects=SecureObjectRepository(engine=secure_engine))
    invoice_repository.save(InvoiceCatalogue())

    with pytest.raises(TransactionValidationError, match="purchase_invoice_evidence_id"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 2),
                amount=Decimal("-121.00"),
                direction=TransactionDirection.OUTGOING,
                description="material oficina",
                purchase_invoice_evidence_id="missing-purchase-evidence",
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            invoice_repository=invoice_repository,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    assert transaction_repository.load().transactions == {}
    assert event_repository.load().events == {}


def test_create_manual_transaction_rejects_missing_attachment_manifest(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    objects = SecureObjectRepository(engine=secure_engine)

    with pytest.raises(TransactionValidationError, match="attachment_ids"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 2),
                amount=Decimal("-121.00"),
                direction=TransactionDirection.OUTGOING,
                description="material oficina",
                attachment_ids=("a" * 64,),
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            attachment_store=AttachmentStore(objects=objects),
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    assert transaction_repository.load().transactions == {}
    assert event_repository.load().events == {}


def test_create_manual_transaction_rejects_purchase_evidence_from_other_bucket(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    invoice_repository = InvoiceCatalogueRepository(objects=SecureObjectRepository(engine=secure_engine))
    other_bucket_invoice = _purchase_invoice().model_copy(update={"bucket_id": "bucket-b"})
    invoice_repository.save(InvoiceCatalogue.from_invoices((other_bucket_invoice,)))

    with pytest.raises(TransactionValidationError, match="command bucket"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 2),
                amount=Decimal("-121.00"),
                direction=TransactionDirection.OUTGOING,
                description="material oficina",
                purchase_invoice_evidence_id=other_bucket_invoice.invoice_id,
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            invoice_repository=invoice_repository,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    assert transaction_repository.load().transactions == {}
    assert event_repository.load().events == {}


def test_create_manual_transaction_rejects_attachment_from_other_bucket(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine)
    objects = SecureObjectRepository(engine=secure_engine)
    store = AttachmentStore(objects=objects)
    body = b"%PDF-1.4\nother bucket evidence\n%%EOF"
    attachment_id = store.put_bytes(body)
    store.write_manifest(
        Attachment(
            attachment_id=attachment_id,
            kind=AttachmentKind.INVOICE_PDF,
            source=AttachmentSource.LOCAL_FILE,
            source_reference="other-bucket.pdf",
            sha256=hashlib.sha256(body).hexdigest(),
            mime_type="application/pdf",
            bytes_size=len(body),
            captured_at=datetime(2026, 5, 4, 9, 0, tzinfo=UTC),
            bucket_id="bucket-b",
            captured_by="operator-B",
            source_command="aeat app ledger attach",
        )
    )

    with pytest.raises(TransactionValidationError, match="command bucket"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 2),
                amount=Decimal("-121.00"),
                direction=TransactionDirection.OUTGOING,
                description="material oficina",
                attachment_ids=(attachment_id,),
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            attachment_store=store,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )

    assert transaction_repository.load().transactions == {}
    assert event_repository.load().events == {}


def test_create_manual_transaction_rejects_repository_bucket_mismatch(secure_engine: Engine) -> None:
    transaction_repository, event_repository = _repositories(secure_engine, bucket_id="bucket-b")

    with pytest.raises(TransactionValidationError, match="bucket_id"):
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id="bucket-a",
                booked_date=date(2026, 5, 2),
                amount=Decimal("-10.00"),
                direction=TransactionDirection.OUTGOING,
                description="wrong bucket",
            ),
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
        )


def test_create_manual_transaction_does_not_save_transaction_when_event_history_fails(
    secure_engine: Engine,
    tmp_path: Path,
) -> None:
    transaction_repository, _ = _repositories(secure_engine)
    broken_engine = create_engine(f"sqlite:///{tmp_path / 'broken-events.db'}")
    broken_objects = SecureObjectRepository(engine=broken_engine)
    Base.metadata.drop_all(broken_engine)
    try:
        with pytest.raises(SQLAlchemyError):
            create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id="bucket-a",
                    booked_date=date(2026, 5, 2),
                    amount=Decimal("-10.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="event failure",
                ),
                transaction_repository=transaction_repository,
                bucket_event_repository=BucketEventHistoryRepository(objects=broken_objects),
                occurred_at=datetime(2026, 5, 4, 9, 30, tzinfo=UTC),
            )
    finally:
        broken_engine.dispose()

    assert transaction_repository.load().transactions == {}
