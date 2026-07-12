"""Intracom and secure persistence tests for business operation invoices."""

from __future__ import annotations

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import IntracomOperationType
from ....core.config import Settings
from .._business_operation_invoice import BusinessOperationInvoice
from ._business_operation_invoice_support import (
    _BUCKET_ID,
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


class TestIntracomFieldsPersistence:
    """INTRACOM-002: intracom fields persist through encrypted roundtrip."""

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
