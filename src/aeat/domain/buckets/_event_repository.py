"""Encrypted SQL repository for the bucket-event-history catalogue.

:class:`BucketEventHistoryRepository` persists
:class:`BucketEventHistoryCatalogue` through
:class:`~aeat.adapters.persistence.storage.sql.SecureObjectRepository`, which
handles encrypted BLOB storage and key management for the active profile
bucket. Each stored record is wrapped in an
:class:`~aeat.adapters.persistence.storage.Envelope` at
:class:`~aeat.adapters.persistence.storage.SensitivityClass` ``FINANCIAL``.
The storage contract is declared by
:data:`aeat.adapters.persistence.storage.BUCKET_EVENT_HISTORY_NAMESPACE`; its
default object key is the singleton ``catalogue`` row.
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
    """Raised when the bucket-event-history catalogue cannot be persisted or loaded.

    This wraps storage-boundary failures from
    :class:`BucketEventHistoryRepository` while preserving translated recovery
    context for callers.
    """


class BucketEventHistoryRepository:
    """Repository over encrypted SQL-backed event-history catalogue storage.

    :data:`aeat.adapters.persistence.storage.BUCKET_EVENT_HISTORY_NAMESPACE`
    is the central profile-local namespace, schema-version, sensitivity, and
    singleton-key contract for the encrypted
    :class:`BucketEventHistoryCatalogue`. The catalogue preserves the
    append-only :class:`BucketEvent` history, is wrapped in
    :class:`~aeat.adapters.persistence.storage.Envelope`, and is persisted
    through :class:`~aeat.adapters.persistence.storage.sql.SecureObjectRepository`.
    The same envelope can be emitted as a
    :class:`~aeat.adapters.persistence.storage.SecureObjectWrite` when sibling
    catalogue updates need one transaction. This class exposes the concrete
    load/save implementation behind
    :class:`~aeat.domain.buckets._protocols.BucketEventHistoryRepositoryProtocol`.
    """

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
            The
            :class:`~aeat.adapters.persistence.storage.sql.SecureObjectRepository`
            backing this repository.
        """
        return self._objects

    def exists(self) -> bool:
        """Return whether a bucket-event-history catalogue has been persisted."""
        return self._objects.exists(_NAMESPACE, _OBJECT_KEY)

    def load(self) -> BucketEventHistoryCatalogue:
        """Return the persisted catalogue or an empty catalogue if absent.

        Returns:
            The deserialised :class:`BucketEventHistoryCatalogue`, or a fresh
            empty instance when no database object is present.

        Raises:
            :class:`BucketEventHistoryPersistenceError`: If secure-object
                classification, envelope version, or payload validation fails.
        """
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
        """Persist ``catalogue`` atomically through the secure-object repository.

        Args:
            catalogue: The :class:`BucketEventHistoryCatalogue` to persist.
        """
        self._objects.save_many((self.to_secure_object_write(catalogue),))

    def to_secure_object_write(self, catalogue: BucketEventHistoryCatalogue) -> SecureObjectWrite:
        """Return the secure-object upsert for ``catalogue`` without committing it.

        The returned :class:`~aeat.adapters.persistence.storage.SecureObjectWrite`
        carries the same :class:`~aeat.adapters.persistence.storage.Envelope`
        and :class:`~aeat.adapters.persistence.storage.SensitivityClass`
        classification that :meth:`save` would persist directly.
        """
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

    Content-addressed: a re-emission of the same :class:`BucketEvent` collapses
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
