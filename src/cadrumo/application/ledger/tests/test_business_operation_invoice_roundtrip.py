"""Roundtrip persistence tests for business operation invoices."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import IntracomOperationType
from ....core.config import Settings
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


class TestUnifiedInvoiceAddRoundtrip:
    """Strict save->load->equality roundtrip for the unified invoice add path."""

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

        assert added.counterparty_name != ""
        assert added.notes != ""
        assert added.country_code is not None
        assert added.eu_iva_id is not None
        assert added.operation_type is not None
        assert added.iva_rate is not None

        fresh_svc = _make_collectible_svc(isolated_settings, secure_objects)
        reloaded = fresh_svc.view(bucket_id=_BUCKET_ID, invoice_id=added.invoice_id)
        assert reloaded == added

    def test_invoice_roundtrip_antitautology(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
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
