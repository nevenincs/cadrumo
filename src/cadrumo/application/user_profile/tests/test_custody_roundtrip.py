"""Behavioral coverage for secure-object custody export policy."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.storage.attachment import AttachmentStore
from ....domain.buckets.event import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
)
from ....adapters.persistence.storage.tests.secure_sql import isolated_two_bucket_runtime
from ..custody_carry import build_secure_object_custody_payload

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EVIDENCE_BYTES = b"%PDF-1.7 invoice evidence \x00\xff bytes"
_INSTANT = datetime(2026, 6, 30, 9, 0, 0, tzinfo=UTC)


def _seed_bucket_event(bucket_id: str) -> None:
    event_id = derive_bucket_event_id(
        bucket_id=bucket_id,
        event_type=BucketEventType.BUCKET_EXPORTED,
        occurred_at=_INSTANT,
        actor="operator",
        object_type=BucketEventObjectType.BUCKET,
        object_id=bucket_id,
        payload={"transfer_id": "custody-export-policy"},
    )
    BucketEventHistoryRepository().save(
        BucketEventHistoryCatalogue(
            events={
                event_id: BucketEvent(
                    event_id=event_id,
                    bucket_id=bucket_id,
                    event_type=BucketEventType.BUCKET_EXPORTED,
                    occurred_at=_INSTANT,
                    actor="operator",
                    object_type=BucketEventObjectType.BUCKET,
                    object_id=bucket_id,
                    payload_version=1,
                    payload={"transfer_id": "custody-export-policy"},
                ),
            },
        ),
    )


def test_structured_profile_excludes_attachment_evidence_bytes(tmp_path: Path) -> None:
    """Structured export excludes evidence bytes that full custody includes."""
    from ....core.storage_taxonomy import StorageCustodyProfile

    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        AttachmentStore().put_bytes(_EVIDENCE_BYTES)
        _seed_bucket_event(runtime.primary.bucket_id)

        structured, _ = build_secure_object_custody_payload(
            bucket_id=runtime.primary.bucket_id,
            custody_profile=StorageCustodyProfile.STRUCTURED,
        )
        full, _ = build_secure_object_custody_payload(
            bucket_id=runtime.primary.bucket_id,
            custody_profile=StorageCustodyProfile.FULL,
        )

        structured_namespaces = {obj.namespace for obj in structured}
        full_namespaces = {obj.namespace for obj in full}
        assert "cadrumo.domain.attachments.blobs" in full_namespaces
        assert "cadrumo.domain.attachments.blobs" not in structured_namespaces
