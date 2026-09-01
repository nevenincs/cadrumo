"""Shared support for manual ledger transaction application tests."""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest

from ....adapters.inbound.financial.providers.base import ParsedLedgerRow
from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.attachment import AttachmentStore
from ....adapters.persistence.storage.errors import StorageValidationError
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....application.ledger.actions_export import export_ledger_transactions
from ....application.ledger.actions_import import import_ledger_source, import_ledger_transactions
from ....application.ledger.actions_lifecycle import (
    archive_manual_transaction,
    remove_manual_transaction,
    reset_ledger_catalogue,
    restore_manual_transaction,
    stash_manual_transaction,
)
from ....application.ledger.actions_manual import (
    attach_manual_transaction_evidence,
    detach_manual_transaction_attachments,
    summarize_manual_transactions,
    update_manual_transaction,
    update_manual_transaction_fields,
)
from ....application.ledger.models import LedgerExportCommand, LedgerSourceImportCommand, ManualLedgerTransactionPatch
from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.attachments.enums import AttachmentKind, AttachmentSource
from ....domain.attachments.models import Attachment
from ....domain.buckets.event import BucketEvent, BucketEventObjectType, BucketEventType
from ....domain.categories.spending_category import SpendingCategory
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.errors import TransactionValidationError
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.usage_ratios.model import UsageRatioProfile
from ....tests import general_m303_filing_evidence
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import (
    TestRuntimeProfile,
    isolated_runtime_profile,
    reset_secure_object_store,
)
from ...export.tabular import ExportSerializationFormat
from ..actions_manual import create_manual_transaction
from ..models import ManualLedgerTransactionCommand, ManualLedgerTransactionResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_REVISION_CASILLA: CasillaId = validated_casilla_id("01")
_BUCKET_ID = "26262626-2626-4626-8626-262626262626"
_OTHER_BUCKET_ID = "27272727-2727-4727-8727-272727272727"

__all__ = [
    "POST_UPDATE_EVENT_PAYLOADS",
    "PRESERVED_CREATE_AUDIT_FIELDS",
    "PROVENANCE_RAW_FIELD_EXPECTATIONS",
    "TAXABLE_IVA_EXPECTATIONS",
    "UPDATED_FIELD_EXPECTATIONS",
    "UTC",
    "_BUCKET_ID",
    "_OTHER_BUCKET_ID",
    "Attachment",
    "AttachmentKind",
    "AttachmentSource",
    "AttachmentStore",
    "BindingSourceKind",
    "BucketEvent",
    "BucketEventObjectType",
    "BucketEventType",
    "BusinessClassification",
    "CreateManualOutcome",
    "Decimal",
    "ExportSerializationFormat",
    "LedgerExportCommand",
    "LedgerSourceImportCommand",
    "ManualLedgerTransactionCommand",
    "ManualLedgerTransactionPatch",
    "ParsedLedgerRow",
    "Path",
    "RawProvenance",
    "RawTransaction",
    "SecureObjectRepository",
    "SourceFormat",
    "SpendingCategory",
    "StorageValidationError",
    "StringIO",
    "Transaction",
    "TransactionCatalogue",
    "TransactionDirection",
    "TransactionLifecycleState",
    "TransactionValidationError",
    "UsageRatioProfile",
    "_create_manual_row",
    "_ledger_module_runtime",
    "_repositories",
    "archive_manual_transaction",
    "attach_manual_transaction_evidence",
    "create_manual_transaction",
    "csv",
    "date",
    "datetime",
    "detach_manual_transaction_attachments",
    "export_ledger_transactions",
    "hashlib",
    "import_ledger_source",
    "import_ledger_transactions",
    "parsed_import_transaction",
    "persist_verified_revision_citing_transaction",
    "purchase_invoice",
    "remove_manual_transaction",
    "reset_ledger_catalogue",
    "restore_manual_transaction",
    "secure_objects",
    "stash_manual_transaction",
    "summarize_manual_transactions",
    "update_manual_transaction",
    "update_manual_transaction_fields",
]


