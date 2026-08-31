"""Encrypted persistence for modelo reconciliation records and audit events."""

from __future__ import annotations

from collections.abc import Iterator
from typing import ClassVar, override

from pydantic import BaseModel

from ....application.modelo.reconciliation_records import (
    ModeloReconciliationPersistencePort,
    ModeloReconciliationRecord,
)
from ....core.classification.policies import SensitivityClass
from ....domain.buckets.event import BucketEvent
from ....domain.buckets.event_repository import append_bucket_event
from ..storage.envelope._secure_repository import SecureBoundRepository
from ..storage.path_safety import safe_repository_id
from ..storage.secure_object_namespaces import MODELO_RECONCILIATION_RECORDS_NAMESPACE
from .buckets import BucketEventHistoryRepository


def modelo_reconciliation_record_key(*, work_unit_id: str, bucket_event_id: str) -> str:
    """Return the storage key for one reconciliation of one work unit.

    The event id keeps repeated reconciliations distinct and joins the encrypted
    detail row to the audit event co-written with it.
    """
    safe_repository_id(work_unit_id, context="work_unit_id")
    safe_repository_id(bucket_event_id, context="bucket_event_id")
    return f"modelo-reconciliation:{work_unit_id}:{bucket_event_id}"


class ModeloReconciliationRecordRepository(SecureBoundRepository[ModeloReconciliationRecord]):
    """Repository over encrypted SQL-backed reconciliation records."""

    namespace: ClassVar[str] = MODELO_RECONCILIATION_RECORDS_NAMESPACE.namespace
    sensitivity: ClassVar[SensitivityClass] = MODELO_RECONCILIATION_RECORDS_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = MODELO_RECONCILIATION_RECORDS_NAMESPACE.schema_version
    payload_type: ClassVar[type[BaseModel]] = ModeloReconciliationRecord

    @override
    def extract_identifier(self, payload: ModeloReconciliationRecord) -> str:
        return modelo_reconciliation_record_key(
            work_unit_id=payload.work_unit_id,
            bucket_event_id=payload.bucket_event_id,
        )


class ModeloReconciliationPersistence(ModeloReconciliationPersistencePort):
    """Concrete atomic persistence for reconciliation detail and audit event."""

    @override
    def persist_with_event(self, record: ModeloReconciliationRecord, event: BucketEvent) -> None:
        event_repository = BucketEventHistoryRepository()
        event_catalogue, event_revision_id = event_repository.load_revisioned()
        next_catalogue = append_bucket_event(event_catalogue, event)
        objects = event_repository.secure_object_repository
        objects.save_many(
            (
                event_repository.to_secure_object_write(
                    next_catalogue,
                    expected_revision_id=event_revision_id,
                ),
                ModeloReconciliationRecordRepository(objects=objects).to_secure_object_write(record),
            ),
        )

    @override
    def iter_records(self) -> Iterator[ModeloReconciliationRecord]:
        yield from ModeloReconciliationRecordRepository().iter_records()


def build_modelo_reconciliation_persistence() -> ModeloReconciliationPersistencePort:
    """Construct the concrete reconciliation persistence adapter."""
    return ModeloReconciliationPersistence()


__all__ = [
    "ModeloReconciliationPersistence",
    "ModeloReconciliationRecordRepository",
    "build_modelo_reconciliation_persistence",
    "modelo_reconciliation_record_key",
]
