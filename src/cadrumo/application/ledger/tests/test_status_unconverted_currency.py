"""A foreign row with no conversion is left out of the euro roll-up, and counted.

The money summary added every active business row into one euro total, falling
back to ``raw.amount`` whenever ``value_in_eur`` was absent. For a domestic row
that fallback is right -- its native amount IS euros. For a foreign row that was
never converted it is not an approximation but a different number wearing the
wrong unit: 1000 USD landed in the total as 1000 EUR.

``effective_eur_amount`` already refuses to answer for such a row, and says why:
a caller that skipped the gate must fail loud rather than fold a foreign amount
into a euro-denominated total. The summary was that caller. It now asks the same
shared predicate, excludes the row, and reports how many it excluded, so a
partial total is visible as partial instead of quietly wrong.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256 as compute_sha256
from pathlib import Path
from typing import override

import pytest

from cadrumo.core.classification.policies import SensitivityClass
from cadrumo.core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from cadrumo.core.secure_object_write import SecureObjectWrite

from ....domain.attachments.models import Attachment
from ....domain.attachments.protocols import AttachmentStoreProtocol
from ....domain.buckets.event import BucketEventHistoryCatalogue
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.invoices.models import InvoiceCatalogue
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ....domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol
from ....domain.modelos.work_unit import WorkUnitCatalogue
from ....domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import (
    LedgerDatePartition,
    OutOfWindowTransactionIndexEntry,
    OutOfWindowTransactionSummary,
    Transaction,
    TransactionCatalogue,
)
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.usage_ratios.model import UsageRatioProfile
from ..action_ports import LedgerActionPorts
from ..actions_manual import summarize_manual_transactions
from ..protocols import (
    BucketEventHistoryCoCommitWriterProtocol,
    InvoiceCatalogueCoCommitWriterProtocol,
    TransactionCatalogueCoCommitWriterProtocol,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "fx0f0f0f-0000-4000-8000-00000000fx01"
_IVA_RATE = Decimal("0.21")
_YEAR = 2026
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_REVISION_ID = "0" * 64


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Pin the compiled authority across transaction construction and summary."""
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _secure_write(
    *,
    namespace: str,
    object_key: str,
    payload: bytes,
    expected_revision_id: str | None = None,
) -> SecureObjectWrite:
    return SecureObjectWrite(
        namespace=namespace,
        object_key=object_key,
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=_T0,
        payload=payload,
        expected_revision_id=expected_revision_id,
    )