@pytest.fixture(scope="module")
def _ledger_module_runtime(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestRuntimeProfile]:
    """Provision the expensive bucket runtime once per test module.

    Hoisting the Argon2id KEK derivation, wrapped-DEK mint, session open, and
    per-bucket engine/table create out of per-test scope is the perf win.
    Per-test isolation is restored by the function-scoped ``secure_objects``
    fixture, which truncates the shared store before each test.
    """
    tmp_path = tmp_path_factory.mktemp("ledger-action-runtime")
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile


@pytest.fixture
def secure_objects(_ledger_module_runtime: TestRuntimeProfile) -> Iterator[SecureObjectRepository]:
    """Yield the module-shared repository over a per-test-reset secure-object store.

    The costly bucket provisioning is paid once by ``_ledger_module_runtime``;
    this fixture truncates the shared ``secure_objects`` table before each test so
    per-test isolation holds without re-minting the bucket. The reset is
    load-bearing: without it the module-shared store bleeds persisted rows across
    tests and idempotency / anti-tautology assertions stop biting.
    """
    reset_secure_object_store(_ledger_module_runtime.repository)
    yield _ledger_module_runtime.repository


def _repositories(
    objects: SecureObjectRepository,
    *,
    bucket_id: str = _BUCKET_ID,
) -> tuple[TransactionCatalogueRepository, BucketEventHistoryRepository]:
    return (
        TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects),
        BucketEventHistoryRepository(objects=objects),
    )


def _create_manual_row(
    secure_objects: SecureObjectRepository,
    *,
    description: str,
    idempotency_key: str,
    amount: Decimal | None = None,
    booked_date: date | None = None,
    occurred_at: datetime | None = None,
) -> tuple[TransactionCatalogueRepository, BucketEventHistoryRepository, ManualLedgerTransactionResult]:
    transaction_repository, event_repository = _repositories(secure_objects)
    resolved_booked_date = booked_date if booked_date is not None else date(2026, 5, 2)
    resolved_amount = amount if amount is not None else Decimal("25.00")
    resolved_occurred_at = occurred_at if occurred_at is not None else datetime(2026, 5, 4, 9, 30, tzinfo=UTC)
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=resolved_booked_date,
            amount=resolved_amount,
            direction=TransactionDirection.OUTGOING,
            description=description,
            idempotency_key=idempotency_key,
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=resolved_occurred_at,
    )
    return transaction_repository, event_repository, created


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
            "bucket_id": _BUCKET_ID,
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
        },
    )


def _raw_import_transaction(
    *,
    transaction_id: str = "provider-row-1",
    amount: Decimal = Decimal("80.00"),
    description: str = "provider import row",
) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=transaction_id,
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


def _parsed_import_transaction(
    *,
    transaction_id: str = "provider-row-1",
    amount: Decimal = Decimal("80.00"),
    description: str = "provider import row",
    direction: TransactionDirection = TransactionDirection.OUTGOING,
) -> ParsedLedgerRow:
    """Wrap a magnitude import row with an explicit direction (parse-boundary pair)."""
    return ParsedLedgerRow(
        raw=_raw_import_transaction(transaction_id=transaction_id, amount=amount, description=description),
        direction=direction,
    )


def parsed_import_transaction(
    *,
    transaction_id: str = "provider-row-1",
    amount: Decimal = Decimal("80.00"),
    description: str = "provider import row",
    direction: TransactionDirection = TransactionDirection.OUTGOING,
) -> ParsedLedgerRow:
    return _parsed_import_transaction(
        transaction_id=transaction_id,
        amount=amount,
        description=description,
        direction=direction,
    )


