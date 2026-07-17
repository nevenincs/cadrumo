"""Encrypted SQL repository for the bucket-event-history catalogue.

:class:`BucketEventHistoryRepository` persists
:class:`~domain.buckets.BucketEventHistoryCatalogue` through
:class:`~adapters.persistence.storage.SecureObjectRepository`, which
handles encrypted BLOB storage and key management for the active profile
bucket. Each stored record is wrapped in an
:class:`~adapters.persistence.storage.Envelope` at
``FINANCIAL`` :class:`~adapters.persistence.storage.SensitivityClass`.

This concrete repository is the persistence adapter behind the read-side
:class:`~domain.buckets.BucketEventHistoryRepositoryProtocol`. It lives in
the persistence adapter (not in :mod:`~domain.buckets`) because its
secure-object coupling is SQL/crypto-bound; the domain package owns only the
typed :class:`~domain.buckets.BucketEventHistoryCatalogue` model, its
narrow port, and the
:class:`~domain.buckets.BucketEventHistoryPersistenceError` boundary error.
The namespace/version constants are redeclared here as the persisted-envelope
contract; the strings are preserved to avoid orphaning persisted envelopes.

See Also:
    :mod:`~domain.buckets`
        Public bucket-event facade that owns the catalogue, event taxonomy, and
        repository protocol.
    :class:`~domain.buckets.BucketEventHistoryCatalogue`
        Domain payload encrypted by this repository.
    :class:`~domain.buckets.BucketEventHistoryRepositoryProtocol`
        Domain port this concrete persistence adapter implements.
    :data:`~adapters.persistence.storage.BUCKET_EVENT_HISTORY_NAMESPACE`
        Central namespace, sensitivity, schema-version, and singleton-key
        contract for these secure objects.
    :func:`~adapters.persistence.storage.secure_object_repository_for_active_bucket`
        Runtime storage factory used when no secure-object repository is injected.
    :mod:`~application.bucket_maintenance`
        Application lifecycle surface that records bucket-maintenance events
        through this repository.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ValidationError

from ....core import ABSENT_SECURE_OBJECT_REVISION_ID
from ....core.external_constants import UTF_8_ENCODING
from ....core.logging import get_logger
from ....core.time import now
from ....domain.buckets import BucketEventHistoryCatalogue, BucketEventHistoryPersistenceError
from ..storage import BUCKET_EVENT_HISTORY_NAMESPACE

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ..storage import SecureObjectRepository, SecureObjectWrite

_LOGGER = get_logger(__name__)
_NAMESPACE = BUCKET_EVENT_HISTORY_NAMESPACE.namespace
_OBJECT_KEY = BUCKET_EVENT_HISTORY_NAMESPACE.require_default_object_key()
_CATALOGUE_VERSION = BUCKET_EVENT_HISTORY_NAMESPACE.schema_version


class BucketEventHistoryRepository:
    """Repository over encrypted SQL-backed event-history catalogue storage.

    :data:`~adapters.persistence.storage.BUCKET_EVENT_HISTORY_NAMESPACE`
    is the central profile-local namespace, schema-version, sensitivity, and
    singleton-key contract for the encrypted
    :class:`~domain.buckets.BucketEventHistoryCatalogue`. The catalogue
    preserves the append-only
    :class:`~domain.buckets.BucketEvent` history, is wrapped in
    :class:`~adapters.persistence.storage.Envelope`, and is persisted
    through :class:`~adapters.persistence.storage.SecureObjectRepository`.
    The same envelope can be emitted as a
    :class:`~adapters.persistence.storage.SecureObjectWrite` when sibling
    catalogue updates need one transaction. This class exposes the concrete
    load/save implementation behind
    :class:`~domain.buckets.BucketEventHistoryRepositoryProtocol`.
    """

    def __init__(self, *, objects: SecureObjectRepository | None = None) -> None:
        """Bind to the active profile bucket's secure-object store, or an injected one.

        Args:
            objects: Optional injected secure-object repository (testing seam);
                the active-bucket store is resolved at runtime when ``None``.
        """
        if objects is not None:
            self._objects = objects
            return
        from ..storage import secure_object_repository_for_active_bucket

        self._objects = secure_object_repository_for_active_bucket()

    @property
    def secure_object_repository(self) -> SecureObjectRepository:
        """Return the secure-object backend used by this catalogue.

        Returns:
            The
            :class:`~adapters.persistence.storage.SecureObjectRepository`
            backing this repository.
        """
        return self._objects

    def exists(self) -> bool:
        """Return whether a bucket-event-history catalogue has been persisted."""
        return self._objects.exists(_NAMESPACE, _OBJECT_KEY)

    def load(self) -> BucketEventHistoryCatalogue:
        """Return the persisted catalogue or an empty catalogue if absent.

        Returns:
            The deserialised
            :class:`~domain.buckets.BucketEventHistoryCatalogue`, or a fresh
            empty instance when no database object is present.

        Raises:
            :class:`~domain.buckets.BucketEventHistoryPersistenceError`: If
                secure-object classification, envelope version, or payload
                validation fails.
        """
        catalogue, _revision_id = self.load_revisioned()
        return catalogue

    def load_revisioned(self) -> tuple[BucketEventHistoryCatalogue, str]:
        """Load the catalogue and the exact secure-object revision observed."""
        from ..storage import (
            ClassificationError,
            Envelope,
            EnvelopeVersionError,
            SensitivityClass,
        )

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
            return BucketEventHistoryCatalogue(), ABSENT_SECURE_OBJECT_REVISION_ID
        try:
            envelope = Envelope[BucketEventHistoryCatalogue].model_validate_json(record.payload)
        except ValidationError as exc:
            _LOGGER.error("bucket-event-history catalogue schema drift", exc_info=True)
            raise BucketEventHistoryPersistenceError(
                context={
                    "namespace": _NAMESPACE,
                    "object_key": _OBJECT_KEY,
                    "recovery": "aeat config repair --help",
                },
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
        return envelope.payload, record.revision_id

    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        """Persist ``catalogue`` atomically through the secure-object repository.

        Args:
            catalogue: The
                :class:`~domain.buckets.BucketEventHistoryCatalogue` to
                persist.
        """
        self._objects.save_many((self.to_secure_object_write(catalogue),))

    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Return the secure-object upsert for ``catalogue`` without committing it.

        The returned
        :class:`~adapters.persistence.storage.SecureObjectWrite` carries the
        same :class:`~adapters.persistence.storage.Envelope` and
        :class:`~adapters.persistence.storage.SensitivityClass`
        classification that :meth:`save` would persist directly.
        """
        from ..storage import Envelope, SecureObjectWrite, SensitivityClass

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
            payload=envelope.model_dump_json().encode(UTF_8_ENCODING),
            expected_revision_id=expected_revision_id,
        )


__all__ = [
    "BucketEventHistoryRepository",
]
