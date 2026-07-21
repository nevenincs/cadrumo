"""Tests for the payable and collectible invoice noun-group CRUD services."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from .._business_operation_invoice import (
    BusinessOperationInvoiceDirection,
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


class TestBusinessInvoiceCurrencyConversion:
    """A slim invoice feeds the same modelo bindings as the rich catalogue one,
    so a foreign-currency record must carry its euro equivalent or be withheld."""

    def test_foreign_currency_add_stamps_the_ecb_conversion(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        from datetime import date

        from ....adapters.outbound.fx import EcbReferenceRateProvider
        from ....tests.ecb_stub import ecb_csv_fetch

        # ECB EXR.D.GBP.EUR.SP00.A 2025-03-14 = 0.84183 (1 EUR = 0.84183 GBP).
        quote = Decimal("0.84183")
        provider = EcbReferenceRateProvider(fetch=ecb_csv_fetch({"GBP": {date(2025, 3, 14): quote}}))
        svc = _make_payable_svc(isolated_settings, secure_objects)

        result = svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B12345678",
            invoice_number="GB-2025-001",
            invoice_date="2025-03-14",
            currency="GBP",
            taxable_base=Decimal("1000.00"),
            total_amount=Decimal("1000.00"),
            rate_provider=provider,
        )

        record = result.record
        assert record.fx_rate == Decimal("1") / quote
        assert record.fx_rate_date == "2025-03-14"
        assert record.total_amount_eur == Decimal("1187.89")
        # Native amount untouched; the euro value is a derived view.
        assert record.total_amount == Decimal("1000.00")

    def test_unresolvable_rate_leaves_the_record_unconverted(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        """No rate means no euro value -- never the foreign face value as euro."""
        from ....adapters.outbound.fx import EcbReferenceRateProvider
        from ....tests.ecb_stub import ecb_csv_fetch

        provider = EcbReferenceRateProvider(fetch=ecb_csv_fetch({}))
        svc = _make_payable_svc(isolated_settings, secure_objects)

        result = svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B12345678",
            invoice_number="GB-2025-002",
            invoice_date="2025-03-14",
            currency="GBP",
            taxable_base=Decimal("1000.00"),
            total_amount=Decimal("1000.00"),
            rate_provider=provider,
        )

        assert result.record.fx_rate is None
        assert result.record.total_amount_eur is None

    def test_euro_add_carries_no_conversion_stamp(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)

        result = svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B12345678",
            invoice_number="ES-2025-001",
            invoice_date="2025-03-14",
            taxable_base=Decimal("1000.00"),
            total_amount=Decimal("1210.00"),
        )

        assert result.record.fx_rate is None
        assert result.record.fx_rate_date is None
        assert result.record.total_amount_eur == Decimal("1210.00")
