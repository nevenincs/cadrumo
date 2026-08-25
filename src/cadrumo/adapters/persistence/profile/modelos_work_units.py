"""Encrypted SQL repository for the modelo work-unit catalogue.

:class:`WorkUnitCatalogueRepository` persists :class:`WorkUnit` records in a
:class:`WorkUnitCatalogue` at ``FINANCIAL``
:class:`~adapters.persistence.storage.SensitivityClass` through
:class:`~adapters.persistence.storage.SecureObjectRepository`. The
catalogue is serialised as a single
:class:`~adapters.persistence.storage.Envelope`-wrapped JSON payload keyed
by a stable namespace and object key; the underlying column is encrypted so no
plaintext work-unit metadata lands on disk.

This concrete repository is the persistence adapter behind the read-side
:class:`~domain.modelos.WorkUnitCatalogueRepositoryProtocol`. It lives in
the persistence adapter (not in :mod:`~domain.modelos`) because its
secure-object coupling is SQL/crypto-bound; the domain package owns only the
typed :class:`WorkUnitCatalogue` model and its pure catalogue mutators.

See Also:
    :mod:`~adapters.persistence.profile._modelo_runtime`
        Bucket-id resolution and runtime secure-object factory shared by modelo
        persistence adapters.
    :class:`~domain.modelos.WorkUnitCatalogue`
        Domain catalogue payload encrypted by this repository.
    :class:`~domain.modelos.WorkUnitCatalogueRepositoryProtocol`
        Domain port this concrete persistence adapter implements.
    :data:`~adapters.persistence.storage.MODELO_WORK_UNIT_CATALOGUE_NAMESPACE`
        Central namespace, sensitivity, schema-version, and singleton-key
        contract for these secure objects.
    :mod:`~adapters.persistence.profile.modelos_calculation`
        Sibling calculation-revision repository referenced by work-unit current
        and verification lifecycle state.
    :mod:`~application.modelo`
        Application facade that creates, calculates, verifies, files, and
        exports work units from this catalogue.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....core.bucket_pointer import resolve_repository_bucket_id
from ....core.external_constants import UTF_8_ENCODING
from ....core.logging import get_logger
from ....domain.modelos import (
    WorkUnitCatalogue,
    WorkUnitPersistenceError,
    raise_catalogue_integrity_error,
)
from ..storage import MODELO_WORK_UNIT_CATALOGUE_NAMESPACE, secure_object_repository_for_bucket
from ._secure_enveloped_document import ProfileEnvelopedModelSecurePersistence

if TYPE_CHECKING:
    from collections.abc import Callable

    # pragma: no cover — import-cycle guard
    from ..storage import SecureObjectRepository, SecureObjectWrite

_LOGGER = get_logger(__name__)
_WORK_UNIT_NAMESPACE = MODELO_WORK_UNIT_CATALOGUE_NAMESPACE.namespace
_WORK_UNIT_OBJECT_KEY = MODELO_WORK_UNIT_CATALOGUE_NAMESPACE.require_default_object_key()
_WORK_UNIT_CATALOGUE_VERSION = MODELO_WORK_UNIT_CATALOGUE_NAMESPACE.schema_version
_WORK_UNIT_CATALOGUE_SENSITIVITY = MODELO_WORK_UNIT_CATALOGUE_NAMESPACE.sensitivity
_WORK_UNIT_PERSISTENCE_MESSAGE = "errors.fail.fail_modelo_work_unit_persistence"


class WorkUnitCatalogueRepository:
    """Repository over encrypted SQL-backed work-unit catalogue storage.

    A single envelope-wrapped catalogue object holds every work unit. Loads
    return an empty catalogue when no object has been persisted yet (no
    separate "fresh install" path is needed). The write path
    (``to_secure_object_write`` / ``save`` / ``exists``) composes
    :class:`~adapters.persistence.profile._secure_enveloped_document.ProfileEnvelopedModelSecurePersistence`
    for the shared Envelope-construction mechanic; ``load`` stays hand-rolled
    here because it translates a classification or schema-version mismatch
    into :class:`WorkUnitPersistenceError` via
    :func:`~domain.modelos.raise_catalogue_integrity_error`. This class is
    the concrete implementation behind
    :class:`~domain.modelos.WorkUnitCatalogueRepositoryProtocol`.
    """

    def __init__(self, *, bucket_id: str | None = None, objects: SecureObjectRepository | None = None) -> None:
        """Bind to a profile bucket's secure-object store, or an injected one.

        Args:
            bucket_id: Profile bucket whose encrypted store backs this repository;
                resolved from the active session when ``None``.
            objects: Optional injected secure-object repository (testing seam).
        """
        self._bucket_id = bucket_id.strip() if bucket_id is not None else None
        if objects is not None:
            self._objects = objects
        else:
            self._bucket_id = resolve_repository_bucket_id(bucket_id, error_type=WorkUnitPersistenceError)
            self._objects = secure_object_repository_for_bucket(self._bucket_id)
        self._storage = ProfileEnvelopedModelSecurePersistence(
            objects=self._objects,
            definition=MODELO_WORK_UNIT_CATALOGUE_NAMESPACE,
            model_type=WorkUnitCatalogue,
            empty_document=WorkUnitCatalogue,
        )

    @property
    def bucket_id(self) -> str | None:
        """Return the profile bucket id when this repository resolved one."""
        return self._bucket_id

    def exists(self) -> bool:
        """Return whether a work-unit catalogue object has been persisted."""
        return self._storage.exists()

    def load(self) -> WorkUnitCatalogue:
        """Return the persisted catalogue or an empty catalogue if absent.

        Returns:
            The deserialised :class:`WorkUnitCatalogue`, or an empty instance
            when no object has been persisted yet.

        Raises:
            :class:`WorkUnitPersistenceError`: When the persisted envelope's
                classification or schema version disagrees with the consumer's
                contract.
        """
        from ..storage import (
            ClassificationError,
            Envelope,
            EnvelopeVersionError,
            inner_envelope_classification_is_expected,
            inner_envelope_version_is_current,
        )

        try:
            record = self._objects.load(
                _WORK_UNIT_NAMESPACE,
                _WORK_UNIT_OBJECT_KEY,
                expected_class=_WORK_UNIT_CATALOGUE_SENSITIVITY,
                max_supported_version=_WORK_UNIT_CATALOGUE_VERSION,
            )
        except (ClassificationError, EnvelopeVersionError) as exc:
            raise_catalogue_integrity_error(
                exc,
                error_cls=WorkUnitPersistenceError,
                label="work-unit",
                translated_message=_WORK_UNIT_PERSISTENCE_MESSAGE,
                logger=_LOGGER,
            )
        if record is None:
            _LOGGER.debug("work-unit catalogue not found; returning empty catalogue")
            return WorkUnitCatalogue()
        envelope = Envelope[WorkUnitCatalogue].model_validate_json(record.payload.decode(UTF_8_ENCODING))
        if not inner_envelope_classification_is_expected(envelope.classification, _WORK_UNIT_CATALOGUE_SENSITIVITY):
            _LOGGER.error(
                "work-unit catalogue classification mismatch",
                extra={
                    "expected_classification": _WORK_UNIT_CATALOGUE_SENSITIVITY.value,
                    "actual_classification": envelope.classification.value,
                },
            )
            raise WorkUnitPersistenceError(
                "work-unit catalogue classification mismatch",
                translated_message=_WORK_UNIT_PERSISTENCE_MESSAGE,
                context={
                    "reason": "classification_mismatch",
                    "expected_classification": _WORK_UNIT_CATALOGUE_SENSITIVITY.value,
                    "actual_classification": envelope.classification.value,
                },
            )
        if not inner_envelope_version_is_current(envelope.schema_version, _WORK_UNIT_CATALOGUE_VERSION):
            _LOGGER.error(
                "work-unit catalogue envelope version unsupported",
                extra={
                    "stored_schema_version": envelope.schema_version,
                    "max_supported_version": _WORK_UNIT_CATALOGUE_VERSION,
                },
            )
            raise WorkUnitPersistenceError(
                "work-unit catalogue envelope version unsupported",
                translated_message=_WORK_UNIT_PERSISTENCE_MESSAGE,
                context={
                    "reason": "unsupported_envelope_version",
                    "stored_schema_version": envelope.schema_version,
                    "max_supported_version": _WORK_UNIT_CATALOGUE_VERSION,
                },
            )
        catalogue = envelope.payload
        _LOGGER.debug("loaded work-unit catalogue with %d entr(y/ies)", len(catalogue))
        return catalogue

    def save(self, catalogue: WorkUnitCatalogue) -> None:
        """Persist ``catalogue`` as the encrypted singleton object.

        The on-disk database value is an encrypted
        :class:`~adapters.persistence.storage.Envelope` BLOB at the
        :class:`~adapters.persistence.storage.SensitivityClass`
        ``FINANCIAL`` classification.

        Args:
            catalogue: The :class:`WorkUnitCatalogue` to persist.
        """
        self._storage.save(catalogue)
        _LOGGER.info("saved work-unit catalogue with %d entr(y/ies)", len(catalogue))

    def mutate(self, mutation: Callable[[WorkUnitCatalogue], WorkUnitCatalogue]) -> WorkUnitCatalogue:
        """Apply ``mutation`` to the stored catalogue as one revision-guarded unit of work.

        The catalogue is a SINGLETON row, so touching one work unit rewrites all
        of them. Performed unguarded, a work unit created or advanced by a
        concurrent caller is discarded by whichever write lands second, and
        nothing reports it: the surviving entries are individually intact and
        the missing one leaves no hole.

        ``mutation`` is re-applied to the newly-current catalogue on a conflict,
        so it MUST be a pure function of the catalogue it is handed -- a
        decision closed over from an earlier read would be replayed against a
        catalogue it was never true of.
        """
        catalogue = self._storage.mutate(mutation)
        _LOGGER.info("mutated work-unit catalogue with %d entr(y/ies)", len(catalogue))
        return catalogue

    def to_secure_object_write(
        self,
        catalogue: WorkUnitCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Return the secure-object upsert for ``catalogue`` without committing it.

        Lets a caller advance the work-unit pointer in the SAME unit of work as
        the calculation, filing, and event catalogues the pointer names, so a
        failure cannot leave an advanced pointer standing over state that never
        committed. The returned
        :class:`~adapters.persistence.storage.SecureObjectWrite` carries the same
        :class:`~adapters.persistence.storage.Envelope` and
        :class:`~adapters.persistence.storage.SensitivityClass` classification
        :meth:`save` would persist directly.
        """
        write = self._storage.to_secure_object_write(catalogue)
        if expected_revision_id is not None:
            return write.model_copy(update={"expected_revision_id": expected_revision_id})
        return write

    def load_revisioned(self) -> tuple[WorkUnitCatalogue, str]:
        """Return the catalogue and the revision id it was read at.

        The read a guarded co-commit needs. A lifecycle transition composes this
        catalogue with the event that records it, so it cannot use the
        self-committing :meth:`mutate`, and without the revision its batch
        rewrites the whole singleton row over a unit another caller created.
        """
        return self._storage.load_revisioned()

    def save_with_secure_object_writes(
        self,
        catalogue: WorkUnitCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
        *,
        expected_revision_id: str | None = None,
    ) -> None:
        """Persist ``catalogue`` plus related secure objects in one unit of work.

        The catalogue save and every extra write land or fail together in a
        single SQL transaction. A work-unit lifecycle transition that saved the
        catalogue and emitted its bucket event afterwards could come to rest
        durable-but-unrecorded: the created, renamed, or discarded unit survived
        while the history had no matching entry and no marker named the gap.
        Folding the event's write in here puts the state and its promised event
        in one transaction, so neither can land without the other.

        Args:
            catalogue: The :class:`WorkUnitCatalogue` to persist.
            extra_writes: Additional
                :class:`~adapters.persistence.storage.SecureObjectWrite`
                objects to commit atomically with the catalogue.
            expected_revision_id: The revision :meth:`load_revisioned` reported
                for the catalogue this one was derived from. Atomicity is what
                the batch already gave; the revision is what stops it writing
                the whole singleton row back over a work unit another caller
                created between the read and this call.
        """
        self._objects.save_many(
            (self.to_secure_object_write(catalogue, expected_revision_id=expected_revision_id), *extra_writes),
        )


__all__ = [
    "WorkUnitCatalogueRepository",
]
