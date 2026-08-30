"""Encrypted persistence adapter for application sync-run provenance records."""

from __future__ import annotations

from typing import ClassVar, override

from pydantic import BaseModel

from ....application.storage.sync_runs import (
    SyncRunRecord,
    SyncRunRecordRepositoryProtocol,
    sync_run_record_key,
)
from ....domain.buckets.event import BucketEvent
from ....domain.buckets.event_repository import bucket_event_history_write
from ..storage import SYNC_RUN_RECORDS_NAMESPACE, SecureBoundRepository, SensitivityClass
from .buckets import BucketEventHistoryRepository


class SyncRunRecordRepository(SecureBoundRepository[SyncRunRecord], SyncRunRecordRepositoryProtocol):
    """Store sync provenance and its bucket event in one secure-object transaction."""

    namespace: ClassVar[str] = SYNC_RUN_RECORDS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = SYNC_RUN_RECORDS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = SYNC_RUN_RECORDS_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = SyncRunRecord

    @override
    def extract_identifier(self, payload: SyncRunRecord) -> str:
        return sync_run_record_key(
            surface=payload.surface,
            bucket_event_id=payload.bucket_event_id,
        )

    @override
    def save_with_bucket_event(self, record: SyncRunRecord, event: BucketEvent) -> None:
        """Commit the run record and its event with the shared backend transaction."""
        events = BucketEventHistoryRepository(objects=self.secure_object_repository)
        event_write = bucket_event_history_write(events, (event,))
        self.secure_object_repository.save_many((self.to_secure_object_write(record), event_write))


__all__ = ["SyncRunRecordRepository"]
