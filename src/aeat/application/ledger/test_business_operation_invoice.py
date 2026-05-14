"""Tests for the payable and collectible invoice noun-group CRUD services."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from aeat.application.ledger._business_operation_invoice import (
    BusinessOperationInvoice,
    BusinessOperationInvoiceInputError,
    BusinessOperationInvoiceNotFoundError,
    BusinessOperationInvoicePatch,
    BusinessOperationInvoiceSourceKind,
    CollectibleInvoiceService,
    PayableInvoiceService,
)
from aeat.core.config import Settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def isolated_settings(tmp_path: Path) -> Settings:
    """Fresh per-test settings rooted in a temp directory."""
    return Settings(aeat_invoices_dir=tmp_path / "invoices")


class TestPayableInvoiceCrud:
    def test_add_creates_persisted_record_with_source_kind(self, isolated_settings: Settings) -> None:
        svc = PayableInvoiceService(settings=isolated_settings)
        record = svc.add(
            bucket_id="bucket-001",
            counterparty_nif="B12345678",
            invoice_number="INV-2025-001",
            invoice_date="2025-03-15",
            taxable_base=Decimal("1000.00"),
            iva_amount=Decimal("210.00"),
            total_amount=Decimal("1210.00"),
        )
        assert record.source_kind is BusinessOperationInvoiceSourceKind.PAYABLE_INVOICE
        assert record.counterparty_nif == "B12345678"
        assert record.taxable_base == Decimal("1000.00")
        assert len(record.invoice_id) == 16

    def test_list_returns_only_payable_invoices(self, isolated_settings: Settings) -> None:
        payable_svc = PayableInvoiceService(settings=isolated_settings)
        collectible_svc = CollectibleInvoiceService(settings=isolated_settings)
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

    def test_view_returns_record_by_full_id(self, isolated_settings: Settings) -> None:
        svc = PayableInvoiceService(settings=isolated_settings)
        added = svc.add(
            bucket_id="bucket-001",
            counterparty_nif="B12345678",
            invoice_number="INV-2025-001",
            invoice_date="2025-03-15",
        )
        viewed = svc.view(bucket_id="bucket-001", invoice_id=added.invoice_id)
        assert viewed == added

    def test_view_resolves_unambiguous_prefix(self, isolated_settings: Settings) -> None:
        svc = PayableInvoiceService(settings=isolated_settings)
        added = svc.add(
            bucket_id="bucket-001",
            counterparty_nif="B12345678",
            invoice_number="INV-001",
            invoice_date="2025-03-15",
        )
        prefix = added.invoice_id[:8]
        viewed = svc.view(bucket_id="bucket-001", invoice_id=prefix)
        assert viewed == added

    def test_view_refuses_on_unknown_id(self, isolated_settings: Settings) -> None:
        svc = PayableInvoiceService(settings=isolated_settings)
        with pytest.raises(BusinessOperationInvoiceNotFoundError):
            svc.view(bucket_id="bucket-001", invoice_id="nonexistent")

    def test_update_overwrites_only_provided_fields(self, isolated_settings: Settings) -> None:
        svc = PayableInvoiceService(settings=isolated_settings)
        added = svc.add(
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
        updated = svc.update(bucket_id="bucket-001", invoice_id=added.invoice_id, patch=patch)
        assert updated.notes == "updated notes"
        assert updated.total_amount == Decimal("500.00")
        assert updated.counterparty_name == "Acme S.L."
        assert updated.invoice_number == "INV-001"
        assert updated.updated_at >= added.updated_at

    def test_remove_deletes_record_and_returns_it(self, isolated_settings: Settings) -> None:
        svc = PayableInvoiceService(settings=isolated_settings)
        added = svc.add(
            bucket_id="bucket-001",
            counterparty_nif="B12345678",
            invoice_number="INV-001",
            invoice_date="2025-03-15",
        )
        removed = svc.remove(bucket_id="bucket-001", invoice_id=added.invoice_id)
        assert removed == added
        assert svc.list_all(bucket_id="bucket-001") == ()
        with pytest.raises(BusinessOperationInvoiceNotFoundError):
            svc.view(bucket_id="bucket-001", invoice_id=added.invoice_id)


class TestPrefixCollisionRefusal:
    def test_ambiguous_prefix_refuses_with_full_id_set(self, isolated_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
        # Force two records to share the same prefix by stubbing uuid4 hex output.
        svc = PayableInvoiceService(settings=isolated_settings)
        ids = iter(["abcdef1234567890fedcba0987654321", "abcdef1234567890ffffffffffffffff"])

        class _StubUuid:
            def __init__(self) -> None:
                self.hex = next(ids)

        monkeypatch.setattr("aeat.application.ledger._business_operation_invoice.uuid.uuid4", _StubUuid)
        svc.add(bucket_id="bucket-001", counterparty_nif="B1", invoice_number="N1", invoice_date="2025-03-15")
        svc.add(bucket_id="bucket-001", counterparty_nif="B2", invoice_number="N2", invoice_date="2025-03-15")
        with pytest.raises(BusinessOperationInvoiceInputError, match="ambiguous"):
            svc.view(bucket_id="bucket-001", invoice_id="abcdef12")


class TestBucketIsolation:
    def test_records_are_bucket_scoped(self, isolated_settings: Settings) -> None:
        svc = PayableInvoiceService(settings=isolated_settings)
        svc.add(bucket_id="bucket-A", counterparty_nif="B1", invoice_number="N1", invoice_date="2025-03-15")
        svc.add(bucket_id="bucket-B", counterparty_nif="B2", invoice_number="N2", invoice_date="2025-03-15")
        a_records = svc.list_all(bucket_id="bucket-A")
        b_records = svc.list_all(bucket_id="bucket-B")
        assert len(a_records) == 1
        assert len(b_records) == 1
        assert a_records[0].counterparty_nif == "B1"
        assert b_records[0].counterparty_nif == "B2"


class TestRecordImmutability:
    def test_record_is_frozen(self, isolated_settings: Settings) -> None:
        svc = PayableInvoiceService(settings=isolated_settings)
        record = svc.add(
            bucket_id="bucket-001",
            counterparty_nif="B12345678",
            invoice_number="INV-001",
            invoice_date="2025-03-15",
        )
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            record.notes = "mutated"  # type: ignore[misc]


class TestRoundTripPersistence:
    def test_jsonl_round_trips_decimals(self, isolated_settings: Settings) -> None:
        svc = PayableInvoiceService(settings=isolated_settings)
        added = svc.add(
            bucket_id="bucket-001",
            counterparty_nif="B12345678",
            invoice_number="INV-001",
            invoice_date="2025-03-15",
            taxable_base=Decimal("1234.56"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("259.26"),
            total_amount=Decimal("1493.82"),
        )
        # New service instance forces re-load from disk.
        fresh_svc = PayableInvoiceService(settings=isolated_settings)
        records = fresh_svc.list_all(bucket_id="bucket-001")
        assert len(records) == 1
        assert records[0].invoice_id == added.invoice_id
        assert records[0].taxable_base == Decimal("1234.56")
        assert records[0].iva_rate == Decimal("0.21")