class _InMemoryTransactionRepository(TransactionCatalogueCoCommitWriterProtocol):
    """Application transaction port that retains the supplied catalogue."""

    def __init__(self, *, bucket_id: str, catalogue: TransactionCatalogue) -> None:
        self._bucket_id = bucket_id
        self._catalogue = catalogue

    @property
    @override
    def bucket_id(self) -> str:
        return self._bucket_id

    @override
    def exists(self) -> bool:
        return bool(self._catalogue.transactions)

    @override
    def load(self) -> TransactionCatalogue:
        return self._catalogue

    @override
    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        return TransactionCatalogue.from_transactions(
            transaction
            for transaction in self._catalogue
            if start <= (transaction.raw.value_date or transaction.raw.booked_date) <= end
        )

    @override
    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        requested = frozenset(transaction_ids)
        return TransactionCatalogue.from_transactions(
            transaction for transaction in self._catalogue if transaction.transaction_id in requested
        )

    @override
    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        in_window: list[Transaction] = []
        out_of_window: list[OutOfWindowTransactionIndexEntry] = []
        for transaction in self._catalogue:
            filing_date = transaction.raw.value_date or transaction.raw.booked_date
            if start <= filing_date <= end:
                in_window.append(transaction)
            else:
                out_of_window.append(
                    OutOfWindowTransactionIndexEntry(
                        transaction_id=transaction.transaction_id,
                        filing_date=filing_date,
                    ),
                )
        return LedgerDatePartition(
            in_window=TransactionCatalogue.from_transactions(in_window),
            out_of_window=tuple(out_of_window),
            out_of_window_summary=OutOfWindowTransactionSummary.from_index_entries(out_of_window),
            index_complete=True,
        )

    @override
    def save(self, catalogue: TransactionCatalogue) -> None:
        self._catalogue = catalogue

    @override
    def save_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        del extra_writes
        self._catalogue = catalogue

    @override
    def replace_if_current_with_secure_object_writes(
        self,
        current: Transaction,
        replacement: Transaction,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        del extra_writes
        if self._catalogue.get(current.transaction_id) != current:
            raise AssertionError("guarded replacement received a stale baseline")
        updated = dict(self._catalogue.transactions)
        updated.pop(current.transaction_id)
        updated[replacement.transaction_id] = replacement
        self._catalogue = TransactionCatalogue.from_transactions(updated.values())


class _InMemoryEventRepository(BucketEventHistoryCoCommitWriterProtocol):
    """In-memory event port for the complete action-port composition."""

    def __init__(self) -> None:
        self._catalogue = BucketEventHistoryCatalogue()
        self._revision_id = _REVISION_ID

    @override
    def exists(self) -> bool:
        return bool(self._catalogue.events)

    @override
    def load(self) -> BucketEventHistoryCatalogue:
        return self._catalogue

    @override
    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        self._catalogue = catalogue

    @override
    def load_revisioned(self) -> tuple[BucketEventHistoryCatalogue, str]:
        return self._catalogue, self._revision_id

    @override
    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        return _secure_write(
            namespace="application-test-events",
            object_key="status-unconverted-currency",
            payload=catalogue.model_dump_json().encode("utf-8"),
            expected_revision_id=expected_revision_id,
        )


class _InMemoryInvoiceRepository(InvoiceCatalogueCoCommitWriterProtocol):
    """Empty invoice port required by the shared ledger action bundle."""

    def __init__(self) -> None:
        self._catalogue = InvoiceCatalogue()
        self._revision_id = _REVISION_ID

    @property
    @override
    def bucket_id(self) -> str:
        return _BUCKET

    @override
    def exists(self) -> bool:
        return bool(self._catalogue.invoices)

    @override
    def load(self) -> InvoiceCatalogue:
        return self._catalogue

    @override
    def save(self, catalogue: InvoiceCatalogue) -> None:
        self._catalogue = catalogue

    @override
    def load_revisioned(self) -> tuple[InvoiceCatalogue, str]:
        return self._catalogue, self._revision_id

    @override
    def to_secure_object_write(
        self,
        catalogue: InvoiceCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        return _secure_write(
            namespace="application-test-invoices",
            object_key="status-unconverted-currency",
            payload=catalogue.model_dump_json().encode("utf-8"),
            expected_revision_id=expected_revision_id,
        )


class _InMemoryAttachmentStore(AttachmentStoreProtocol):
    """Small content-addressed attachment port with no filesystem persistence."""

    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}
        self._manifests: dict[str, Attachment] = {}

    @override
    def put_bytes(self, data: bytes) -> str:
        attachment_id = compute_sha256(data).hexdigest()
        self._blobs[attachment_id] = data
        return attachment_id

    @override
    def put_file(self, source: Path) -> tuple[str, int]:
        data = source.read_bytes()
        return self.put_bytes(data), len(data)

    @override
    def read_bytes(self, sha256: str) -> bytes:
        return self._blobs[sha256]

    @override
    def write_manifest(self, attachment: Attachment) -> None:
        self._manifests[attachment.attachment_id] = attachment

    @override
    def load_manifest(self, attachment_id: str) -> Attachment:
        return self._manifests[attachment_id]

    @override
    def iter_manifests(self) -> Iterator[Attachment]:
        for attachment_id in sorted(self._manifests):
            yield self._manifests[attachment_id]

    @override
    def verify_blob(self, attachment_id: str) -> None:
        if compute_sha256(self._blobs[attachment_id]).hexdigest() != attachment_id:
            raise ValueError(f"attachment blob digest mismatch for {attachment_id}")


class _InMemoryWorkUnitRepository(WorkUnitCatalogueRepositoryProtocol):
    """Empty work-unit port required by the shared ledger action bundle."""

    def __init__(self) -> None:
        self._catalogue = WorkUnitCatalogue()
        self._revision_id = _REVISION_ID

    @property
    @override
    def bucket_id(self) -> str:
        return _BUCKET

    @override
    def exists(self) -> bool:
        return bool(self._catalogue.work_units)

    @override
    def load(self) -> WorkUnitCatalogue:
        return self._catalogue

    @override
    def load_revisioned(self) -> tuple[WorkUnitCatalogue, str]:
        return self._catalogue, self._revision_id

    @override
    def save(self, catalogue: WorkUnitCatalogue) -> None:
        self._catalogue = catalogue

    @override
    def mutate(self, mutation: Callable[[WorkUnitCatalogue], WorkUnitCatalogue]) -> WorkUnitCatalogue:
        self._catalogue = mutation(self._catalogue)
        return self._catalogue

    @override
    def save_with_secure_object_writes(
        self,
        catalogue: WorkUnitCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
        *,
        expected_revision_id: str | None = None,
    ) -> None:
        del extra_writes, expected_revision_id
        self._catalogue = catalogue

    @override
    def to_secure_object_write(
        self,
        catalogue: WorkUnitCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        return _secure_write(
            namespace="application-test-work-units",
            object_key="status-unconverted-currency",
            payload=catalogue.model_dump_json().encode("utf-8"),
            expected_revision_id=expected_revision_id,
        )


class _InMemoryCalculationRepository(CalculationRevisionCatalogueRepositoryProtocol):
    """Empty calculation port required by the shared ledger action bundle."""

    def __init__(self) -> None:
        self._catalogue = CalculationRevisionCatalogue()
        self._revision_id = _REVISION_ID

    @property
    @override
    def bucket_id(self) -> str:
        return _BUCKET

    @override
    def exists(self) -> bool:
        return bool(self._catalogue.revisions)

    @override
    def load(self) -> CalculationRevisionCatalogue:
        return self._catalogue

    @override
    def load_revisioned(self) -> tuple[CalculationRevisionCatalogue, str]:
        return self._catalogue, self._revision_id

    @override
    def save(self, catalogue: CalculationRevisionCatalogue) -> None:
        self._catalogue = catalogue

    @override
    def to_secure_object_write(
        self,
        catalogue: CalculationRevisionCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        return _secure_write(
            namespace="application-test-calculations",
            object_key="status-unconverted-currency",
            payload=catalogue.model_dump_json().encode("utf-8"),
            expected_revision_id=expected_revision_id,
        )

    @override
    def save_with_secure_object_writes(
        self,
        catalogue: CalculationRevisionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
        *,
        expected_revision_id: str | None = None,
    ) -> None:
        del extra_writes, expected_revision_id
        self._catalogue = catalogue


def _empty_usage_ratio_profile(*, bucket_id: str, operation: PinnedAuthorityOperation) -> UsageRatioProfile:
    """Return an empty profile while honoring the operation-bound loader shape."""
    del bucket_id, operation
    return UsageRatioProfile()


def _raw_transaction(provider_id: str, *, booked_date: date, amount: Decimal) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency="EUR",
        description=f"IVA transaction {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_T0,
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def iva_transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    taxable_base: Decimal,
) -> Transaction:
    iva_amount = (taxable_base * _IVA_RATE).quantize(Decimal("0.01"))
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=date(_YEAR, 2, 15),
                amount=taxable_base + iva_amount,
            ),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": "BUSINESS",
            "category_id": "material_oficina",
            "taxable_base": taxable_base,
            "iva_rate": _IVA_RATE,
            "iva_amount": iva_amount,
            "deduction_fact_kind": (
                IvaDeductionFactKind.from_registry("domestic_current")
                if direction is TransactionDirection.OUTGOING
                else None
            ),
            "deduction_provenance": (
                IvaDeductionClassificationProvenance(
                    authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
                    source_locator=f"test-invoice:{provider_id}",
                    evidence_digest="a" * 64,
                )
                if direction is TransactionDirection.OUTGOING
                else None
            ),
            "classified_at": _T0,
            "classified_by": "manual",
        },
    )


