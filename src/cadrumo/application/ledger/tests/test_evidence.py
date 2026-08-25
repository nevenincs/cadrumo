"""Tests for the purchase invoice evidence CRUD service with bucket event emission."""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.persistence.storage.attachment import AttachmentStore
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....domain.attachments import load_attachment
from ....domain.buckets import BucketEventType
from ..evidence import (
    PurchaseInvoiceEvidencePatch,
    PurchaseInvoiceEvidenceService,
)
from ._evidence_test_support import _BUCKET_ID, _event_repo, _make_svc
from ._evidence_test_support import runtime_profile as runtime_profile
from ._ledger_value_fixtures import isolated_settings, pdf_file, secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "pdf_file", "runtime_profile", "secure_objects"]


class TestEvidenceEventEmission:
    """Verify each mutating verb emits the correct BucketEventType and returns the event id."""

    def test_add_emits_purchase_invoice_evidence_attached(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        pdf_file: Path,
    ) -> None:
        svc = _make_svc(isolated_settings, secure_objects)
        result = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_file)
        assert len(result.bucket_event_ids) == 1
        catalogue = _event_repo(secure_objects).load()
        event = catalogue.events[result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED
        assert event.object_id == result.record.evidence_id
        assert event.bucket_id == _BUCKET_ID

    def test_default_event_repository_uses_active_runtime_bucket(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        pdf_file: Path,
    ) -> None:
        svc = PurchaseInvoiceEvidenceService(settings=isolated_settings)

        result = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_file)

        catalogue = _event_repo(secure_objects).load()
        event = catalogue.events[result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED
        assert event.bucket_id == _BUCKET_ID

    def test_update_emits_purchase_invoice_evidence_replaced(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        pdf_file: Path,
    ) -> None:
        svc = _make_svc(isolated_settings, secure_objects)
        add_result = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_file)
        update_result = svc.update(
            bucket_id=_BUCKET_ID,
            evidence_id=add_result.record.evidence_id,
            patch=PurchaseInvoiceEvidencePatch(notes="updated"),
        )
        assert len(update_result.bucket_event_ids) == 1
        catalogue = _event_repo(secure_objects).load()
        event = catalogue.events[update_result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.PURCHASE_INVOICE_EVIDENCE_REPLACED
        assert event.object_id == add_result.record.evidence_id

    def test_remove_emits_purchase_invoice_evidence_detached(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        pdf_file: Path,
    ) -> None:
        svc = _make_svc(isolated_settings, secure_objects)
        add_result = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_file)
        remove_result = svc.remove(
            bucket_id=_BUCKET_ID,
            evidence_id=add_result.record.evidence_id,
        )
        assert len(remove_result.bucket_event_ids) == 1
        catalogue = _event_repo(secure_objects).load()
        event = catalogue.events[remove_result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED

    def test_add_result_carries_the_record(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        pdf_file: Path,
    ) -> None:
        svc = _make_svc(isolated_settings, secure_objects)
        result = svc.add(
            bucket_id=_BUCKET_ID,
            source_path=pdf_file,
            supplier="Acme S.L.",
            invoice_number="INV-001",
        )
        assert result.record.supplier == "Acme S.L."
        assert result.record.invoice_number == "INV-001"
        assert result.record.media_kind == "pdf"

    def test_add_persists_attachment_custody_and_ledger_provenance(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        pdf_file: Path,
    ) -> None:
        svc = _make_svc(isolated_settings, secure_objects)

        result = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_file, actor="operator-A")

        store = AttachmentStore(objects=secure_objects)
        manifest = load_attachment(store, result.record.attachment_id)
        assert store.read_bytes(manifest.sha256) == pdf_file.read_bytes()
        assert manifest.attachment_id == result.record.source_sha256
        assert manifest.bucket_id == _BUCKET_ID
        assert manifest.captured_by == "operator-A"
        assert manifest.source_command == "aeat app ledger evidence add"

    def test_remove_result_carries_the_removed_record(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        pdf_file: Path,
    ) -> None:
        svc = _make_svc(isolated_settings, secure_objects)
        add_result = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_file)
        remove_result = svc.remove(
            bucket_id=_BUCKET_ID,
            evidence_id=add_result.record.evidence_id,
        )
        assert remove_result.record == add_result.record
        assert svc.list_all(bucket_id=_BUCKET_ID) == ()
