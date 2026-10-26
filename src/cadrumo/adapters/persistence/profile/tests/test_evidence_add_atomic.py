"""Evidence add retries catalogue and event races as one guarded unit."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.purchase_invoice_evidence import (
    LedgerEvidenceAttachmentIngestor,
    LedgerEvidenceRepositoryAdapter,
)
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.evidence import (
    MediaKind,
    PurchaseInvoiceEvidence,
    PurchaseInvoiceEvidenceService,
)
from cadrumo.application.ledger.evidence_ports import LedgerEvidencePorts
from cadrumo.core.secure_object_write import SecureObjectWrite
from cadrumo.domain.buckets.event import BucketEventObjectType, BucketEventType
from cadrumo.domain.buckets.event_repository import emit_bucket_event

from .evidence_test_support import pdf_file
from .evidence_test_support import secure_objects as _secure_objects

__all__ = ["_secure_objects", "pdf_file"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "34343434-3434-4434-8434-343434343434"
_CONCURRENT_ID = "evidence-concurrent"
_AT = datetime(2026, 5, 8, 10, 15, tzinfo=UTC)


def _record(evidence_id: str) -> PurchaseInvoiceEvidence:
    return PurchaseInvoiceEvidence(
        evidence_id=evidence_id,
        bucket_id=_BUCKET_ID,
        source_path=f"{evidence_id}.pdf",
        source_sha256="a" * 64,
        attachment_id="a" * 64,
        media_kind=MediaKind.PDF,
        supplier="Concurrent SL",
        created_at=_AT,
        updated_at=_AT,
    )


@pytest.mark.parametrize("race", ["evidence_catalogue", "event_catalogue"])
def test_evidence_add_retries_and_commits_row_with_its_event(
    race: Literal["evidence_catalogue", "event_catalogue"],
    secure_objects: SecureObjectRepository,
    pdf_file,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence_repository = LedgerEvidenceRepositoryAdapter(objects=secure_objects)
    event_repository = BucketEventHistoryRepository(objects=secure_objects)
    service = PurchaseInvoiceEvidenceService(
        ports=LedgerEvidencePorts(
            evidence_repository=evidence_repository,
            attachment_ingestor=LedgerEvidenceAttachmentIngestor(store=AttachmentStore(objects=secure_objects)),
            bucket_event_repository=event_repository,
        ),
    )
    concurrent = _record(_CONCURRENT_ID)
    guarded_save = evidence_repository.save_if_revision_with_secure_object_writes
    raced = False

    def inject_race(
        *,
        bucket_id: str,
        records,
        expected_revision_id: str,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        nonlocal raced
        assert bucket_id == _BUCKET_ID
        if not raced:
            raced = True
            if race == "evidence_catalogue":
                evidence_repository.save(bucket_id=_BUCKET_ID, records=(concurrent,))
            else:
                emit_bucket_event(
                    repository=event_repository,
                    bucket_id=_BUCKET_ID,
                    event_type=BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED,
                    occurred_at=_AT,
                    actor="concurrent-writer",
                    object_type=BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE,
                    object_id=_CONCURRENT_ID,
                    payload={"media_kind": "pdf", "source_sha256": "a" * 64},
                    payload_version=1,
                )
        guarded_save(
            bucket_id=bucket_id,
            records=records,
            expected_revision_id=expected_revision_id,
            extra_writes=extra_writes,
        )

    monkeypatch.setattr(evidence_repository, "save_if_revision_with_secure_object_writes", inject_race)

    result = service.add(bucket_id=_BUCKET_ID, source_path=pdf_file, supplier="Added SL")

    assert raced is True
    stored = evidence_repository.load(bucket_id=_BUCKET_ID)
    expected_evidence_ids = {result.record.evidence_id}
    if race == "evidence_catalogue":
        expected_evidence_ids.add(_CONCURRENT_ID)
    assert {record.evidence_id for record in stored} == expected_evidence_ids
    assert result.record.supplier == "Added SL"
    event_catalogue = event_repository.load()
    own_event = next(event_catalogue.events[event_id] for event_id in result.bucket_event_ids)
    assert own_event.object_id == result.record.evidence_id
    if race == "event_catalogue":
        assert any(event.object_id == _CONCURRENT_ID for event in event_catalogue.events.values())