def _eur_income(label: str, *, base: Decimal) -> Transaction:
    return iva_transaction(label, direction=TransactionDirection.INCOMING, taxable_base=base)


def _foreign(
    transaction: Transaction,
    *,
    currency: str,
    fx_rate: Decimal | None = None,
) -> Transaction:
    """Restate a row in a foreign currency, converting it when a rate is given.

    ``fx_rate`` and ``value_in_eur`` must both be set or both be absent, and
    the EUR value is derived from the rate rather than chosen independently:
    the relation is multiplicative over the gross, so an invented pair would
    make the fixture assert a conversion that never happened.
    """
    return transaction.model_copy(
        update={
            "raw": transaction.raw.model_copy(update={"currency": currency}),
            "fx_rate": fx_rate,
            "value_in_eur": None if fx_rate is None else transaction.raw.amount * fx_rate,
        },
    )


def _summarise(*transactions: Transaction, operation: PinnedAuthorityOperation):
    transaction_repository = _InMemoryTransactionRepository(
        bucket_id=_BUCKET,
        catalogue=TransactionCatalogue.from_transactions(transactions),
    )
    ports = LedgerActionPorts(
        operation=operation,
        transaction_repository=transaction_repository,
        bucket_event_repository=_InMemoryEventRepository(),
        invoice_repository=_InMemoryInvoiceRepository(),
        attachment_store=_InMemoryAttachmentStore(),
        usage_ratio_profile=UsageRatioProfile(),
        usage_ratio_profile_loader=_empty_usage_ratio_profile,
        work_unit_repository=_InMemoryWorkUnitRepository(),
        calculation_repository=_InMemoryCalculationRepository(),
        purchase_invoice_evidence_records=(),
    )
    return summarize_manual_transactions(
        bucket_id=_BUCKET,
        ports=ports,
    )


