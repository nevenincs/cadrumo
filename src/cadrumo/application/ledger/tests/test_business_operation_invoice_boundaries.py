"""Boundary and invariant tests for business-operation invoice services."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage.errors import StorageValidationError
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from .._business_operation_invoice import BusinessOperationInvoiceInputError
from ._business_operation_invoice_support import (
    _BUCKET_ID,
    _make_collectible_svc,
    _make_payable_svc,
)
from ._business_operation_invoice_support import isolated_settings as isolated_settings
from ._business_operation_invoice_support import runtime_profile as runtime_profile
from ._business_operation_invoice_support import secure_objects as secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "runtime_profile", "secure_objects"]


class TestPrefixCollisionRefusal:
    def test_ambiguous_prefix_refuses_with_full_id_set(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)

        # invoice_id is a 32-hex-char UUID4 hex. Sixteen possible first
        # characters means seventeen real records guarantee a repeated first
        # character, driving ambiguity without patching uuid.uuid4.
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
        assert shared_prefix is not None, "finite prefix-space guarantee violated"

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

        with pytest.raises(ValidationError):
            result.record.notes = "mutated"
