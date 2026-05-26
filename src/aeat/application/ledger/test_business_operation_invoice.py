"""Tests for the payable and collectible invoice noun-group CRUD services."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage.sql import SecureObjectRepository
from aeat.application.ledger._business_operation_invoice import (
    BusinessOperationInvoiceInputError,
    BusinessOperationInvoiceNotFoundError,
    BusinessOperationInvoicePatch,
    BusinessOperationInvoiceSourceKind,
    CollectibleInvoiceService,
    PayableInvoiceService,
)
from aeat.core.config import Settings
from aeat.domain.buckets import BucketEventHistoryRepository, BucketEventType
from aeat.tests.secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def isolated_settings(tmp_path: Path) -> Settings:
    """Fresh per-test settings rooted in a temp directory."""
    return Settings(aeat_invoices_dir=tmp_path / "invoices")


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="bucket-001") as profile:
        yield profile.repository


def _make_payable_svc(isolated_settings: Settings, objects: SecureObjectRepository) -> PayableInvoiceService:
    return PayableInvoiceService(
        settings=isolated_settings,
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
    )


def _make_collectible_svc(isolated_settings: Settings, objects: SecureObjectRepository) -> CollectibleInvoiceService:
    return CollectibleInvoiceService(
        settings=isolated_settings,
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
    )


class TestPayableInvoiceCrud:
    def test_add_creates_persisted_record_with_source_kind(
        self, isolated_settings: Settings, secure_objects: SecureObjectRepository
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        result = svc.add(
            bucket_id="bucket-001",
            counterparty_nif="B12345678",
            invoice_number="INV-2025-001",
            invoice_date="2025-03-15",
            taxable_base=Decimal("1000.00"),
            iva_amount=Decimal("210.00"),
            total_amount=Decimal("1210.00"),
        )
        record = result.record
        assert record.source_kind is BusinessOperationInvoiceSourceKind.PAYABLE_INVOICE
        assert record.counterparty_nif == "B12345678"
        assert record.taxable_base == Decimal("1000.00")
        assert len(record.invoice_id) == 16

    def test_list_returns_only_payable_invoices(
        self, isolated_settings: Settings, secure_objects: SecureObjectRepository
    ) -> None:
        payable_svc = _make_payable_svc(isolated_settings, secure_objects)
        collectible_svc = _make_collectible_svc(isolated_settings, secure_objects)
        payable_svc.add(
            bucket_id="bucket-001",
            counterparty_nif="B11111111",
            invoice_number="INV-1",
            invoice_date="2025-03-15",
        )
        collectible_svc.add(
            bucket_id="bucket-001",
            counterparty_nif="B22222222",
            invoice_number="INV-2",
            invoice_date="2025-03-16",
        )
        payable_records = payable_svc.list_all(bucket_id="bucket-001")
        collectible_records = collectible_svc.list_all(bucket_id="bucket-001")
        assert len(payable_records) == 1
        assert len(collectible_records) == 1
        assert payable_records[0].source_kind is BusinessOperationInvoiceSourceKind.PAYABLE_INVOICE
        assert collectible_records[0].source_kind is BusinessOperationInvoiceSourceKind.COLLECTIBLE_INVOICE

    def test_view_returns_record_by_full_id(
        self, isolated_settings: Settings, secure_objects: SecureObjectRepository
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        result = svc.add(
            bucket_id="bucket-001",
            counterparty_nif="B12345678",
            invoice_number="INV-2025-001",
            invoice_date="2025-03-15",
        )
        viewed = svc.view(bucket_id="bucket-001", invoice_id=result.record.invoice_id)
        assert viewed == result.record

    def test_view_resolves_unambiguous_prefix(
        self, isolated_settings: Settings, secure_objects: SecureObjectRepository
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        result = svc.add(
            bucket_id="bucket-001",
            counterparty_nif="B12345678",
            invoice_number="INV-001",
            invoice_date="2025-03-15",
        )
        prefix = result.record.invoice_id[:8]
        viewed = svc.view(bucket_id="bucket-001", invoice_id=prefix)
        assert viewed == result.record

    def test_view_refuses_on_unknown_id(
        self, isolated_settings: Settings, secure_objects: SecureObjectRepository
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        with pytest.raises(BusinessOperationInvoiceNotFoundError):
            svc.view(bucket_id="bucket-001", invoice_id="nonexistent")

    def test_update_overwrites_only_provided_fields(
        self, isolated_settings: Settings, secure_objects: SecureObjectRepository
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        add_result = svc.add(
            bucket_id="bucket-001",
            counterparty_nif="B12345678",
            counterparty_name="Acme S.L.",
            invoice_number="INV-001",
            invoice_date="2025-03-15",
            notes="initial notes",
        )
        patch = BusinessOperationInvoicePatch(
            notes="updated notes",
            total_amount=Decimal("500.00"),
        )
        update_result = svc.update(bucket_id="bucket-001", invoice_id=add_result.record.invoice_id, patch=patch)
        updated = update_result.record
        assert updated.notes == "updated notes"
        assert updated.total_amount == Decimal("500.00")
        assert updated.counterparty_name == "Acme S.L."
        assert updated.invoice_number == "INV-001"
        assert updated.updated_at >= add_result.record.updated_at

    def test_remove_deletes_record_and_returns_it(
        self, isolated_settings: Settings, secure_objects: SecureObjectRepository
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        add_result = svc.add(
            bucket_id="bucket-001",
            counterparty_nif="B12345678",
            invoice_number="INV-001",
            invoice_date="2025-03-15",
        )
        remove_result = svc.remove(bucket_id="bucket-001", invoice_id=add_result.record.invoice_id)
        assert remove_result.record == add_result.record
        assert svc.list_all(bucket_id="bucket-001") == ()
        with pytest.raises(BusinessOperationInvoiceNotFoundError):
            svc.view(bucket_id="bucket-001", invoice_id=add_result.record.invoice_id)


class TestPayableInvoiceEventEmission:
    """Verify that each mutating verb emits exactly one bucket event of the correct type."""

    def _event_repo(self, objects: SecureObjectRepository) -> BucketEventHistoryRepository:
        return BucketEventHistoryRepository(objects=objects)

    def test_add_emits_payable_invoice_created(
        self, isolated_settings: Settings, secure_objects: SecureObjectRepository
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        result = svc.add(
            bucket_id="bucket-001",
            counterparty_nif="B99999999",
            invoice_number="INV-EVENT-001",
            invoice_date="2025-04-01",
        )
        assert len(result.bucket_event_ids) == 1
        catalogue = self._event_repo(secure_objects).load()
        event = catalogue.events[result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.PAYABLE_INVOICE_CREATED
        assert event.object_id == result.record.invoice_id
        assert event.bucket_id == "bucket-001"

    def test_update_emits_payable_invoice_updated(
        self, isolated_settings: Settings, secure_objects: SecureObjectRepository
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        add_result = svc.add(
            bucket_id="bucket-001",
            counterparty_nif="B99999999",
            invoice_number="INV-EVENT-002",
            invoice_date="2025-04-01",
        )
        update_result = svc.update(
            bucket_id="bucket-001",
            invoice_id=add_result.record.invoice_id,
            patch=BusinessOperationInvoicePatch(notes="event test"),
        )
        assert len(update_result.bucket_event_ids) == 1
        catalogue = self._event_repo(secure_objects).load()
        event = catalogue.events[update_result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.PAYABLE_INVOICE_UPDATED

    def test_remove_emits_payable_invoice_removed(
        self, isolated_settings: Settings, secure_objects: SecureObjectRepository
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        add_result = svc.add(
            bucket_id="bucket-001",
            counterparty_nif="B99999999",
            invoice_number="INV-EVENT-003",
            invoice_date="2025-04-01",
        )
        remove_result = svc.remove(
            bucket_id="bucket-001",
            invoice_id=add_result.record.invoice_id,
        )
        assert len(remove_result.bucket_event_ids) == 1
        catalogue = self._event_repo(secure_objects).load()
        event = catalogue.events[remove_result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.PAYABLE_INVOICE_REMOVED


class TestCollectibleInvoiceEventEmission:
    """Verify that collectible invoice mutations emit the correct event types."""

    def _event_repo(self, objects: SecureObjectRepository) -> BucketEventHistoryRepository:
        return BucketEventHistoryRepository(objects=objects)

    def test_add_emits_collectible_invoice_created(
        self, isolated_settings: Settings, secure_objects: SecureObjectRepository
    ) -> None:
        svc = _make_collectible_svc(isolated_settings, secure_objects)
        result = svc.add(
            bucket_id="bucket-002",
            counterparty_nif="C11111111",
            invoice_number="CINV-001",
            invoice_date="2025-05-01",
        )
        assert len(result.bucket_event_ids) == 1
        catalogue = self._event_repo(secure_objects).load()
        event = catalogue.events[result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.COLLECTIBLE_INVOICE_CREATED
        assert event.bucket_id == "bucket-002"

    def test_remove_emits_collectible_invoice_removed(
        self, isolated_settings: Settings, secure_objects: SecureObjectRepository
    ) -> None:
        svc = _make_collectible_svc(isolated_settings, secure_objects)
        add_result = svc.add(
            bucket_id="bucket-002",
            counterparty_nif="C11111111",
            invoice_number="CINV-002",
            invoice_date="2025-05-01",
        )
        remove_result = svc.remove(
            bucket_id="bucket-002",
            invoice_id=add_result.record.invoice_id,
        )
        assert len(remove_result.bucket_event_ids) == 1
        catalogue = self._event_repo(secure_objects).load()
        event = catalogue.events[remove_result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.COLLECTIBLE_INVOICE_REMOVED


class TestPrefixCollisionRefusal:
    def test_ambiguous_prefix_refuses_with_full_id_set(
        self, isolated_settings: Settings, secure_objects: SecureObjectRepository
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)

        # invoice_id is a 32-hex-char UUID4 hex. Sixteen possible first
        # characters → seventeen records guarantee (pigeonhole) that
        # at least two share the same first hex character. Look up by
        # that shared character to drive the real ambiguous-prefix
        # refusal path without patching uuid.uuid4.
        minted: list[str] = []
        for index in range(17):
            result = svc.add(
                bucket_id="bucket-001",
                counterparty_nif=f"B{index:02d}",
                invoice_number=f"N{index:02d}",
                invoice_date="2025-03-15",
            )
            minted.append(result.record.invoice_id)

        first_chars: dict[str, str] = {}
        shared_prefix: str | None = None
        for invoice_id in minted:
            head = invoice_id[0]
            if head in first_chars:
                shared_prefix = head
                break
            first_chars[head] = invoice_id
        assert shared_prefix is not None, "pigeonhole guarantee violated"

        with pytest.raises(BusinessOperationInvoiceInputError, match="ambiguous"):
            svc.view(bucket_id="bucket-001", invoice_id=shared_prefix)


class TestBucketIsolation:
    def test_records_are_bucket_scoped(
        self, isolated_settings: Settings, secure_objects: SecureObjectRepository
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        svc.add(bucket_id="bucket-A", counterparty_nif="B1", invoice_number="N1", invoice_date="2025-03-15")
        svc.add(bucket_id="bucket-B", counterparty_nif="B2", invoice_number="N2", invoice_date="2025-03-15")
        a_records = svc.list_all(bucket_id="bucket-A")
        b_records = svc.list_all(bucket_id="bucket-B")
        assert len(a_records) == 1
        assert len(b_records) == 1
        assert a_records[0].counterparty_nif == "B1"
        assert b_records[0].counterparty_nif == "B2"


class TestRecordImmutability:
    def test_record_is_frozen(self, isolated_settings: Settings, secure_objects: SecureObjectRepository) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        result = svc.add(
            bucket_id="bucket-001",
            counterparty_nif="B12345678",
            invoice_number="INV-001",
            invoice_date="2025-03-15",
        )
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            setattr(result.record, "notes", "mutated")  # noqa: B010 — exercise frozen-model __setattr__


class TestRoundTripPersistence:
    def test_jsonl_round_trips_decimals(
        self, isolated_settings: Settings, secure_objects: SecureObjectRepository
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        add_result = svc.add(
            bucket_id="bucket-001",
            counterparty_nif="B12345678",
            invoice_number="INV-001",
            invoice_date="2025-03-15",
            taxable_base=Decimal("1234.56"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("259.26"),
            total_amount=Decimal("1493.82"),
        )
        fresh_svc = _make_payable_svc(isolated_settings, secure_objects)
        records = fresh_svc.list_all(bucket_id="bucket-001")
        assert len(records) == 1
        assert records[0].invoice_id == add_result.record.invoice_id
        assert records[0].taxable_base == Decimal("1234.56")
        assert records[0].iva_rate == Decimal("0.21")