def test_a_domestic_row_without_an_explicit_eur_value_is_still_counted(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The fallback is correct here: a EUR row's native amount IS euros.

    Without this the fix would read as a pass merely because everything was
    excluded.
    """
    report = _summarise(_eur_income("fx-domestic", base=Decimal("1000.00")), operation=authority_operation)

    assert report.unconverted_currency_count == 0
    assert Decimal(report.business_income_total) == Decimal("1210.00")


def test_an_unconverted_foreign_row_is_excluded_from_the_total_and_counted(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The defect: its native amount is not euros, so it has nothing to add."""
    domestic = _eur_income("fx-domestic", base=Decimal("1000.00"))
    unconverted = _foreign(_eur_income("fx-foreign", base=Decimal("5000.00")), currency="USD")

    report = _summarise(domestic, unconverted, operation=authority_operation)

    assert report.unconverted_currency_count == 1
    # The domestic row's gross alone -- the foreign figure is absent, not added.
    assert Decimal(report.business_income_total) == Decimal("1210.00")


def test_a_converted_foreign_row_contributes_its_euro_value_not_its_face_value(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Conversion is what makes a foreign row summable, and at the converted figure."""
    # 6050.00 gross at 0.9 -> 5445.00, which is NOT the 6050.00 face value.
    converted = _foreign(
        _eur_income("fx-foreign", base=Decimal("5000.00")),
        currency="USD",
        fx_rate=Decimal("0.9"),
    )

    report = _summarise(converted, operation=authority_operation)

    assert report.unconverted_currency_count == 0
    assert Decimal(report.business_income_total) == Decimal("5445.00")
    assert Decimal(report.business_income_total) != converted.raw.amount


def test_the_count_reports_only_rows_the_roll_up_would_otherwise_have_taken(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """An excluded-anyway row is not an unconverted-currency problem to report.

    A personal row never entered the total, so counting it would send the
    operator to convert a row whose conversion would change nothing.
    """
    personal_foreign = _foreign(
        _eur_income("fx-personal", base=Decimal("5000.00")),
        currency="USD",
    ).model_copy(update={"business_classification": "PERSONAL"})

    report = _summarise(personal_foreign, operation=authority_operation)

    assert report.unconverted_currency_count == 0
    assert Decimal(report.business_income_total) == Decimal("0.00")
