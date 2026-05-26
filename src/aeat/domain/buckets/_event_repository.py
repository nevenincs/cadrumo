"""Encrypted SQL repository for the bucket-event-history catalogue."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ...adapters.persistence.storage import Envelope, SensitivityClass
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.sql import SecureObjectWrite
from ...core.logging import get_logger
from ._errors import BucketsError
from ._event import BucketEvent, BucketEventHistoryCatalogue

if TYPE_CHECKING:
    from ...adapters.persistence.storage.sql import SecureObjectRepository

_LOGGER = get_logger(__name__)
_NAMESPACE = "aeat.domain.buckets.event_history"
_OBJECT_KEY = "catalogue"
_CATALOGUE_VERSION = 1


class BucketEventHistoryPersistenceError(BucketsError):
    """Raised when the bucket-event-history catalogue cannot be persisted or loaded."""


def _secure_objects_for_bucket(bucket_id: str) -> SecureObjectRepository:
    """Return the runtime-created secure-object repository for ``bucket_id``."""

    from ...adapters.persistence.storage import inspect_bucket_storage_runtime
    from ...core.config import load_settings

    return inspect_bucket_storage_runtime(bucket_id, load_settings()).secure_object_repository()


def _secure_objects_for_active_bucket() -> SecureObjectRepository:
    """Return the runtime-created repository for the selected active profile."""

    from ...core._bucket_pointer_io import resolve_active_bucket_id
    from ...core.i18n import tr

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        raise BucketEventHistoryPersistenceError(tr("application.workflow.errors.no_active_profile_bucket"))
    return _secure_objects_for_bucket(bucket_id)


class BucketEventHistoryRepository:
    """Read / write the bucket-event-history catalogue."""

    def __init__(self, *, objects: SecureObjectRepository | None = None) -> None:
        self._objects = objects

    @property
    def secure_object_repository(self) -> SecureObjectRepository:
        """Return the secure-object backend used by this catalogue."""

        return self._repository

    @property
    def _repository(self) -> SecureObjectRepository:
        if self._objects is None:
            self._objects = _secure_objects_for_active_bucket()
        return self._objects

    def exists(self) -> bool:
        return self._repository.exists(_NAMESPACE, _OBJECT_KEY)

    def load(self) -> BucketEventHistoryCatalogue:
        try:
            record = self._repository.load(
                _NAMESPACE,
                _OBJECT_KEY,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=_CATALOGUE_VERSION,
            )
        except (ClassificationError, EnvelopeVersionError) as exc:
            _LOGGER.error("bucket-event-history catalogue integrity error", exc_info=True)
            raise BucketEventHistoryPersistenceError(
                f"bucket-event-history catalogue integrity error: {type(exc).__name__}: {exc}"
            ) from exc
        if record is None:
            return BucketEventHistoryCatalogue()
        envelope = Envelope[BucketEventHistoryCatalogue].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not SensitivityClass.FINANCIAL:
            raise BucketEventHistoryPersistenceError(
                f"bucket-event-history catalogue has classification {envelope.classification}; FINANCIAL expected"
            )
        if envelope.schema_version > _CATALOGUE_VERSION:
            raise BucketEventHistoryPersistenceError(
                f"bucket-event-history catalogue is at version {envelope.schema_version}; "
                f"consumer supports up to {_CATALOGUE_VERSION}"
            )
        return envelope.payload

    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        self._repository.save_many((self.to_secure_object_write(catalogue),))

    def to_secure_object_write(self, catalogue: BucketEventHistoryCatalogue) -> SecureObjectWrite:
        """Return the secure-object upsert for ``catalogue`` without committing it."""

        envelope = Envelope[BucketEventHistoryCatalogue](
            schema_version=_CATALOGUE_VERSION,
            written_at=datetime.now(UTC),
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
    """Return a new catalogue with ``event`` inserted.

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
