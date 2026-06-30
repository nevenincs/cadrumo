"""Bucket-event emission tests for business operation invoice services."""

from __future__ import annotations

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....domain.buckets import BucketEventHistoryRepository, BucketEventType
from .._business_operation_invoice import BusinessOperationInvoicePatch, PayableInvoiceService
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


class TestPayableInvoiceEventEmission:
    """Verify that each mutating verb emits exactly one bucket event of the correct type."""

    def _event_repo(self, objects: SecureObjectRepository) -> BucketEventHistoryRepository:
        return BucketEventHistoryRepository(objects=objects)

    def test_add_emits_payable_invoice_created(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        result = svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B99999999",
            invoice_number="INV-EVENT-001",
            invoice_date="2025-04-01",
        )
        assert len(result.bucket_event_ids) == 1
        catalogue = self._event_repo(secure_objects).load()
        event = catalogue.events[result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.PAYABLE_INVOICE_CREATED
        assert event.object_id == result.record.invoice_id
        assert event.bucket_id == _BUCKET_ID

    def test_default_event_repository_uses_active_runtime_bucket(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = PayableInvoiceService(settings=isolated_settings)

        result = svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B99999999",
            invoice_number="INV-EVENT-DEFAULT",
            invoice_date="2025-04-01",
        )

        catalogue = self._event_repo(secure_objects).load()
        event = catalogue.events[result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.PAYABLE_INVOICE_CREATED
        assert event.bucket_id == _BUCKET_ID

    def test_update_emits_payable_invoice_updated(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        add_result = svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B99999999",
            invoice_number="INV-EVENT-002",
            invoice_date="2025-04-01",
        )
        update_result = svc.update(
            bucket_id=_BUCKET_ID,
            invoice_id=add_result.record.invoice_id,
            patch=BusinessOperationInvoicePatch(notes="event test"),
        )
        assert len(update_result.bucket_event_ids) == 1
        catalogue = self._event_repo(secure_objects).load()
        event = catalogue.events[update_result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.PAYABLE_INVOICE_UPDATED

    def test_remove_emits_payable_invoice_removed(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_payable_svc(isolated_settings, secure_objects)
        add_result = svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="B99999999",
            invoice_number="INV-EVENT-003",
            invoice_date="2025-04-01",
        )
        remove_result = svc.remove(
            bucket_id=_BUCKET_ID,
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
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_collectible_svc(isolated_settings, secure_objects)
        result = svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="C11111111",
            invoice_number="CINV-001",
            invoice_date="2025-05-01",
        )
        assert len(result.bucket_event_ids) == 1
        catalogue = self._event_repo(secure_objects).load()
        event = catalogue.events[result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.COLLECTIBLE_INVOICE_CREATED
        assert event.bucket_id == _BUCKET_ID

    def test_remove_emits_collectible_invoice_removed(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_collectible_svc(isolated_settings, secure_objects)
        add_result = svc.add(
            bucket_id=_BUCKET_ID,
            counterparty_nif="C11111111",
            invoice_number="CINV-002",
            invoice_date="2025-05-01",
        )
        remove_result = svc.remove(
            bucket_id=_BUCKET_ID,
            invoice_id=add_result.record.invoice_id,
        )
        assert len(remove_result.bucket_event_ids) == 1
        catalogue = self._event_repo(secure_objects).load()
        event = catalogue.events[remove_result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.COLLECTIBLE_INVOICE_REMOVED
