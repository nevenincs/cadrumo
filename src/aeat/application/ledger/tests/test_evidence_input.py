"""Real-behaviour tests for evidence resolution into in-memory EvidenceInput.

Exercises the secure-storage byte path end to end with real adapters: the
purchase-invoice ``add`` verb stores bytes in the encrypted ``AttachmentStore``,
and the resolver reads them back into an in-memory :class:`EvidenceInput`. No
mocks, no temp files, no bytes written outside secure storage.
"""

from __future__ import annotations

import hashlib
import pickle
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel
from pydantic_core import PydanticSerializationError

from ....adapters.persistence.storage.attachment import AttachmentStore
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....domain.buckets import BucketEventHistoryRepository
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._evidence import (
    MediaKind,
    PurchaseInvoiceEvidence,
    PurchaseInvoiceEvidenceInputError,
    PurchaseInvoiceEvidenceService,
)
from .._evidence_input import (
    EvidenceInput,
    resolve_attachment_evidence_input,
    resolve_purchase_invoice_evidence_input,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PDF_BYTES = b"%PDF-1.4 evidence-input-roundtrip body"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="bucket-001") as profile:
        yield profile


@pytest.fixture
def isolated_settings(runtime_profile: TestRuntimeProfile) -> Settings:
    return runtime_profile.settings


@pytest.fixture
def secure_objects(runtime_profile: TestRuntimeProfile) -> SecureObjectRepository:
    return runtime_profile.repository


@pytest.fixture
def pdf_file(tmp_path: Path) -> Path:
    p = tmp_path / "invoice.pdf"
    p.write_bytes(_PDF_BYTES)
    return p


def _added_record(
    isolated_settings: Settings, secure_objects: SecureObjectRepository, pdf_file: Path
) -> PurchaseInvoiceEvidence:
    svc = PurchaseInvoiceEvidenceService(
        settings=isolated_settings,
        bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
    )
    return svc.add(bucket_id="bucket-001", source_path=pdf_file).record


def test_add_stores_bytes_in_secure_storage_under_attachment_id(
    isolated_settings: Settings, secure_objects: SecureObjectRepository, pdf_file: Path
) -> None:
    record = _added_record(isolated_settings, secure_objects, pdf_file)
    # The bytes now live in the encrypted attachment store, content-addressed.
    assert record.attachment_id == hashlib.sha256(_PDF_BYTES).hexdigest()
    assert record.source_sha256 == record.attachment_id
    store = AttachmentStore(objects=secure_objects)
    assert store.read_bytes(record.attachment_id) == _PDF_BYTES


def test_resolve_purchase_invoice_evidence_reads_secure_storage_into_memory(
    isolated_settings: Settings, secure_objects: SecureObjectRepository, pdf_file: Path
) -> None:
    record = _added_record(isolated_settings, secure_objects, pdf_file)
    store = AttachmentStore(objects=secure_objects)

    resolved = resolve_purchase_invoice_evidence_input(record, store=store)

    assert isinstance(resolved, EvidenceInput)
    assert resolved.data == _PDF_BYTES
    assert resolved.content_sha256 == hashlib.sha256(_PDF_BYTES).hexdigest()
    assert resolved.media_kind is MediaKind.PDF
    assert resolved.mime_type == "application/pdf"
    assert resolved.evidence_id == record.evidence_id
    assert resolved.attachment_id == record.attachment_id


def test_resolve_attachment_evidence_input_round_trips_bytes(
    isolated_settings: Settings, secure_objects: SecureObjectRepository, pdf_file: Path
) -> None:
    record = _added_record(isolated_settings, secure_objects, pdf_file)
    store = AttachmentStore(objects=secure_objects)

    resolved = resolve_attachment_evidence_input(record.attachment_id, store=store)

    assert resolved.data == _PDF_BYTES
    assert resolved.attachment_id == record.attachment_id


def test_resolve_refuses_record_without_in_store_attachment(
    secure_objects: SecureObjectRepository,
) -> None:
    # A record whose bytes are not in secure storage (no attachment_id) must not
    # fall back to a cleartext path read.
    orphan = PurchaseInvoiceEvidence(
        evidence_id="ev-orphan",
        bucket_id="bucket-001",
        source_path="/some/cleartext/path.pdf",
        source_sha256=hashlib.sha256(_PDF_BYTES).hexdigest(),
        attachment_id=None,
        media_kind=MediaKind.PDF,
        created_at=datetime(2026, 6, 10, tzinfo=UTC),
        updated_at=datetime(2026, 6, 10, tzinfo=UTC),
    )
    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        resolve_purchase_invoice_evidence_input(orphan, store=AttachmentStore(objects=secure_objects))


def test_evidence_input_refuses_persistence(
    isolated_settings: Settings, secure_objects: SecureObjectRepository, pdf_file: Path
) -> None:
    record = _added_record(isolated_settings, secure_objects, pdf_file)
    resolved = resolve_purchase_invoice_evidence_input(record, store=AttachmentStore(objects=secure_objects))
    # The rule made executable: decrypted FINANCIAL bytes must never be serialized out.
    # Direct dump/json refuse loudly.
    with pytest.raises(NotImplementedError):
        resolved.model_dump()
    with pytest.raises(NotImplementedError):
        resolved.model_dump_json()
    # dict()/iteration and pickle refuse (they would otherwise expose `data`).
    with pytest.raises(NotImplementedError):
        dict(resolved)
    with pytest.raises(NotImplementedError):
        pickle.dumps(resolved)


def test_nested_serialization_cannot_leak_evidence_bytes(
    isolated_settings: Settings, secure_objects: SecureObjectRepository, pdf_file: Path
) -> None:
    # The realistic leak path: EvidenceInput embedded in another model that is dumped.
    # The model serializer must refuse so the bytes never serialize through the parent.
    record = _added_record(isolated_settings, secure_objects, pdf_file)
    resolved = resolve_purchase_invoice_evidence_input(record, store=AttachmentStore(objects=secure_objects))

    class _Wrapper(BaseModel):
        ev: EvidenceInput

    wrapper = _Wrapper(ev=resolved)
    with pytest.raises(PydanticSerializationError):
        wrapper.model_dump()
    with pytest.raises(PydanticSerializationError):
        wrapper.model_dump_json()