def _persist_verified_revision_citing_transaction(
    objects: SecureObjectRepository,
    *,
    transaction_id: str,
    additional_transaction_ids: Iterable[str] = (),
    bucket_id: str = _BUCKET_ID,
) -> None:
    source_transaction_ids = (transaction_id, *tuple(additional_transaction_ids))
    period = Period.from_year_and_code(2026, "1T")
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="2022",
    )
    filing_instance_evidence = general_m303_filing_evidence(period, reference="test:ledger-action-support")
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={_REVISION_CASILLA: "1"},
        binding_overrides={},
        casilla_values={_REVISION_CASILLA: Decimal("1")},
        source_transaction_ids=source_transaction_ids,
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("303"),
        filing_year=2026,
        period=period,
        revision_id="2022",
        name="303-2026-1T",
        created_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 2, 8, 0, tzinfo=UTC),
        current_calculation_revision_id=revision_id,
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id={_REVISION_CASILLA: "1"},
        binding_overrides={},
        source_transaction_ids=source_transaction_ids,
        casilla_values={_REVISION_CASILLA: Decimal("1")},
        observations=registry_grounded_observations(
            modelo="303",
            filing_year=2026,
            period=period.registry_token,
            casilla_values={_REVISION_CASILLA: Decimal("1")},
        ),
        created_at=datetime(2026, 5, 2, 8, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 2, 9, 0, tzinfo=UTC),
        verified_at=datetime(2026, 5, 2, 9, 0, tzinfo=UTC),
        verified_by="operator-A",
        filing_instance_evidence=filing_instance_evidence,
        source_provenance=(),
    )
    WorkUnitCatalogueRepository(objects=objects).save(WorkUnitCatalogue.from_work_units((work_unit,)))
    CalculationRevisionCatalogueRepository(objects=objects).save(
        CalculationRevisionCatalogue(revisions={revision_id: revision}),
    )


def purchase_invoice() -> Invoice:
    return _purchase_invoice()


def persist_verified_revision_citing_transaction(
    objects: SecureObjectRepository,
    *,
    transaction_id: str,
    additional_transaction_ids: Iterable[str] = (),
    bucket_id: str = _BUCKET_ID,
) -> None:
    _persist_verified_revision_citing_transaction(
        objects,
        transaction_id=transaction_id,
        additional_transaction_ids=additional_transaction_ids,
        bucket_id=bucket_id,
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


CreateManualOutcome = _CreateManualOutcome


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
        bucket_id=_BUCKET_ID,
        booked_date=date(2026, 5, 2),
        value_date=date(2026, 5, 3),
        amount=Decimal("121.00"),
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
    events = event_repository.load().for_bucket(_BUCKET_ID)
    return _CreateManualOutcome(
        result=result,
        persisted=persisted,
        events=tuple(events),
        purchase_invoice_evidence_id=purchase_evidence.invoice_id,
    )


def drive_create_manual_transaction(secure_objects: SecureObjectRepository) -> CreateManualOutcome:
    return _drive_create_manual_transaction(secure_objects)


_PROVENANCE_RAW_FIELD_EXPECTATIONS = (
    ("source_kind", BindingSourceKind.LEDGER_TRANSACTION.value),
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
    (BucketEventType.LEDGER_TRANSACTION_UPDATED, "mutation_kind", "edit"),
    (BucketEventType.LEDGER_TRANSACTION_CLASSIFIED, "mutation_kind", "classification"),
    (BucketEventType.LEDGER_TRANSACTION_ALLOCATED, "mutation_kind", "allocation"),
)

POST_UPDATE_EVENT_PAYLOADS = _POST_UPDATE_EVENT_PAYLOADS
PRESERVED_CREATE_AUDIT_FIELDS = _PRESERVED_CREATE_AUDIT_FIELDS
PROVENANCE_RAW_FIELD_EXPECTATIONS = _PROVENANCE_RAW_FIELD_EXPECTATIONS
TAXABLE_IVA_EXPECTATIONS = _TAXABLE_IVA_EXPECTATIONS
UPDATED_FIELD_EXPECTATIONS = _UPDATED_FIELD_EXPECTATIONS
