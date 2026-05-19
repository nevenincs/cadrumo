"""Tests for the purchase invoice evidence CRUD service with bucket event emission."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.adapters.persistence.storage.sql import SecureObjectRepository, create_engine_from_settings
from aeat.adapters.persistence.storage.sql._orm import Base
from aeat.application.ledger._evidence import (
    PurchaseInvoiceEvidenceInputError,
    PurchaseInvoiceEvidenceNotFoundError,
    PurchaseInvoiceEvidencePatch,
    PurchaseInvoiceEvidenceService,
)
from aeat.core.config import Settings
from aeat.domain.buckets import BucketEventHistoryRepository, BucketEventType

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def isolated_settings(tmp_path: Path) -> Settings:
    return Settings(aeat_purchase_invoice_evidence_dir=tmp_path / "evidence")


@pytest.fixture
def secure_engine(tmp_path: Path) -> Iterator[Engine]:
    provider = EphemeralMasterKeyProvider()
    with provider:
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
        )
        Base.metadata.create_all(engine)
        try:
            yield engine
        finally:
            engine.dispose()


@pytest.fixture
def pdf_file(tmp_path: Path) -> Path:
    """A minimal real file with a .pdf extension that the service can hash."""
    p = tmp_path / "receipt.pdf"
    p.write_bytes(b"%PDF-1.4 test")
    return p


def _make_svc(isolated_settings: Settings, engine: Engine) -> PurchaseInvoiceEvidenceService:
    objects = SecureObjectRepository(engine=engine)
    return PurchaseInvoiceEvidenceService(
        settings=isolated_settings,
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
    )


def _event_repo(engine: Engine) -> BucketEventHistoryRepository:
    return BucketEventHistoryRepository(objects=SecureObjectRepository(engine=engine))


class TestEvidenceEventEmission:
    """Verify each mutating verb emits the correct BucketEventType and returns the event id."""

    def test_add_emits_purchase_invoice_evidence_attached(
        self, isolated_settings: Settings, secure_engine: Engine, pdf_file: Path
    ) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        result = svc.add(bucket_id="bucket-001", source_path=pdf_file)
        assert len(result.bucket_event_ids) == 1
        catalogue = _event_repo(secure_engine).load()
        event = catalogue.events[result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED
        assert event.object_id == result.record.evidence_id
        assert event.bucket_id == "bucket-001"

    def test_update_emits_purchase_invoice_evidence_replaced(
        self, isolated_settings: Settings, secure_engine: Engine, pdf_file: Path
    ) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        add_result = svc.add(bucket_id="bucket-001", source_path=pdf_file)
        update_result = svc.update(
            bucket_id="bucket-001",
            evidence_id=add_result.record.evidence_id,
            patch=PurchaseInvoiceEvidencePatch(notes="updated"),
        )
        assert len(update_result.bucket_event_ids) == 1
        catalogue = _event_repo(secure_engine).load()
        event = catalogue.events[update_result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.PURCHASE_INVOICE_EVIDENCE_REPLACED
        assert event.object_id == add_result.record.evidence_id

    def test_remove_emits_purchase_invoice_evidence_detached(
        self, isolated_settings: Settings, secure_engine: Engine, pdf_file: Path
    ) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        add_result = svc.add(bucket_id="bucket-001", source_path=pdf_file)
        remove_result = svc.remove(
            bucket_id="bucket-001",
            evidence_id=add_result.record.evidence_id,
        )
        assert len(remove_result.bucket_event_ids) == 1
        catalogue = _event_repo(secure_engine).load()
        event = catalogue.events[remove_result.bucket_event_ids[0]]
        assert event.event_type is BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED

    def test_add_result_carries_the_record(
        self, isolated_settings: Settings, secure_engine: Engine, pdf_file: Path
    ) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        result = svc.add(
            bucket_id="bucket-001",
            source_path=pdf_file,
            supplier="Acme S.L.",
            invoice_number="INV-001",
        )
        assert result.record.supplier == "Acme S.L."
        assert result.record.invoice_number == "INV-001"
        assert result.record.media_kind == "pdf"

    def test_remove_result_carries_the_removed_record(
        self, isolated_settings: Settings, secure_engine: Engine, pdf_file: Path
    ) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        add_result = svc.add(bucket_id="bucket-001", source_path=pdf_file)
        remove_result = svc.remove(
            bucket_id="bucket-001",
            evidence_id=add_result.record.evidence_id,
        )
        assert remove_result.record == add_result.record
        assert svc.list_all(bucket_id="bucket-001") == ()


class TestEvidenceErrorPaths:
    def test_add_rejects_missing_file(self, isolated_settings: Settings, secure_engine: Engine, tmp_path: Path) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        with pytest.raises(PurchaseInvoiceEvidenceInputError, match="not a readable file"):
            svc.add(bucket_id="b1", source_path=tmp_path / "ghost.pdf")

    def test_add_rejects_unsupported_extension(
        self, isolated_settings: Settings, secure_engine: Engine, tmp_path: Path
    ) -> None:
        txt_file = tmp_path / "note.txt"
        txt_file.write_text("hello")
        svc = _make_svc(isolated_settings, secure_engine)
        with pytest.raises(PurchaseInvoiceEvidenceInputError, match="unsupported extension"):
            svc.add(bucket_id="b1", source_path=txt_file)

    def test_update_raises_on_missing_id(self, isolated_settings: Settings, secure_engine: Engine) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        with pytest.raises(PurchaseInvoiceEvidenceNotFoundError):
            svc.update(
                bucket_id="b1",
                evidence_id="doesnotexist",
                patch=PurchaseInvoiceEvidencePatch(notes="x"),
            )

    def test_remove_raises_on_missing_id(self, isolated_settings: Settings, secure_engine: Engine) -> None:
        svc = _make_svc(isolated_settings, secure_engine)
        with pytest.raises(PurchaseInvoiceEvidenceNotFoundError):
            svc.remove(bucket_id="b1", evidence_id="doesnotexist")
