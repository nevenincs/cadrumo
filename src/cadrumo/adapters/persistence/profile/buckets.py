"""Encrypted SQL repository for the bucket-event-history catalogue.

:class:`BucketEventHistoryRepository` persists
:class:`~domain.buckets.BucketEventHistoryCatalogue` through
:class:`~adapters.persistence.storage.SecureObjectRepository`, which
handles encrypted BLOB storage and key management for the active profile
bucket. Each stored record is wrapped in an
:class:`~adapters.persistence.storage.Envelope` at
``FINANCIAL`` :class:`~adapters.persistence.storage.SensitivityClass`.

The write path (``to_secure_object_write`` / ``save`` / ``exists``) composes
:class:`~adapters.persistence.profile._secure_enveloped_document.ProfileEnvelopedModelSecurePersistence`
for the shared envelope-construction mechanic. The read path
(``load`` / ``load_revisioned``) stays hand-rolled here rather than routing
through the shared kernel's generic checks: this repository's classification
and schema-version mismatch errors carry a richer, test-asserted
``translated_message``/``context`` shape distinguishing an outer (SQL-row)
integrity failure from an inner (envelope-payload) classification or version
drift, plus a dedicated schema-drift (``ValidationError``) translation none
of that is part of the shared kernel's generic contract, and collapsing it
would be a silent, observable error-message regression for every caller and
test that depends on the specific translated message.

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

from ....core.logging import get_logger
from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ....domain.buckets.event import BucketEventHistoryCatalogue
from ....domain.buckets.event_repository import BucketEventHistoryPersistenceError
from ..storage._secure_object_namespaces import BUCKET_EVENT_HISTORY_NAMESPACE
from ._secure_enveloped_document import ProfileEnvelopedModelSecurePersistence

if TYPE_CHECKING:
    from collections.abc import Callable

    # pragma: no cover — import-cycle guard
    from ..storage.sql import SecureObjectRepository, SecureObjectWrite

_LOGGER = get_logger(__name__)
_NAMESPACE = BUCKET_EVENT_HISTORY_NAMESPACE.namespace
_OBJECT_KEY = BUCKET_EVENT_HISTORY_NAMESPACE.require_default_object_key()
_CATALOGUE_VERSION = BUCKET_EVENT_HISTORY_NAMESPACE.schema_version
_CATALOGUE_SENSITIVITY = BUCKET_EVENT_HISTORY_NAMESPACE.sensitivity


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
    :class:`~domain.buckets.BucketEventHistoryRepositoryProtocol`, composing
    :class:`~adapters.persistence.profile._secure_enveloped_document.ProfileEnvelopedModelSecurePersistence`
    for the write-path envelope mechanic (see module docstring for why the
    read path stays separate).
    """

    def __init__(self, *, objects: SecureObjectRepository | None = None) -> None:
        """Bind to the active profile bucket's secure-object store, or an injected one.

        Args:
            objects: Optional injected secure-object repository (testing seam);
                the active-bucket store is resolved at runtime when ``None``.
        """
        if objects is not None:
            self._objects = objects
        else:
            from ..storage.runtime_repository import secure_object_repository_for_active_bucket

            self._objects = secure_object_repository_for_active_bucket()
        self._storage = ProfileEnvelopedModelSecurePersistence(
            objects=self._objects,
            definition=BUCKET_EVENT_HISTORY_NAMESPACE,
            model_type=BucketEventHistoryCatalogue,
            empty_document=BucketEventHistoryCatalogue,
        )

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
        return self._storage.exists()

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
        from ..storage._schema_lineage import (
            inner_envelope_classification_is_expected,
            inner_envelope_version_is_current,
        )
        from ..storage.envelope._envelope import Envelope
        from ..storage.errors import ClassificationError, EnvelopeVersionError

        try:
            record = self._objects.load(
                _NAMESPACE,
                _OBJECT_KEY,
                expected_class=_CATALOGUE_SENSITIVITY,
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
                },
                translated_message="errors.storage.stored_data_validation_boundary",
            ) from exc
        if not inner_envelope_classification_is_expected(envelope.classification, _CATALOGUE_SENSITIVITY):
            _LOGGER.error(
                "bucket-event-history catalogue classification mismatch classification=%s",
                envelope.classification.value,
            )
            raise BucketEventHistoryPersistenceError(
                context={
                    "namespace": _NAMESPACE,
                    "object_key": _OBJECT_KEY,
                    "classification": envelope.classification.value,
                    "expected": _CATALOGUE_SENSITIVITY.value,
                },
                translated_message="errors.integrity.integrity_storage_classification",
            )
        if not inner_envelope_version_is_current(envelope.schema_version, _CATALOGUE_VERSION):
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

    def append_guarded(
        self,
        appender: Callable[[BucketEventHistoryCatalogue], BucketEventHistoryCatalogue],
        *,
        attempts: int = 4,
    ) -> BucketEventHistoryCatalogue:
        """Append through ``appender`` as one revision-guarded unit of work.

        The event history is a SINGLETON row, so appending one event rewrites
        the whole catalogue. Performed unguarded, two callers recording
        DIFFERENT transitions both read the same catalogue and the later write
        discards the earlier event. Nothing detects it: the events are
        content-addressed, so the survivors all look internally consistent and
        the missing one leaves no gap to notice. On an append-only audit trail
        that is the worst shape of loss -- the record reads as complete.

        The write carries the revision the catalogue was READ at, so the
        substrate refuses it if the row moved, and ``appender`` is re-applied to
        the newly-current catalogue. It is therefore called once per attempt and
        MUST be a pure function of what it is handed.

        Args:
            appender: Builds the next catalogue from the current one.
            attempts: Maximum reads before the contention is surfaced.

        Returns:
            The catalogue as written.

        Raises:
            SecureObjectRevisionConflictError: Contention persisted across every
                attempt.
        """
        from ..storage.errors import SecureObjectRevisionConflictError

        last_conflict: SecureObjectRevisionConflictError | None = None
        for _attempt in range(attempts):
            current, revision_id = self.load_revisioned()
            updated = appender(current)
            try:
                self._objects.save_many(
                    (self.to_secure_object_write(updated, expected_revision_id=revision_id),),
                )
            except SecureObjectRevisionConflictError as exc:
                last_conflict = exc
                continue
            return updated
        if last_conflict is not None:
            raise last_conflict
        raise AssertionError("append_guarded exhausted without a conflict")

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
        write = self._storage.to_secure_object_write(catalogue)
        if expected_revision_id is not None:
            return write.model_copy(update={"expected_revision_id": expected_revision_id})
        return write


def build_bucket_event_history_repository(*, bucket_id: str) -> BucketEventHistoryRepository:
    """Build the encrypted event-history repository for ``bucket_id``."""
    from ..storage.runtime_repository import secure_object_repository_for_bucket

    return BucketEventHistoryRepository(objects=secure_object_repository_for_bucket(bucket_id))


__all__ = [
    "BucketEventHistoryRepository",
    "build_bucket_event_history_repository",
]
