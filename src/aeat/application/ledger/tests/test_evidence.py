"""Tests for the purchase invoice evidence CRUD service with bucket event emission."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....domain.buckets import BucketEventHistoryRepository, BucketEventType
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._evidence import (
    PurchaseInvoiceEvidenceInputError,
    PurchaseInvoiceEvidenceNotFoundError,
    PurchaseInvoiceEvidencePatch,
    PurchaseInvoiceEvidenceService,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "29292929-2929-4929-8929-292929292929"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile


@pytest.fixture
def isolated_settings(runtime_profile: TestRuntimeProfile) -> Settings:
    return runtime_profile.settings


@pytest.fixture
def secure_objects(runtime_profile: TestRuntimeProfile) -> SecureObjectRepository:
    return runtime_profile.repository


@pytest.fixture
def pdf_file(tmp_path: Path) -> Path:
    """A minimal real file with a .pdf extension that the service can hash."""
    p = tmp_path / "receipt.pdf"
    p.write_bytes(b"%PDF-1.4 test")
    return p


def _make_svc(isolated_settings: Settings, objects: SecureObjectRepository) -> PurchaseInvoiceEvidenceService:
    return PurchaseInvoiceEvidenceService(
        settings=isolated_settings,
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
    )


def _event_repo(objects: SecureObjectRepository) -> BucketEventHistoryRepository:
    return BucketEventHistoryRepository(objects=objects)


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


class TestEvidenceSecureStorage:
    def test_purchase_invoice_evidence_persists_in_secure_object_store(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        pdf_file: Path,
    ) -> None:
        svc = _make_svc(isolated_settings, secure_objects)

        result = svc.add(bucket_id=_BUCKET_ID, source_path=pdf_file, supplier="Acme S.L.")
        records = svc.list_all(bucket_id=_BUCKET_ID)

        assert records == (result.record,)
        assert not (isolated_settings.aeat_purchase_invoice_evidence_dir / f"{_BUCKET_ID}.jsonl").exists()
        raw_records = tuple(secure_objects.iter_all_records_raw())
        assert any(row.namespace == "aeat.application.ledger.purchase_invoice_evidence" for row in raw_records)


class TestEvidenceErrorPaths:
    def test_add_rejects_missing_file(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        svc = _make_svc(isolated_settings, secure_objects)
        with pytest.raises(PurchaseInvoiceEvidenceInputError, match="does not resolve to a readable file") as exc_info:
            svc.add(bucket_id=_BUCKET_ID, source_path=tmp_path / "ghost.pdf")
        # The refusal addresses the path, not the irrelevant 'evidence list' verb.
        assert exc_info.value.suggestion is not None
        assert "evidence list" not in exc_info.value.suggestion
        assert "path" in exc_info.value.suggestion.lower()

    def test_add_rejects_unsupported_extension(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
        tmp_path: Path,
    ) -> None:
        txt_file = tmp_path / "note.txt"
        txt_file.write_text("hello")
        svc = _make_svc(isolated_settings, secure_objects)
        with pytest.raises(PurchaseInvoiceEvidenceInputError, match="unsupported extension"):
            svc.add(bucket_id=_BUCKET_ID, source_path=txt_file)

    def test_update_raises_on_missing_id(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_svc(isolated_settings, secure_objects)
        with pytest.raises(PurchaseInvoiceEvidenceNotFoundError):
            svc.update(
                bucket_id=_BUCKET_ID,
                evidence_id="doesnotexist",
                patch=PurchaseInvoiceEvidencePatch(notes="x"),
            )

    def test_remove_raises_on_missing_id(
        self,
        isolated_settings: Settings,
        secure_objects: SecureObjectRepository,
    ) -> None:
        svc = _make_svc(isolated_settings, secure_objects)
        with pytest.raises(PurchaseInvoiceEvidenceNotFoundError):
            svc.remove(bucket_id=_BUCKET_ID, evidence_id="doesnotexist")
