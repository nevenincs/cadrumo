"""Persistence roundtrip for the generic secure-object custody carry.

Proves the previously-dropped per-bucket stores survive an export/import into a
recipient bucket with a *different* data-encryption key: the attachment evidence
bytes (FINANCIAL) and the bucket event-history audit trail are seeded in the
source bucket, carried under the full custody profile, restored into the
recipient bucket, and read back intact. The recipient bucket's distinct DEK is
the exact condition that breaks a digest-based carry, so a green test here is the
proof that the natural-key carry re-keys correctly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.storage.attachment import AttachmentStore
from ....domain.buckets import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
)
from ....tests.secure_sql import isolated_two_bucket_runtime
from .._custody_carry import restore_carried_objects, serialize_carried_objects

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EVIDENCE_BYTES = b"%PDF-1.7 invoice evidence \x00\xff bytes"
_INSTANT = datetime(2026, 6, 30, 9, 0, 0, tzinfo=UTC)


def _seed_bucket_event(bucket_id: str) -> str:
    event_id = derive_bucket_event_id(
        bucket_id=bucket_id,
        event_type=BucketEventType.PROFILE_RENAMED,
        occurred_at=_INSTANT,
        actor="operator",
        object_type=BucketEventObjectType.PROFILE,
        object_id=bucket_id,
        payload={"display_name": "Audited"},
    )
    event = BucketEvent(
        event_id=event_id,
        bucket_id=bucket_id,
        event_type=BucketEventType.PROFILE_RENAMED,
        occurred_at=_INSTANT,
        actor="operator",
        object_type=BucketEventObjectType.PROFILE,
        object_id=bucket_id,
        payload_version=1,
        payload={"display_name": "Audited"},
    )
    repo = BucketEventHistoryRepository()
    repo.save(BucketEventHistoryCatalogue(events={event_id: event}))
    return event_id


def test_full_custody_carry_restores_evidence_bytes_and_audit_trail(tmp_path: Path) -> None:
    from ....adapters.persistence.storage._namespace_registry import StorageCustodyProfile

    with isolated_two_bucket_runtime(tmp_path=tmp_path) as runtime:
        source_bucket = runtime.primary.bucket_id
        target_bucket = runtime.secondary.bucket_id

        # Seed previously-dropped stores in the source bucket.
        sha = AttachmentStore().put_bytes(_EVIDENCE_BYTES)
        event_id = _seed_bucket_event(source_bucket)

        carried = serialize_carried_objects(bucket_id=source_bucket, profile=StorageCustodyProfile.FULL)

        carried_namespaces = {obj.namespace for obj in carried}
        assert "aeat.domain.attachments.blobs" in carried_namespaces
        assert "aeat.domain.buckets.event_history" in carried_namespaces

        with runtime.switch_to_secondary():
            # The recipient bucket starts without the evidence or the audit event.
            with pytest.raises(Exception):  # noqa: B017 - AttachmentNotFoundError
                AttachmentStore().read_bytes(sha)

            restore_carried_objects(carried, target_bucket_id=target_bucket)

            # Evidence bytes survive and resolve under the recipient DEK.
            assert AttachmentStore().read_bytes(sha) == _EVIDENCE_BYTES

            # The audit trail survives with its content-addressed event id intact.
            restored = BucketEventHistoryRepository().load()
            assert event_id in restored.events
            assert restored.events[event_id].payload["display_name"] == "Audited"
