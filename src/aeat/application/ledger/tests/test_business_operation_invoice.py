"""Tests for the payable and collectible invoice noun-group CRUD services."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....adapters.persistence.storage.errors import StorageValidationError
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import IntracomOperationType
from ....core.config import Settings
from .._business_operation_invoice import (
    BusinessOperationInvoice,
    BusinessOperationInvoiceDirection,
    BusinessOperationInvoiceInputError,
    BusinessOperationInvoiceNotFoundError,
    BusinessOperationInvoicePatch,
)
from ._business_operation_invoice_support import (
    _BUCKET_ID,
    _make_collectible_svc,
    _make_payable_svc,
)
from ._business_operation_invoice_support import (
    isolated_settings as isolated_settings,
)
from ._business_operation_invoice_support import (
    runtime_profile as runtime_profile,
)
from ._business_operation_invoice_support import (
    secure_objects as secure_objects,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

__all__ = ["isolated_settings", "runtime_profile", "secure_objects"]


class TestPayableInvoiceCrud:
    def test_add_creates_persisted_record_with_source_kind(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        result = svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B12345678",
            invoice_number="INV-2025-001",
            invoice_date="2025-03-15",
            taxable_base=Decimal("1000.00"),
            iva_amount=Decimal("210.00"),
            total_amount=Decimal("1210.00"),
        )
        record = result.record
        assert record.source_kind is BusinessOperationInvoiceDirection.PAYABLE_INVOICE
        assert record.counterparty_nif == "B12345678"
        assert record.taxable_base == Decimal("1000.00")
        assert len(record.invoice_id) == 16

    def test_list_returns_only_payable_invoices(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        payable_svc = _make_payable_svc(isolated_settings, secure_objects)
        collectible_svc = _make_collectible_svc(isolated_settings, secure_objects)
        payable_svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B11111111",
            invoice_number="INV-1",
            invoice_date="2025-03-15",
        )
        collectible_svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B22222222",
            invoice_number="INV-2",
            invoice_date="2025-03-16",
        )
        payable_records = payable_svc.list_all(bucket_id=_BUCKET_ID)
        collectible_records = collectible_svc.list_all(bucket_id=_BUCKET_ID)
        assert len(payable_records) == 1
        assert len(collectible_records) == 1
        assert payable_records[0].source_kind is BusinessOperationInvoiceDirection.PAYABLE_INVOICE
        assert collectible_records[0].source_kind is BusinessOperationInvoiceDirection.COLLECTIBLE_INVOICE

    def test_view_returns_record_by_full_id(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        result = svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B12345678",
            invoice_number="INV-2025-001",
            invoice_date="2025-03-15",
        )
        viewed = svc.view(bucket_id=_BUCKET_ID, invoice_id=result.record.invoice_id)
        assert viewed == result.record

    def test_view_resolves_unambiguous_prefix(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        result = svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B12345678",
            invoice_number="INV-001",
            invoice_date="2025-03-15",
        )
        prefix = result.record.invoice_id[:8]
        viewed = svc.view(bucket_id=_BUCKET_ID, invoice_id=prefix)
        assert viewed == result.record

    def test_view_refuses_on_unknown_id(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        with pytest.raises(BusinessOperationInvoiceNotFoundError):
            svc.view(bucket_id=_BUCKET_ID, invoice_id="nonexistent")

    def test_update_overwrites_only_provided_fields(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        add_result = svc.add(
            bucket_id=_BUCKET_ID,
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
        update_result = svc.update(bucket_id=_BUCKET_ID, invoice_id=add_result.record.invoice_id, patch=patch)
        updated = update_result.record
        assert updated.notes == "updated notes"
        assert updated.total_amount == Decimal("500.00")
        assert updated.counterparty_name == "Acme S.L."
        assert updated.invoice_number == "INV-001"
        assert updated.updated_at >= add_result.record.updated_at

    def test_remove_deletes_record_and_returns_it(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        add_result = svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B12345678",
            invoice_number="INV-001",
            invoice_date="2025-03-15",
        )
        remove_result = svc.remove(bucket_id=_BUCKET_ID, invoice_id=add_result.record.invoice_id)
        assert remove_result.record == add_result.record
        assert svc.list_all(bucket_id=_BUCKET_ID) == ()
        with pytest.raises(BusinessOperationInvoiceNotFoundError):
            svc.view(bucket_id=_BUCKET_ID, invoice_id=add_result.record.invoice_id)


class TestPrefixCollisionRefusal:
    def test_ambiguous_prefix_refuses_with_full_id_set(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
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
                bucket_id=_BUCKET_ID,
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
            svc.view(bucket_id=_BUCKET_ID, invoice_id=shared_prefix)


class TestSourceKindIsolation:
    def test_records_are_source_kind_scoped(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        payable_svc = _make_payable_svc(isolated_settings, secure_objects)
        collectible_svc = _make_collectible_svc(isolated_settings, secure_objects)
        payable_svc.add(bucket_id=_BUCKET_ID, counterparty_nif="B1", invoice_number="N1", invoice_date="2025-03-15")
        collectible_svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B2",
            invoice_number="N2",
            invoice_date="2025-03-15",
        )
        payable_records = payable_svc.list_all(bucket_id=_BUCKET_ID)
        collectible_records = collectible_svc.list_all(bucket_id=_BUCKET_ID)
        assert len(payable_records) == 1
        assert len(collectible_records) == 1
        assert payable_records[0].counterparty_nif == "B1"
        assert collectible_records[0].counterparty_nif == "B2"

    def test_non_active_bucket_fails_closed(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)

        with pytest.raises(StorageValidationError, match="not ready"):
            svc.add(bucket_id="bucket-002", counterparty_nif="B2", invoice_number="N2", invoice_date="2025-03-15")


class TestRecordImmutability:
    def test_record_is_frozen(self, isolated_settings: Settings, secure_objects: SecureObjectRepository) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        result = svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B12345678",
            invoice_number="INV-001",
            invoice_date="2025-03-15",
        )
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            result.record.notes = "mutated"


class TestRoundTripPersistence:
    def test_secure_object_round_trips_decimals(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        add_result = svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B12345678",
            invoice_number="INV-001",
            invoice_date="2025-03-15",
            taxable_base=Decimal("1234.56"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("259.26"),
            total_amount=Decimal("1493.82"),
        )
        fresh_svc = _make_payable_svc(isolated_settings, secure_objects)
        records = fresh_svc.list_all(bucket_id=_BUCKET_ID)
        assert len(records) == 1
        assert records[0].invoice_id == add_result.record.invoice_id
        assert records[0].taxable_base == Decimal("1234.56")
        assert records[0].iva_rate == Decimal("0.21")


class TestIntracomFieldsPersistence:
    """INTRACOM-002 — intracom fields persist through encrypted roundtrip."""

    def test_intracom_fields_default_to_none(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        result = svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B12345678",
            invoice_number="INV-001",
            invoice_date="2025-03-15",
        )
        assert result.record.country_code is None
        assert result.record.eu_iva_id is None
        assert result.record.operation_type is None

    def test_intracom_fields_are_required_nullable_schema_keys(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        result = svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B12345678",
            invoice_number="INV-001",
            invoice_date="2025-03-15",
        )
        payload = result.record.model_dump()
        for key in ("country_code", "eu_iva_id", "operation_type"):
            del payload[key]

        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Field required"):
            BusinessOperationInvoice.model_validate(payload)

    def test_intracom_fields_persist_and_roundtrip(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B12345678",
            invoice_number="INV-001",
            invoice_date="2025-03-15",
            country_code="DE",
            eu_iva_id="DE345678901",
            operation_type=IntracomOperationType.E,
        )
        fresh_svc = _make_payable_svc(isolated_settings, secure_objects)
        records = fresh_svc.list_all(bucket_id=_BUCKET_ID)
        assert len(records) == 1
        record = records[0]
        assert record.country_code == "DE"
        assert record.eu_iva_id == "DE345678901"
        assert record.operation_type is IntracomOperationType.E

    def test_invoice_persistence_writes_secure_object_not_jsonl(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)

        result = svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B12345678",
            invoice_number="INV-SECURE-001",
            invoice_date="2025-03-15",
        )
        records = svc.list_all(bucket_id=_BUCKET_ID)

        assert records == (result.record,)
        assert not (isolated_settings.aeat_invoices_dir / "payable_invoice" / f"{_BUCKET_ID}.jsonl").exists()
        raw_records = tuple(secure_objects.iter_all_records_raw())
        assert any(row.namespace == "aeat.application.ledger.business_operation_invoices" for row in raw_records)

    def test_anti_tautology_intracom_fields_actually_differ(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        # Proves the roundtrip test would fail if eu_iva_id were silently dropped:
        # two records with different eu_iva_id must not be equal.
        svc = _make_payable_svc(isolated_settings, secure_objects)
        r1 = svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B12345678",
            invoice_number="INV-A",
            invoice_date="2025-03-15",
            country_code="DE",
            eu_iva_id="DE345678901",
            operation_type=IntracomOperationType.E,
        ).record
        r2 = svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B12345678",
            invoice_number="INV-B",
            invoice_date="2025-03-15",
        ).record
        assert r1.eu_iva_id != r2.eu_iva_id
        assert r1.operation_type != r2.operation_type


class TestUnifiedInvoiceAddRoundtrip:
    """C4 ledger-invoice-unification: strict save->load->equality roundtrip for
    the unified ``invoice add`` write path against the encrypted
    ``LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE``, with every defaultable
    field (incl. the intracom EU triple and notes) populated non-default, plus
    an anti-tautology proof."""

    def test_invoice_add_roundtrip_all_fields(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_collectible_svc(isolated_settings, secure_objects)
        added = svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B87654321",
            invoice_number="ISS-2026-042",
            invoice_date="2026-02-14",
            counterparty_name="Kunde GmbH",
            currency="EUR",
            taxable_base=Decimal("2500.55"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("525.12"),
            total_amount=Decimal("3025.67"),
            notes="non-default operator notes",
            country_code="DE",
            eu_iva_id="DE345678901",
            operation_type=IntracomOperationType.S,
        ).record

        # Every defaultable field carries a non-default value, so a
        # save-drops / load-re-defaults regression cannot hide.
        assert added.counterparty_name != ""
        assert added.notes != ""
        assert added.country_code is not None
        assert added.eu_iva_id is not None
        assert added.operation_type is not None
        assert added.iva_rate is not None

        # Reload through a FRESH service against the same encrypted secure
        # objects and assert strict pydantic equality across the boundary.
        fresh_svc = _make_collectible_svc(isolated_settings, secure_objects)
        reloaded = fresh_svc.view(bucket_id=_BUCKET_ID, invoice_id=added.invoice_id)
        assert reloaded == added

    def test_invoice_roundtrip_antitautology(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        # Save a record carrying the EU triple, then rewrite the persisted
        # secure-object document with the SAME record minus its eu_iva_id and
        # operation_type. Reloading must surface STRICT INEQUALITY against the
        # original — proving the roundtrip would fail if the boundary silently
        # dropped those fields (otherwise the original would already read None
        # and the two would compare equal).
        from .._business_operation_invoice import (
            BusinessOperationInvoiceDirection,
            BusinessOperationInvoiceDocument,
            BusinessOperationInvoiceRepository,
        )

        svc = _make_collectible_svc(isolated_settings, secure_objects)
        original = svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B87654321",
            invoice_number="ISS-ANTITAUT",
            invoice_date="2026-02-14",
            country_code="DE",
            eu_iva_id="DE345678901",
            operation_type=IntracomOperationType.S,
        ).record

        repository = BusinessOperationInvoiceRepository(objects=secure_objects)
        key = f"{_BUCKET_ID}:{BusinessOperationInvoiceDirection.COLLECTIBLE_INVOICE.value}"
        document = repository.load(key)
        assert document is not None
        tampered_record = original.model_copy(update={"eu_iva_id": None, "operation_type": None})
        repository.save(
            BusinessOperationInvoiceDocument(
                bucket_id=_BUCKET_ID,
                source_kind=BusinessOperationInvoiceDirection.COLLECTIBLE_INVOICE,
                records=(tampered_record,),
            ),
        )

        fresh_svc = _make_collectible_svc(isolated_settings, secure_objects)
        reloaded = fresh_svc.view(bucket_id=_BUCKET_ID, invoice_id=original.invoice_id)
        assert reloaded != original
        assert reloaded.eu_iva_id is None
        assert original.eu_iva_id == "DE345678901"
