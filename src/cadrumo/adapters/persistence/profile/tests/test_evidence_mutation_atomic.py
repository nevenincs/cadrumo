"""Evidence mutations retry revision races without losing sibling state or events."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.purchase_invoice_evidence import LedgerEvidenceRepositoryAdapter
from cadrumo.adapters.persistence.storage.sql.secure_object_records import (
    SecureObjectDeletion,
    SecureObjectRevisionAssertion,
)
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.application.ledger.evidence import (
    MediaKind,
    PurchaseInvoiceEvidence,
    PurchaseInvoiceEvidencePatch,
    PurchaseInvoiceEvidenceService,
)
from cadrumo.application.ledger.evidence_ports import EvidenceAttachmentIngestRequest, LedgerEvidencePorts
from cadrumo.core.identity.digest import ContentDigest
from cadrumo.core.secure_object_write import SecureObjectWrite
from cadrumo.domain.buckets.event import BucketEventObjectType, BucketEventType
from cadrumo.domain.buckets.event_repository import emit_bucket_event

from .evidence_test_support import secure_objects as _secure_objects

__all__ = ["_secure_objects"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "34343434-3434-4434-8434-343434343434"
_TARGET_ID = "evidence-target"
_CONCURRENT_ID = "evidence-concurrent"
_AT = datetime(2026, 5, 8, 10, 15, tzinfo=UTC)


class _UnexpectedAttachmentIngestor:
    def ingest(self, request: EvidenceAttachmentIngestRequest) -> ContentDigest:
        raise AssertionError("evidence mutations must not ingest files")


def _record(evidence_id: str) -> PurchaseInvoiceEvidence:
    return PurchaseInvoiceEvidence(
        evidence_id=evidence_id,
        bucket_id=_BUCKET_ID,
        source_path=f"{evidence_id}.pdf",
        source_sha256="a" * 64,
        attachment_id="a" * 64,
        media_kind=MediaKind.PDF,
        supplier="Before SL",
        invoice_number="INV-2026-05",
        invoice_date="2026-05-08",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
        notes="invoice note",
        created_at=_AT,
        updated_at=_AT,
    )


@pytest.mark.parametrize("action", ["update", "remove"])
@pytest.mark.parametrize("race", ["evidence_catalogue", "event_catalogue"])
def test_evidence_mutation_retries_whole_snapshot_and_co_commits_event(
    action: Literal["update", "remove"],
    race: Literal["evidence_catalogue", "event_catalogue"],
    secure_objects: SecureObjectRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence_repository = LedgerEvidenceRepositoryAdapter(objects=secure_objects)
    event_repository = BucketEventHistoryRepository(objects=secure_objects)
    target = _record(_TARGET_ID)
    concurrent = _record(_CONCURRENT_ID)
    evidence_repository.save(bucket_id=_BUCKET_ID, records=(target,))
    ports = LedgerEvidencePorts(
        evidence_repository=evidence_repository,
        attachment_ingestor=_UnexpectedAttachmentIngestor(),
        bucket_event_repository=event_repository,
    )
    service = PurchaseInvoiceEvidenceService(ports=ports)

    apply_batch = secure_objects.apply_batch
    raced = False

    def inject_concurrent_write(
        writes: tuple[SecureObjectWrite, ...],
        deletions: tuple[SecureObjectDeletion, ...] = (),
        *,
        assertions: tuple[SecureObjectRevisionAssertion, ...] = (),
    ) -> None:
        nonlocal raced
        if not raced:
            raced = True
            if race == "evidence_catalogue":
                evidence_repository.save(bucket_id=_BUCKET_ID, records=(target, concurrent))
            else:
                emit_bucket_event(
                    repository=event_repository,
                    bucket_id=_BUCKET_ID,
                    event_type=BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED,
                    occurred_at=_AT,
                    actor="concurrent-writer",
                    object_type=BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE,
                    object_id=_CONCURRENT_ID,
                    payload={"media_kind": "pdf"},
                    payload_version=1,
                )
        apply_batch(writes, deletions, assertions=assertions)

    monkeypatch.setattr(secure_objects, "apply_batch", inject_concurrent_write)

    if action == "update":
        result = service.update(
            bucket_id=_BUCKET_ID,
            evidence_id=_TARGET_ID,
            patch=PurchaseInvoiceEvidencePatch(supplier="After SL"),
            actor="operator",
            occurred_at=_AT,
        )
        assert result.record.supplier == "After SL"
    else:
        result = service.remove(bucket_id=_BUCKET_ID, evidence_id=_TARGET_ID, actor="operator")
        assert result.record == target

    assert raced is True
    stored = evidence_repository.load(bucket_id=_BUCKET_ID)
    if action == "remove":
        expected_records = (concurrent,) if race == "evidence_catalogue" else ()
    else:
        updated_target = next(record for record in stored if record.evidence_id == _TARGET_ID)
        expected_records = (updated_target, concurrent) if race == "evidence_catalogue" else (updated_target,)
    assert stored == expected_records
    if action == "update":
        updated = next(record for record in stored if record.evidence_id == _TARGET_ID)
        assert updated.supplier == "After SL"
    elif race == "evidence_catalogue":
        assert stored == (concurrent,)

    events = event_repository.load().events
    mutation_events = tuple(event for event in events.values() if event.object_id == _TARGET_ID)
    assert len(mutation_events) == 1
    assert result.bucket_event_ids == (mutation_events[0].event_id,)
    if race == "event_catalogue":
        assert any(event.object_id == _CONCURRENT_ID for event in events.values())
