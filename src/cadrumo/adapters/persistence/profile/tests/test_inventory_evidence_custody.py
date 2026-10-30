"""A purchase document enters real encrypted custody and comes back as its own digest."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.purchase_invoice_evidence import (
    LedgerEvidenceAttachmentIngestor,
    LedgerEvidenceRepositoryAdapter,
)
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.evidence import ingest_evidence_file
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
        source_path=source.name,
        source_directory=tmp_path,
        now=_AT,
        actor="cli",
    )

    assert str(digest) == hashlib.sha256(source.read_bytes()).hexdigest()
    assert ports.evidence_repository.load(bucket_id=BUCKET_ID) == ()


def test_the_same_file_twice_is_the_same_document(secure_objects: SecureObjectRepository, tmp_path: Path) -> None:
    source = tmp_path / "price.pdf"
    source.write_bytes(b"%PDF-1.7 synthetic price")
    ports = _ports(secure_objects)
    arguments = {
        "ports": ports,
        "bucket_id": BUCKET_ID,
        "source_path": str(source),
        "source_directory": None,
        "now": _AT,
        "actor": "cli",
    }

    assert ingest_evidence_file(**arguments) == ingest_evidence_file(**arguments)


def test_a_missing_file_is_refused(secure_objects: SecureObjectRepository, tmp_path: Path) -> None:
    with pytest.raises(PurchaseInvoiceEvidenceInputError):
        ingest_evidence_file(
            ports=_ports(secure_objects),
            bucket_id=BUCKET_ID,
            source_path="absent.pdf",
            source_directory=tmp_path,
            now=_AT,
            actor="cli",
        )
