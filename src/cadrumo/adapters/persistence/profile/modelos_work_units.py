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

from ....core.external_constants import UTF_8_ENCODING
from ....core.logging import get_logger
from ....core.time import now
from ....domain.modelos import (
    WorkUnitCatalogue,
    WorkUnitPersistenceError,
    raise_catalogue_integrity_error,
)
from ..storage import MODELO_WORK_UNIT_CATALOGUE_NAMESPACE
from ._modelo_runtime import resolve_modelo_repository_bucket_id, secure_objects_for_modelo_bucket

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ..storage import SecureObjectRepository

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
    separate "fresh install" path is needed). The
    :class:`WorkUnitCatalogue` payload is wrapped in
    :class:`~adapters.persistence.storage.Envelope` before the
    :class:`~adapters.persistence.storage.SecureObjectRepository`
    persists it; this class is the concrete implementation behind
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
            return
        self._bucket_id = resolve_modelo_repository_bucket_id(bucket_id, error_type=WorkUnitPersistenceError)
        self._objects = secure_objects_for_modelo_bucket(self._bucket_id)

    @property
    def bucket_id(self) -> str | None:
        """Return the profile bucket id when this repository resolved one."""
        return self._bucket_id

    def exists(self) -> bool:
        """Return whether a work-unit catalogue object has been persisted."""
        return self._objects.exists(_WORK_UNIT_NAMESPACE, _WORK_UNIT_OBJECT_KEY)

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
        if envelope.classification is not _WORK_UNIT_CATALOGUE_SENSITIVITY:
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
        if envelope.schema_version > _WORK_UNIT_CATALOGUE_VERSION:
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
        from ..storage import Envelope

        envelope = Envelope[WorkUnitCatalogue](
            schema_version=_WORK_UNIT_CATALOGUE_VERSION,
            written_at=now(),
            classification=_WORK_UNIT_CATALOGUE_SENSITIVITY,
            payload=catalogue,
        )
        self._objects.save(
            namespace=_WORK_UNIT_NAMESPACE,
            object_key=_WORK_UNIT_OBJECT_KEY,
            classification=_WORK_UNIT_CATALOGUE_SENSITIVITY,
            schema_version=_WORK_UNIT_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode(UTF_8_ENCODING),
        )
        _LOGGER.info("saved work-unit catalogue with %d entr(y/ies)", len(catalogue))


__all__ = [
    "WorkUnitCatalogueRepository",
]
