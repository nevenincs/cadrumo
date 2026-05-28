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
    IntracomOperationType,
    PayableInvoiceService,
    validate_eu_vat_id,
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


class TestEuVatIdValidator:
    """INTRACOM-001 — per-member-state EU VAT-ID format validation."""

    def test_de_valid_nine_digits_accepted(self) -> None:
        # Anti-tautology spec: DE must have exactly 9 digits after "DE"
        assert validate_eu_vat_id("DE345678901") == "DE345678901"

    def test_de_too_short_rejected(self) -> None:
        # Spec §6: DE12345 is too short (only 5 digits, needs 9)
        with pytest.raises(BusinessOperationInvoiceInputError, match="DE"):
            validate_eu_vat_id("DE12345")

    def test_de_non_digit_rejected(self) -> None:
        # Spec §6: DE34567890A contains a letter after DE — invalid for DE
        with pytest.raises(BusinessOperationInvoiceInputError, match="DE"):
            validate_eu_vat_id("DE34567890A")

    def test_fr_valid_alphanumeric_11_chars_accepted(self) -> None:
        # FR: 2 alphanumeric chars + 9 digits = 11 chars after prefix
        assert validate_eu_vat_id("FR12345678901") == "FR12345678901"

    def test_fr_letter_prefix_chars_accepted(self) -> None:
        assert validate_eu_vat_id("FRAB123456789") == "FRAB123456789"

    def test_it_eleven_digits_accepted(self) -> None:
        assert validate_eu_vat_id("IT12345678901") == "IT12345678901"

    def test_it_wrong_length_rejected(self) -> None:
        with pytest.raises(BusinessOperationInvoiceInputError, match="IT"):
            validate_eu_vat_id("IT1234567890")

    def test_ie_eight_chars_accepted(self) -> None:
        # IE: 7 digits + 1 letter
        assert validate_eu_vat_id("IE1234567A") == "IE1234567A"

    def test_ie_missing_letter_rejected(self) -> None:
        with pytest.raises(BusinessOperationInvoiceInputError, match="IE"):
            validate_eu_vat_id("IE12345678")

    def test_nl_twelve_chars_pattern_accepted(self) -> None:
        # NL: 9 digits + B + 2 digits
        assert validate_eu_vat_id("NL123456789B01") == "NL123456789B01"

    def test_nl_missing_b_separator_rejected(self) -> None:
        with pytest.raises(BusinessOperationInvoiceInputError, match="NL"):
            validate_eu_vat_id("NL12345678901")

    def test_es_valid_nif_format_accepted(self) -> None:
        assert validate_eu_vat_id("ESB12345678") == "ESB12345678"

    def test_gr_el_prefix_accepted(self) -> None:
        # Greece uses EL in VAT-IDs (not GR)
        assert validate_eu_vat_id("EL123456789") == "EL123456789"

    def test_non_eu_prefix_rejected(self) -> None:
        with pytest.raises(BusinessOperationInvoiceInputError, match="GB"):
            validate_eu_vat_id("GB123456789")

    def test_too_short_no_prefix_rejected(self) -> None:
        with pytest.raises(BusinessOperationInvoiceInputError):
            validate_eu_vat_id("DE")

    def test_whitespace_and_hyphens_stripped(self) -> None:
        # Normalisation: spaces and hyphens are stripped before matching
        assert validate_eu_vat_id("DE 345 678 901") == "DE345678901"

    def test_lowercase_input_normalised_to_upper(self) -> None:
        assert validate_eu_vat_id("de345678901") == "DE345678901"

    def test_anti_tautology_de_ten_digits_rejected(self) -> None:
        # Proves the DE pattern is not trivially permissive: 10 digits must fail
        with pytest.raises(BusinessOperationInvoiceInputError):
            validate_eu_vat_id("DE3456789012")


