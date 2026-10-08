"""Authority membership guards for every manual ledger category writer."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from typing import Any, cast

import pytest

import cadrumo.application.ledger.actions_manual as actions_manual

from ....core.classification.policies import SensitivityClass
from ....core.secure_object_write import SecureObjectWrite
from ....domain.attachments.enums import AttachmentKind, AttachmentSource
from ....domain.attachments.models import Attachment
from ....domain.buckets.event import BucketEventHistoryCatalogue
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.iva.schema import IvaCategory
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ....domain.modelos.work_unit import WorkUnitCatalogue
from ....domain.transactions.dates import transaction_filing_date
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.errors import TransactionValidationError
from ....domain.transactions.models import LedgerDatePartition, Transaction, TransactionCatalogue
from ....domain.usage_ratios.model import UsageRatioProfile
from ..action_ports import LedgerActionPorts
from ..actions_classification import bulk_classify_from_csv
from ..actions_manual import create_manual_transaction, update_manual_transaction_fields
from ..models import ManualLedgerTransactionCommand, ManualLedgerTransactionPatch
from ..persistence_ports import LedgerPersistenceConflictError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "21000000-0000-4000-8000-000000000001"
_BOOKED = date(2026, 5, 2)
_NOW = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)
_ATTACHMENT_ID = "a" * 64


class _PreparedEventWrite(SecureObjectWrite):
    catalogue: BucketEventHistoryCatalogue


class _EventRepository:
    def __init__(self) -> None:
        self.catalogue = BucketEventHistoryCatalogue()
        self.revision_id: str = "0" * 64
        self.save_count = 0

    def load(self) -> BucketEventHistoryCatalogue:
        return self.catalogue

    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        self.catalogue = catalogue
        self.revision_id = sha256(self.revision_id.encode()).hexdigest()
        self.save_count += 1

    def load_revisioned(self) -> tuple[BucketEventHistoryCatalogue, str]:
        return self.catalogue, self.revision_id

    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> _PreparedEventWrite:
        return _PreparedEventWrite(
            namespace="application-test-events",
            object_key="iva-category-membership",
            classification=SensitivityClass.AUDIT,
            schema_version=1,
            written_at=_NOW,
            payload=b"event-catalogue",
            expected_revision_id=expected_revision_id,
            catalogue=catalogue,
        )

    def commit(self, write: _PreparedEventWrite) -> None:
        if write.expected_revision_id != self.revision_id:
            raise AssertionError("test event write used a stale revision")
        self.save(write.catalogue)


class _TransactionRepository:
    def __init__(self, catalogue: TransactionCatalogue, events: _EventRepository) -> None:
        self.bucket_id = _BUCKET
        self.catalogue = catalogue
        self.events = events
        self.save_count = 0
        self.guarded_replacement: tuple[Transaction, Transaction] | None = None
        self.revision_id = sha256(catalogue.model_dump_json().encode("utf-8")).hexdigest()
        self.after_load_revisioned: Callable[[], None] | None = None

    def exists(self) -> bool:
        return bool(self.catalogue.transactions)

    def load(self) -> TransactionCatalogue:
        return self.catalogue

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        return TransactionCatalogue.from_transactions(
            transaction
            for transaction in self.catalogue.values()
            if start <= transaction_filing_date(transaction) <= end
        )

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        selected_ids = set(transaction_ids)
        return TransactionCatalogue.from_transactions(
            transaction for transaction in self.catalogue.values() if transaction.transaction_id in selected_ids
        )

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        _ = start, end
        raise NotImplementedError("this fixture does not exercise range partitioning")

    def save(self, catalogue: TransactionCatalogue) -> None:
        self.catalogue = catalogue
        self.save_count += 1
        self._advance_revision()

    def load_revisioned(self) -> tuple[TransactionCatalogue, str]:
        snapshot = self.catalogue, self.revision_id
        if self.after_load_revisioned is not None:
            after_load = self.after_load_revisioned
            self.after_load_revisioned = None
            after_load()
        return snapshot

    def replace_catalogue_from_concurrent_writer(self, catalogue: TransactionCatalogue) -> None:
        """Model a catalogue write landing after a caller captured its snapshot."""
        self.catalogue = catalogue
        self.save_count += 1
        self._advance_revision()

    def _advance_revision(self) -> None:
        payload = self.catalogue.model_dump_json().encode("utf-8")
        self.revision_id = sha256(self.revision_id.encode("ascii") + b"\0" + payload).hexdigest()

    def save_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        (event_write,) = extra_writes
        if not isinstance(event_write, _PreparedEventWrite):
            raise TypeError("test action port expected a prepared bucket-event write")
        self.events.commit(event_write)
        self.catalogue = catalogue
        self.save_count += 1
        self._advance_revision()

    def save_if_revision_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        *,
        expected_revision_id: str,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        if expected_revision_id != self.revision_id:
            raise LedgerPersistenceConflictError("transaction catalogue changed since the snapshot was loaded")
        (event_write,) = extra_writes
        if not isinstance(event_write, _PreparedEventWrite):
            raise TypeError("test action port expected a prepared bucket-event write")
        self.events.commit(event_write)
        self.catalogue = catalogue
        self.save_count += 1
        self._advance_revision()

    def replace_if_current_with_secure_object_writes(
        self,
        current: Transaction,
        replacement: Transaction,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        if self.catalogue.get(current.transaction_id) != current:
            raise AssertionError("test guarded replacement received a stale baseline")
        (event_write,) = extra_writes
        if not isinstance(event_write, _PreparedEventWrite):
            raise TypeError("test action port expected a prepared bucket-event write")
        self.events.commit(event_write)
        updated = dict(self.catalogue.transactions)
        updated.pop(current.transaction_id)
        updated[replacement.transaction_id] = replacement
        self.catalogue = TransactionCatalogue.from_transactions(updated.values())
        self.guarded_replacement = current, replacement
        self.save_count += 1
        self._advance_revision()


class _EmptyRepository:
    def __init__(self, catalogue: object) -> None:
        self.catalogue = catalogue

    def load(self) -> object:
        return self.catalogue


def _command(
    *,
    description: str = "category membership fixture",
    iva_category: IvaCategory | None = None,
    attachment_ids: tuple[str, ...] = (),
) -> ManualLedgerTransactionCommand:
    return ManualLedgerTransactionCommand(
        bucket_id=_BUCKET,
        booked_date=_BOOKED,
        amount=Decimal("10.00"),
        direction=TransactionDirection.OUTGOING,
        description=description,
        business_classification=BusinessClassification.BUSINESS,
        actor="operator",
        source_command="aeat app ledger add",
        iva_category=iva_category,
        attachment_ids=attachment_ids,
    )


def _ports(
    *,
    operation: PinnedAuthorityOperation,
    transactions: _TransactionRepository,
    events: _EventRepository,
    attachment_store: object | None = None,
) -> LedgerActionPorts:
    return LedgerActionPorts(
        operation=operation,
        transaction_repository=cast(Any, transactions),
        bucket_event_repository=cast(Any, events),
        invoice_repository=cast(Any, None),
        attachment_store=cast(Any, attachment_store),
        usage_ratio_profile=UsageRatioProfile(),
        usage_ratio_profile_loader=lambda **_kwargs: UsageRatioProfile(),
        work_unit_repository=cast(Any, _EmptyRepository(WorkUnitCatalogue())),
        calculation_repository=cast(Any, _EmptyRepository(CalculationRevisionCatalogue())),
        purchase_invoice_evidence_records=(),
    )


def _repositories(catalogue: TransactionCatalogue) -> tuple[_TransactionRepository, _EventRepository]:
    events = _EventRepository()
    return _TransactionRepository(catalogue, events), events


def _stored_catalogue(*descriptions: str) -> TransactionCatalogue:
    return TransactionCatalogue.from_transactions(
        actions_manual._transaction_from_command(_command(description=description), occurred_at=_NOW)
        for description in descriptions
    )


def test_create_and_update_persist_real_date_supported_categories(
    operation: PinnedAuthorityOperation,
) -> None:
    transactions, events = _repositories(TransactionCatalogue())
    ports = _ports(operation=operation, transactions=transactions, events=events)
    created = create_manual_transaction(
        _command(iva_category=IvaCategory("domestic_general")),
        ports=ports,
        occurred_at=_NOW,
    )
    assert (created_transaction := transactions.catalogue.get(created.ref.transaction_id)) is not None
    assert created_transaction.iva_category == IvaCategory("domestic_general")

    updated = update_manual_transaction_fields(
        bucket_id=_BUCKET,
        transaction_id=created.ref.transaction_id,
        patch=ManualLedgerTransactionPatch(iva_category=IvaCategory("operacion_no_sujeta")),
        actor="operator",
        source_command="aeat app ledger classify",
        ports=ports,
        occurred_at=_NOW,
    )

    assert updated.transaction.iva_category == IvaCategory("operacion_no_sujeta")
    assert (updated_transaction := transactions.catalogue.get(updated.ref.transaction_id)) is not None
    assert updated_transaction.iva_category == IvaCategory("operacion_no_sujeta")
    assert transactions.save_count == events.save_count == 2


def test_create_refuses_a_real_undeclared_category_before_catalogue_or_event_write(
    operation: PinnedAuthorityOperation,
) -> None:
    transactions, events = _repositories(TransactionCatalogue())

    with pytest.raises(RegistryValidationError, match="not declared by the facts registry"):
        create_manual_transaction(
            _command(iva_category=IvaCategory("not-a-declared-category")),
            ports=_ports(operation=operation, transactions=transactions, events=events),
            occurred_at=_NOW,
        )

    assert transactions.catalogue == TransactionCatalogue()
    assert transactions.save_count == events.save_count == 0


def test_field_patch_refuses_a_real_undeclared_category_without_a_catalogue_or_event_write(
    operation: PinnedAuthorityOperation,
) -> None:
    catalogue = _stored_catalogue("field-patch membership fixture")
    transaction_id = next(iter(catalogue.transactions))
    transactions, events = _repositories(catalogue)

    with pytest.raises(RegistryValidationError, match="not declared by the facts registry"):
        update_manual_transaction_fields(
            bucket_id=_BUCKET,
            transaction_id=transaction_id,
            patch=ManualLedgerTransactionPatch(iva_category=IvaCategory("not-a-declared-category")),
            actor="operator",
            source_command="aeat app ledger classify",
            ports=_ports(operation=operation, transactions=transactions, events=events),
            occurred_at=_NOW,
        )

    assert transactions.catalogue == catalogue
    assert transactions.save_count == events.save_count == 0


def test_bulk_classification_persists_valid_rows_and_collects_undeclared_categories(
    operation: PinnedAuthorityOperation,
) -> None:
    catalogue = _stored_catalogue("valid batch row", "undeclared batch row")
    valid_id, invalid_id = tuple(catalogue.transactions)
    transactions, events = _repositories(catalogue)

    result = bulk_classify_from_csv(
        bucket_id=_BUCKET,
        csv_text=(
            "transaction_id,classification,iva_category\n"
            f"{valid_id},BUSINESS,domestic_general\n"
            f"{invalid_id},BUSINESS,not-a-declared-category\n"
        ),
        actor="operator",
        ports=_ports(operation=operation, transactions=transactions, events=events),
    )

    assert result.applied == 1
    assert result.failures[0].transaction_id == invalid_id
    assert "not declared by the facts registry" in result.failures[0].reason
    assert (valid_transaction := transactions.catalogue.get(valid_id)) is not None
    assert valid_transaction.iva_category == IvaCategory("domestic_general")
    assert (invalid_transaction := transactions.catalogue.get(invalid_id)) is not None
    assert invalid_transaction.iva_category is None
    assert transactions.save_count == events.save_count == 1


def test_bulk_classification_refuses_a_catalogue_changed_after_its_snapshot(
    operation: PinnedAuthorityOperation,
) -> None:
    catalogue = _stored_catalogue("concurrent batch row")
    transaction_id = next(iter(catalogue.transactions))
    transactions, events = _repositories(catalogue)
    concurrent_transaction = catalogue.get(transaction_id)
    assert concurrent_transaction is not None
    concurrent_transaction = concurrent_transaction.model_copy(update={"notes": "edited elsewhere"})
    concurrent_catalogue = TransactionCatalogue.from_transactions((concurrent_transaction,))
    concurrent_revision: list[str] = []

    def write_concurrently_after_snapshot() -> None:
        transactions.replace_catalogue_from_concurrent_writer(concurrent_catalogue)
        concurrent_revision.append(transactions.revision_id)

    transactions.after_load_revisioned = write_concurrently_after_snapshot
    original_event_catalogue = events.catalogue
    original_event_revision = events.revision_id

    with pytest.raises(
        LedgerPersistenceConflictError,
        match="transaction catalogue changed since the snapshot was loaded",
    ):
        bulk_classify_from_csv(
            bucket_id=_BUCKET,
            csv_text=(f"transaction_id,classification,iva_category\n{transaction_id},BUSINESS,domestic_general\n"),
            actor="operator",
            ports=_ports(operation=operation, transactions=transactions, events=events),
        )

    assert transactions.catalogue == concurrent_catalogue
    assert transactions.catalogue.get(transaction_id) == concurrent_transaction
    assert concurrent_revision == [transactions.revision_id]
    assert transactions.save_count == 1
    assert events.catalogue == original_event_catalogue
    assert events.revision_id == original_event_revision
    assert events.save_count == 0


def test_none_and_declared_non_declarable_categories_are_not_remapped(
    operation: PinnedAuthorityOperation,
) -> None:
    transactions, events = _repositories(TransactionCatalogue())
    ports = _ports(operation=operation, transactions=transactions, events=events)

    actions_manual._require_declared_iva_category(_command(), ports=ports)
    actions_manual._require_declared_iva_category(_command(iva_category=IvaCategory("unknown")), ports=ports)
    actions_manual._require_declared_iva_category(
        _command(iva_category=IvaCategory("domestic_not_subject")),
        ports=ports,
    )
    actions_manual._require_declared_iva_category(
        _command(iva_category=IvaCategory("erroneous_invoice")),
        ports=ports,
    )


def test_stale_baseline_refuses_both_manual_edit_doors_before_a_write(
    operation: PinnedAuthorityOperation,
) -> None:
    """A detail snapshot must be current for direct and patch-shaped edits."""
    baseline_catalogue = _stored_catalogue("opened transaction")
    baseline = next(iter(baseline_catalogue.values()))
    concurrently_changed = baseline.model_copy(update={"notes": "edited elsewhere"})
    assert concurrently_changed.transaction_id == baseline.transaction_id
    latest_catalogue = TransactionCatalogue.from_transactions((concurrently_changed,))
    transactions, events = _repositories(latest_catalogue)
    ports = _ports(operation=operation, transactions=transactions, events=events)

    with pytest.raises(
        TransactionValidationError, match="transaction changed since it was opened; reopen it before editing"
    ):
        update_manual_transaction_fields(
            bucket_id=_BUCKET,
            transaction_id=baseline.transaction_id,
            patch=ManualLedgerTransactionPatch(iva_category=IvaCategory("domestic_general")),
            actor="operator",
            source_command="tui.ledger.transaction.update",
            ports=ports,
            expected_current=baseline,
            occurred_at=_NOW,
        )

    command = actions_manual._command_from_patch(
        bucket_id=_BUCKET,
        current=baseline,
        patch=ManualLedgerTransactionPatch(notes="operator correction"),
        actor="operator",
        source_command="tui.ledger.transaction.update",
    )
    with pytest.raises(
        TransactionValidationError, match="transaction changed since it was opened; reopen it before editing"
    ):
        actions_manual.update_manual_transaction(
            transaction_id=baseline.transaction_id,
            command=command,
            ports=ports,
            expected_current=baseline,
            occurred_at=_NOW,
        )

    assert transactions.catalogue == latest_catalogue
    assert transactions.save_count == events.save_count == 0


def test_current_baseline_uses_the_guarded_manual_update_co_commit(
    operation: PinnedAuthorityOperation,
) -> None:
    """A detail edit carries its opened row through the persistence boundary."""
    catalogue = _stored_catalogue("opened transaction")
    baseline = next(iter(catalogue.values()))
    transactions, events = _repositories(catalogue)

    updated = update_manual_transaction_fields(
        bucket_id=_BUCKET,
        transaction_id=baseline.transaction_id,
        patch=ManualLedgerTransactionPatch(notes="operator correction"),
        actor="operator",
        source_command="tui.ledger.transaction.update",
        ports=_ports(operation=operation, transactions=transactions, events=events),
        expected_current=baseline,
        occurred_at=_NOW,
    )

    assert transactions.guarded_replacement == (baseline, updated.transaction)
    assert transactions.catalogue.get(updated.ref.transaction_id) == updated.transaction
    assert transactions.save_count == events.save_count == 1


class _FailsOnSecondManifestRead:
    """Lets pre-write attachment validation run but catches a redundant post-write link."""

    def __init__(self, *, transaction_id: str) -> None:
        self._transaction_id = transaction_id
        self.manifest_reads = 0

    def load_manifest(self, attachment_id: str) -> Attachment:
        assert attachment_id == _ATTACHMENT_ID
        self.manifest_reads += 1
        if self.manifest_reads > 1:
            raise RuntimeError("unchanged attachment must not be reconciled after the transaction commits")
        return Attachment(
            attachment_id=_ATTACHMENT_ID,
            sha256=_ATTACHMENT_ID,
            kind=AttachmentKind.INVOICE_PDF,
            source=AttachmentSource.LOCAL_FILE,
            source_reference="operator-evidence",
            mime_type="application/pdf",
            bytes_size=1,
            captured_at=_NOW,
            linked_transaction_ids=(self._transaction_id,),
            bucket_id=_BUCKET,
        )

    def verify_blob(self, attachment_id: str) -> None:
        assert attachment_id == _ATTACHMENT_ID


def test_description_edit_does_not_reconcile_an_unchanged_attachment_after_commit(
    operation: PinnedAuthorityOperation,
) -> None:
    """A post-commit manifest failure must not turn a committed description edit into a reported failure."""
    baseline = actions_manual._transaction_from_command(
        _command(description="attached transaction", attachment_ids=(_ATTACHMENT_ID,)),
        occurred_at=_NOW,
    )
    transactions, events = _repositories(TransactionCatalogue.from_transactions((baseline,)))
    attachment_store = _FailsOnSecondManifestRead(transaction_id=baseline.transaction_id)
    ports = _ports(
        operation=operation,
        transactions=transactions,
        events=events,
        attachment_store=attachment_store,
    )

    updated = update_manual_transaction_fields(
        bucket_id=_BUCKET,
        transaction_id=baseline.transaction_id,
        patch=ManualLedgerTransactionPatch(notes="description correction"),
        actor="operator",
        source_command="tui.ledger.transaction.update",
        ports=ports,
        occurred_at=_NOW,
    )

    assert updated.transaction.notes == "description correction"
    assert transactions.catalogue.get(updated.ref.transaction_id) == updated.transaction
    assert transactions.save_count == events.save_count == 1
    assert attachment_store.manifest_reads == 1
