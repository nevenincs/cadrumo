"""Real-behaviour tests for evidence resolution into in-memory EvidenceInput.

Exercises the secure-storage byte path end to end with real adapters: the
purchase-invoice ``add`` verb stores bytes in the encrypted ``AttachmentStore``,
and the resolver reads them back into an in-memory :class:`EvidenceInput`. No
mocks, no temp files, no bytes written outside secure storage.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.storage.attachment import AttachmentStore
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from .._evidence import (
    MediaKind,
    PurchaseInvoiceEvidence,
    PurchaseInvoiceEvidenceInputError,
)
from .._evidence_input import (
    EvidenceInput,
    resolve_attachment_evidence_input,
    resolve_purchase_invoice_evidence_input,
)
from ._evidence_input_test_support import _BUCKET_ID, _PDF_BYTES, _added_record, _make_svc
from ._evidence_input_test_support import isolated_settings as isolated_settings
from ._evidence_input_test_support import pdf_file as pdf_file
from ._evidence_input_test_support import runtime_profile as runtime_profile
from ._evidence_input_test_support import secure_objects as secure_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["isolated_settings", "pdf_file", "runtime_profile", "secure_objects"]


def test_add_stores_bytes_in_secure_storage_under_attachment_id(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    pdf_file: Path,
) -> None:
    record = _added_record(isolated_settings, secure_objects, pdf_file)
    # The bytes now live in the encrypted attachment store, content-addressed.
    assert record.attachment_id == hashlib.sha256(_PDF_BYTES).hexdigest()
    assert record.source_sha256 == record.attachment_id
    assert record.attachment_id is not None
    store = AttachmentStore(objects=secure_objects)
    assert store.read_bytes(record.attachment_id) == _PDF_BYTES


def test_add_with_nonexistent_path_refuses_with_path_oriented_guidance(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    tmp_path: Path,
) -> None:
    """A typo'd / missing --file path must surface a PATH problem, not a
    'evidence list' suggestion irrelevant to the file the operator named.

    The refusal names the offending path in its context and tells the operator
    to fix the path, then re-run ``evidence add`` — never to list existing
    records, which does not address a wrong path at all.
    """
    svc = _make_svc(isolated_settings, secure_objects)
    bogus = tmp_path / "does-not-exist.pdf"

    with pytest.raises(PurchaseInvoiceEvidenceInputError) as exc_info:
        svc.add(bucket_id=_BUCKET_ID, source_path=bogus)

    error = exc_info.value
    # The suggestion addresses the path, not the (irrelevant) list verb.
    assert error.suggestion is not None
    assert "evidence list" not in error.suggestion
    assert "path" in error.suggestion.lower()
    assert "aeat app ledger evidence add" in error.suggestion
    # The offending path is named in structured context for the operator.
    assert error.context is not None
    assert str(bogus) == error.context["source_path"]
    assert "resolved_path" in error.context


def test_resolve_purchase_invoice_evidence_reads_secure_storage_into_memory(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    pdf_file: Path,
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
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    pdf_file: Path,
) -> None:
    record = _added_record(isolated_settings, secure_objects, pdf_file)
    assert record.attachment_id is not None
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
        bucket_id=_BUCKET_ID,
        source_path="/some/cleartext/path.pdf",
        source_sha256=hashlib.sha256(_PDF_BYTES).hexdigest(),
        attachment_id=None,
        media_kind=MediaKind.PDF,
        created_at=datetime(2026, 6, 10, tzinfo=UTC),
        updated_at=datetime(2026, 6, 10, tzinfo=UTC),
    )
    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        resolve_purchase_invoice_evidence_input(orphan, store=AttachmentStore(objects=secure_objects))