class TestIntracomFieldsPersistence:
    """INTRACOM-002 — intracom fields persist through JSONL roundtrip and default to None."""

    def test_intracom_fields_default_to_none(
        self, isolated_settings: Settings, secure_objects: SecureObjectRepository
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        result = svc.add(
            bucket_id="bucket-001",
            counterparty_nif="B12345678",
            invoice_number="INV-001",
            invoice_date="2025-03-15",
        )
        assert result.record.country_code is None
        assert result.record.eu_vat_id is None
        assert result.record.operation_type is None

    def test_intracom_fields_persist_and_roundtrip(
        self, isolated_settings: Settings, secure_objects: SecureObjectRepository
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        svc.add(
            bucket_id="bucket-001",
            counterparty_nif="B12345678",
            invoice_number="INV-001",
            invoice_date="2025-03-15",
            country_code="DE",
            eu_vat_id="DE345678901",
            operation_type=IntracomOperationType.E,
        )
        fresh_svc = _make_payable_svc(isolated_settings, secure_objects)
        records = fresh_svc.list_all(bucket_id="bucket-001")
        assert len(records) == 1
        record = records[0]
        assert record.country_code == "DE"
        assert record.eu_vat_id == "DE345678901"
        assert record.operation_type is IntracomOperationType.E


    def test_existing_record_without_intracom_fields_loads_as_none(
        self, isolated_settings: Settings, secure_objects: SecureObjectRepository, tmp_path: Path
    ) -> None:
        # Schema migration test: a JSONL record written before the intracom fields
        # were added (missing keys) must load with country_code=None etc.
        import json
        from datetime import UTC, datetime

        from aeat.application._storage_paths import storage_path
        from aeat.application.ledger._business_operation_invoice import (
            BusinessOperationInvoiceSourceKind,
        )

        bucket_id = "bucket-legacy"
        kind = BusinessOperationInvoiceSourceKind.PAYABLE_INVOICE
        path = storage_path(isolated_settings.aeat_invoices_dir / kind.value, bucket_id)
        # Write a record in the pre-intracom schema (no country_code / eu_vat_id / operation_type)
        legacy = {
            "invoice_id": "abc123",
            "source_kind": "payable_invoice",
            "bucket_id": bucket_id,
            "counterparty_nif": "B99999999",
            "counterparty_name": "",
            "invoice_number": "INV-LEGACY-001",
            "invoice_date": "2024-01-15",
            "currency": "EUR",
            "taxable_base": "500",
            "iva_rate": None,
            "iva_amount": "0",
            "total_amount": "500",
            "notes": "",
            "created_at": datetime.now(tz=UTC).isoformat(),
            "updated_at": datetime.now(tz=UTC).isoformat(),
        }
        path.write_text(json.dumps(legacy) + "\n", encoding="utf-8")

        svc = _make_payable_svc(isolated_settings, secure_objects)
        records = svc.list_all(bucket_id=bucket_id)
        assert len(records) == 1
        assert records[0].country_code is None
        assert records[0].eu_vat_id is None
        assert records[0].operation_type is None
        assert records[0].invoice_number == "INV-LEGACY-001"

    def test_anti_tautology_intracom_fields_actually_differ(
        self, isolated_settings: Settings, secure_objects: SecureObjectRepository
    ) -> None:
        # Proves the roundtrip test would fail if eu_vat_id were silently dropped:
        # two records with different eu_vat_id must not be equal.
        svc = _make_payable_svc(isolated_settings, secure_objects)
        r1 = svc.add(
            bucket_id="bucket-001",
            counterparty_nif="B12345678",
            invoice_number="INV-A",
            invoice_date="2025-03-15",
            country_code="DE",
            eu_vat_id="DE345678901",
            operation_type=IntracomOperationType.E,
        ).record
        r2 = svc.add(
            bucket_id="bucket-001",
            counterparty_nif="B12345678",
            invoice_number="INV-B",
            invoice_date="2025-03-15",
        ).record
        assert r1.eu_vat_id != r2.eu_vat_id
        assert r1.operation_type != r2.operation_type
