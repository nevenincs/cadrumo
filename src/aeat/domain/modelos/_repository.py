"""Encrypted SQL repository for the modelo work-unit catalogue.

The work-unit catalogue persists at :class:`SensitivityClass` FINANCIAL
through the same :class:`aeat.adapters.persistence.storage.sql.SecureObjectRepository`
backend the transaction and invoice catalogues use. The catalogue is
serialised as a single :class:`Envelope`-wrapped JSON payload keyed by
a stable namespace + object key; the underlying column is encrypted so
no plaintext work-unit metadata lands on disk.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.logging import get_logger
from ...core.time import now

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ...adapters.persistence.storage import SecureObjectRepository
from ._errors import ModeloError, raise_catalogue_integrity_error
from ._runtime_repository import resolve_modelo_repository_bucket_id, secure_objects_for_modelo_bucket
from ._work_unit import WorkUnit, WorkUnitCatalogue

_LOGGER = get_logger(__name__)
_WORK_UNIT_NAMESPACE = "aeat.domain.modelos.work_units"
_WORK_UNIT_OBJECT_KEY = "catalogue"
_WORK_UNIT_CATALOGUE_VERSION = 1
_WORK_UNIT_PERSISTENCE_MESSAGE = "errors.fail.fail_modelo_work_unit_persistence"


class WorkUnitPersistenceError(ModeloError):
    """Raised when the work-unit catalogue cannot be loaded or saved."""


class WorkUnitCatalogueRepository:
    """Read / write the work-unit catalogue in the encrypted backend.

    A single envelope-wrapped catalogue object holds every work
    unit. Loads return an empty catalogue when no object has been
    persisted yet (no separate "fresh install" path is needed).
    """

    def __init__(self, *, bucket_id: str | None = None, objects: SecureObjectRepository | None = None) -> None:
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
            WorkUnitPersistenceError: When the persisted envelope's
                classification or schema version disagrees with the
                consumer's contract.
        """
        from ...adapters.persistence.storage import Envelope, SensitivityClass
        from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError

        try:
            record = self._objects.load(
                _WORK_UNIT_NAMESPACE,
                _WORK_UNIT_OBJECT_KEY,
                expected_class=SensitivityClass.FINANCIAL,
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
        envelope = Envelope[WorkUnitCatalogue].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not SensitivityClass.FINANCIAL:
            _LOGGER.error(
                "work-unit catalogue classification mismatch",
                extra={
                    "expected_classification": SensitivityClass.FINANCIAL.value,
                    "actual_classification": envelope.classification.value,
                },
            )
            raise WorkUnitPersistenceError(
                "work-unit catalogue classification mismatch",
                translated_message=_WORK_UNIT_PERSISTENCE_MESSAGE,
                context={
                    "reason": "classification_mismatch",
                    "expected_classification": SensitivityClass.FINANCIAL.value,
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
        """Persist ``catalogue`` as the encrypted singleton object."""
        from ...adapters.persistence.storage import Envelope, SensitivityClass

        envelope = Envelope[WorkUnitCatalogue](
            schema_version=_WORK_UNIT_CATALOGUE_VERSION,
            written_at=now(),
            classification=SensitivityClass.FINANCIAL,
            payload=catalogue,
        )
        self._objects.save(
            namespace=_WORK_UNIT_NAMESPACE,
            object_key=_WORK_UNIT_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_WORK_UNIT_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )
        _LOGGER.info("saved work-unit catalogue with %d entr(y/ies)", len(catalogue))


def upsert_work_unit(catalogue: WorkUnitCatalogue, unit: WorkUnit) -> WorkUnitCatalogue:
    """Return a new :class:`WorkUnitCatalogue` with ``unit`` inserted or replaced.

    The input catalogue is not mutated. The returned catalogue
    carries the same work units as the input plus ``unit`` at its
    deterministic ``work_unit_id``; any existing entry under that
    id is replaced.
    """
    mapping = dict(catalogue.work_units)
    mapping[unit.work_unit_id] = unit
    return WorkUnitCatalogue(work_units=mapping)


def remove_work_unit(catalogue: WorkUnitCatalogue, work_unit_id: str) -> WorkUnitCatalogue:
    """Return a new catalogue with ``work_unit_id`` removed.

    Removing an absent id is a no-op that returns a value-equal
    catalogue. The original is not mutated.

    Returns:
        A :class:`WorkUnitCatalogue` without the given work unit.
    """
    if work_unit_id not in catalogue.work_units:
        return catalogue
    mapping = dict(catalogue.work_units)
    del mapping[work_unit_id]
    return WorkUnitCatalogue(work_units=mapping)


__all__ = [
    "WorkUnitCatalogueRepository",
    "WorkUnitPersistenceError",
    "remove_work_unit",
    "upsert_work_unit",
]
