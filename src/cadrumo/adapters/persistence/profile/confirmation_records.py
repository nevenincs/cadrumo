"""Encrypted persistence adapter for ledger confirmation records."""

from __future__ import annotations

from typing import override

from ....application.ledger.confirmation_record import (
    ConfirmationRecordDocument,
    confirmation_record_object_key,
)
from ....core.config import Settings
from ..storage.envelope.secure_bound_repository import SecureBoundRepository
from ..storage.runtime_repository import secure_object_repository_for_bucket
from ..storage.secure_object_namespaces import LEDGER_CONFIRMATION_RECORD_NAMESPACE


class ConfirmationRecordRepository(SecureBoundRepository[ConfirmationRecordDocument]):
    """Store one bucket's confirmation provenance through encrypted objects."""

    namespace = LEDGER_CONFIRMATION_RECORD_NAMESPACE.namespace
    sensitivity = LEDGER_CONFIRMATION_RECORD_NAMESPACE.sensitivity
    schema_version = LEDGER_CONFIRMATION_RECORD_NAMESPACE.schema_version
    payload_type = ConfirmationRecordDocument

    def __init__(self, *, bucket_id: str, settings: Settings | None) -> None:
        """Bind the repository to ``bucket_id`` through the storage runtime."""
        super().__init__(objects=secure_object_repository_for_bucket(bucket_id, settings))

    @override
    def extract_identifier(self, payload: ConfirmationRecordDocument) -> str:
        """Return the application-owned natural key for ``payload``."""
        return confirmation_record_object_key(payload)


__all__ = ["ConfirmationRecordRepository"]
