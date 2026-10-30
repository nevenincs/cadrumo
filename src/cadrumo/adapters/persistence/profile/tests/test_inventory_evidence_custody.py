"""A purchase document enters real encrypted custody and comes back as its own digest."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.inventory_documents import attachment_source_file_name
from cadrumo.adapters.persistence.profile.purchase_invoice_evidence import (
    LedgerEvidenceAttachmentIngestor,
    LedgerEvidenceRepositoryAdapter,
)
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.evidence import admit_evidence_file, ingest_evidence_file
from cadrumo.application.ledger.evidence_errors import PurchaseInvoiceEvidenceInputError
from cadrumo.application.ledger.evidence_ports import LedgerEvidencePorts

from .evidence_test_support import BUCKET_ID
from .evidence_test_support import secure_objects as _secure_objects

__all__ = ["_secure_objects"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_AT = datetime(2026, 5, 8, 10, 15, tzinfo=UTC)


def _ports(objects: SecureObjectRepository) -> LedgerEvidencePorts:
    return LedgerEvidencePorts(
        evidence_repository=LedgerEvidenceRepositoryAdapter(objects=objects),
        attachment_ingestor=LedgerEvidenceAttachmentIngestor(store=AttachmentStore(objects=objects)),
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
    )


def test_the_digest_is_the_files_own_and_no_invoice_record_appears(
    secure_objects: SecureObjectRepository, tmp_path: Path
) -> None:
    source = tmp_path / "cost-check.pdf"
    source.write_bytes(b"%PDF-1.7 synthetic cost check")
    ports = _ports(secure_objects)

    digest = ingest_evidence_file(
        ports=ports,
        bucket_id=BUCKET_ID,
        admitted=admit_evidence_file(source.name, tmp_path),
        now=_AT,
        actor="cli",
    )

    assert str(digest) == hashlib.sha256(source.read_bytes()).hexdigest()
    assert ports.evidence_repository.load(bucket_id=BUCKET_ID) == ()


def test_a_held_document_answers_its_name_without_its_folder(
    secure_objects: SecureObjectRepository, tmp_path: Path
) -> None:
    source = tmp_path / "cost-check.pdf"
    source.write_bytes(b"%PDF-1.7 synthetic named cost check")
    digest = ingest_evidence_file(
        ports=_ports(secure_objects),
        bucket_id=BUCKET_ID,
        admitted=admit_evidence_file(str(source), None),
        now=_AT,
        actor="cli",
    )

    assert attachment_source_file_name(secure_objects, str(digest)) == "cost-check.pdf"


def test_a_document_never_held_has_no_name(secure_objects: SecureObjectRepository) -> None:
    assert attachment_source_file_name(secure_objects, "a" * 64) is None


def test_the_same_file_twice_is_the_same_document(secure_objects: SecureObjectRepository, tmp_path: Path) -> None:
    source = tmp_path / "price.pdf"
    source.write_bytes(b"%PDF-1.7 synthetic price")
    ports = _ports(secure_objects)
    arguments = {
        "ports": ports,
        "bucket_id": BUCKET_ID,
        "admitted": admit_evidence_file(str(source), None),
        "now": _AT,
        "actor": "cli",
    }

    assert ingest_evidence_file(**arguments) == ingest_evidence_file(**arguments)


@pytest.mark.parametrize("name", ["absent.pdf", "notes.txt"])
def test_a_file_that_cannot_be_kept_is_refused_before_any_effect(name: str, tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("synthetic")
    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        admit_evidence_file(name, tmp_path)
