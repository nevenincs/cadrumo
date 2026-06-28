"""Encrypted SQL repository for the bucket-event-history catalogue.

Persistence is delegated to :class:`SecureObjectRepository`, which handles
encrypted BLOB storage and key management for the active profile bucket.
Each stored record is wrapped in an :class:`Envelope` at
:class:`SensitivityClass` ``FINANCIAL``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ValidationError

from ...core.logging import get_logger
from ...core.time import now
from ._errors import BucketsError
from ._event import BucketEvent, BucketEventHistoryCatalogue

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ...adapters.persistence.storage import SecureObjectRepository, SecureObjectWrite

_LOGGER = get_logger(__name__)
_NAMESPACE = "aeat.domain.buckets.event_history"
_OBJECT_KEY = "catalogue"
_CATALOGUE_VERSION = 1


class BucketEventHistoryPersistenceError(BucketsError):
    """Raised when the bucket-event-history catalogue cannot be persisted or loaded."""


class BucketEventHistoryRepository:
    """Read / write the bucket-event-history catalogue."""

    def __init__(self, *, objects: SecureObjectRepository | None = None) -> None:
        if objects is not None:
            self._objects = objects
            return
        from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket

        self._objects = secure_object_repository_for_active_bucket()

    @property
    def secure_object_repository(self) -> SecureObjectRepository:
        """Return the secure-object backend used by this catalogue.

        Returns:
            The :class:`SecureObjectRepository` backing this repository.
        """
        return self._objects

    def exists(self) -> bool:
        return self._objects.exists(_NAMESPACE, _OBJECT_KEY)

    def load(self) -> BucketEventHistoryCatalogue:
        from ...adapters.persistence.storage import Envelope, SensitivityClass
        from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError

        try:
            record = self._objects.load(
                _NAMESPACE,
                _OBJECT_KEY,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=_CATALOGUE_VERSION,
            )
        except (ClassificationError, EnvelopeVersionError) as exc:
            _LOGGER.error("bucket-event-history catalogue integrity error", exc_info=True)
            raise BucketEventHistoryPersistenceError(
                context={"namespace": _NAMESPACE, "object_key": _OBJECT_KEY, "error": type(exc).__name__},
                translated_message=getattr(exc, "translated_message", None)
                or "errors.integrity.integrity_storage_validation",
            ) from exc
        if record is None:
            return BucketEventHistoryCatalogue()
        try:
            envelope = Envelope[BucketEventHistoryCatalogue].model_validate_json(record.payload)
        except ValidationError as exc:
            _LOGGER.error("bucket-event-history catalogue schema drift", exc_info=True)
            raise BucketEventHistoryPersistenceError(
                context={"namespace": _NAMESPACE, "object_key": _OBJECT_KEY, "recovery": "aeat config repair --help"},
                suggestion="aeat config repair --help",
                translated_message="errors.storage.stored_data_validation_boundary",
            ) from exc
        if envelope.classification is not SensitivityClass.FINANCIAL:
            _LOGGER.error(
                "bucket-event-history catalogue classification mismatch classification=%s",
                envelope.classification.value,
            )
            raise BucketEventHistoryPersistenceError(
                context={
                    "namespace": _NAMESPACE,
                    "object_key": _OBJECT_KEY,
                    "classification": envelope.classification.value,
                    "expected": SensitivityClass.FINANCIAL.value,
                },
                translated_message="errors.integrity.integrity_storage_classification",
            )
        if envelope.schema_version > _CATALOGUE_VERSION:
            _LOGGER.error(
                "bucket-event-history catalogue envelope version mismatch schema_version=%d",
                envelope.schema_version,
            )
            raise BucketEventHistoryPersistenceError(
                context={
                    "namespace": _NAMESPACE,
                    "object_key": _OBJECT_KEY,
                    "schema_version": envelope.schema_version,
                    "expected": _CATALOGUE_VERSION,
                },
                translated_message="errors.integrity.integrity_storage_envelope_version",
            )
        return envelope.payload

    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        self._objects.save_many((self.to_secure_object_write(catalogue),))

    def to_secure_object_write(self, catalogue: BucketEventHistoryCatalogue) -> SecureObjectWrite:
        """Return the :class:`SecureObjectWrite` upsert for ``catalogue`` without committing it."""
        from ...adapters.persistence.storage import Envelope, SecureObjectWrite, SensitivityClass

        envelope = Envelope[BucketEventHistoryCatalogue](
            schema_version=_CATALOGUE_VERSION,
            written_at=now(),
            classification=SensitivityClass.FINANCIAL,
            payload=catalogue,
        )
        return SecureObjectWrite(
            namespace=_NAMESPACE,
            object_key=_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )


def append_bucket_event(catalogue: BucketEventHistoryCatalogue, event: BucketEvent) -> BucketEventHistoryCatalogue:
    """Return a new :class:`BucketEventHistoryCatalogue` with ``event`` inserted.

    Content-addressed: a re-emission with identical content collapses
    to the same ``event_id`` and the existing entry is left in place.
    """
    mapping = dict(catalogue.events)
    mapping[event.event_id] = event
    return BucketEventHistoryCatalogue(events=mapping)


__all__ = [
    "BucketEventHistoryPersistenceError",
    "BucketEventHistoryRepository",
    "append_bucket_event",
]
