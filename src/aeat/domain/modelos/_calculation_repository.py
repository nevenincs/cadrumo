"""Encrypted SQL repository for the calculation-revision catalogue.

Persists and loads :class:`CalculationRevision` records via
:class:`SecureObjectRepository` at :class:`SensitivityClass` FINANCIAL.
Each record is wrapped in an :class:`Envelope` before being written to
the encrypted BLOB per profile bucket.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.logging import get_logger
from ...core.time import now
from ._calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    assert_revision_snapshot_evidence_coverage,
)
from ._errors import ModeloError
from ._runtime_repository import resolve_modelo_repository_bucket_id, secure_objects_for_modelo_bucket

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ...adapters.persistence.storage import SecureObjectRepository, SecureObjectWrite

_LOGGER = get_logger(__name__)
_CALCULATION_NAMESPACE = "aeat.domain.modelos.calculation_revisions"
_CALCULATION_OBJECT_KEY = "catalogue"
_CALCULATION_CATALOGUE_VERSION = 1
_CALCULATION_PERSISTENCE_MESSAGE = "errors.fail.fail_modelo_calculation_revision_persistence"


class CalculationRevisionPersistenceError(ModeloError):
    """Raised when the calculation-revision catalogue cannot be persisted or loaded."""


class CalculationRevisionCatalogueRepository:
    """Read / write the calculation-revision catalogue in encrypted storage."""

    def __init__(self, *, bucket_id: str | None = None, objects: SecureObjectRepository | None = None) -> None:
        self._bucket_id = bucket_id.strip() if bucket_id is not None else None
        if objects is not None:
            self._objects = objects
            return
        self._bucket_id = resolve_modelo_repository_bucket_id(
            bucket_id,
            error_type=CalculationRevisionPersistenceError,
        )
        self._objects = secure_objects_for_modelo_bucket(self._bucket_id)

    @property
    def bucket_id(self) -> str | None:
        """Identifier of the per-profile storage bucket this repository reads and writes.

        A modelo (an AEAT tax form or declaration) carries calculation revisions
        per filing profile, and each profile owns its own encrypted bucket. This
        property exposes the resolved bucket identifier, or ``None`` when the
        repository was constructed against a caller-supplied ``SecureObjectRepository``
        rather than a resolved bucket.

        Returns:
            The trimmed bucket identifier, or ``None`` when no bucket was resolved.
        """
        return self._bucket_id

    def exists(self) -> bool:
        """Report whether a calculation-revision catalogue has been persisted.

        Checks the encrypted store for an object under this repository's namespace
        and key without decrypting or validating it, so a ``True`` result attests
        to presence only, not integrity.

        Returns:
            ``True`` when a stored catalogue object exists, ``False`` otherwise.
        """
        return self._objects.exists(_CALCULATION_NAMESPACE, _CALCULATION_OBJECT_KEY)

    def load(self) -> CalculationRevisionCatalogue:
        """Load and decrypt the persisted calculation-revision catalogue.

        A calculation revision is a dated, computed version of a modelo's casilla
        values (a casilla is a numbered box on an AEAT form); the catalogue is the
        keyed collection of those revisions. The stored record is decrypted, its
        ``Envelope`` parsed, and its sensitivity classification and schema version
        checked before the payload is returned. When nothing has been persisted yet,
        an empty ``CalculationRevisionCatalogue`` is returned rather than raising.

        Returns:
            The persisted :class:`CalculationRevisionCatalogue`, or an empty one when no
            record exists.

        Raises:
            CalculationRevisionPersistenceError: If the stored record fails the
                FINANCIAL classification check, or its envelope schema version
                exceeds the version this consumer supports, or an integrity error
                surfaces while decrypting and decoding the record.
        """
        from ...adapters.persistence.storage import Envelope, SensitivityClass
        from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError

        try:
            record = self._objects.load(
                _CALCULATION_NAMESPACE,
                _CALCULATION_OBJECT_KEY,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=_CALCULATION_CATALOGUE_VERSION,
            )
        except (ClassificationError, EnvelopeVersionError) as exc:
            _LOGGER.error("calculation-revision catalogue integrity error", exc_info=True)
            raise CalculationRevisionPersistenceError(
                "calculation-revision catalogue integrity error",
                translated_message=_CALCULATION_PERSISTENCE_MESSAGE,
                context={
                    "reason": "secure_object_integrity",
                    "cause_type": type(exc).__name__,
                },
            ) from exc
        if record is None:
            return CalculationRevisionCatalogue()
        envelope = Envelope[CalculationRevisionCatalogue].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not SensitivityClass.FINANCIAL:
            _LOGGER.error(
                "calculation-revision catalogue classification mismatch",
                extra={
                    "expected_classification": SensitivityClass.FINANCIAL.value,
                    "actual_classification": envelope.classification.value,
                },
            )
            raise CalculationRevisionPersistenceError(
                "calculation-revision catalogue classification mismatch",
                translated_message=_CALCULATION_PERSISTENCE_MESSAGE,
                context={
                    "reason": "classification_mismatch",
                    "expected_classification": SensitivityClass.FINANCIAL.value,
                    "actual_classification": envelope.classification.value,
                },
            )
        if envelope.schema_version > _CALCULATION_CATALOGUE_VERSION:
            _LOGGER.error(
                "calculation-revision catalogue envelope version unsupported",
                extra={
                    "stored_schema_version": envelope.schema_version,
                    "max_supported_version": _CALCULATION_CATALOGUE_VERSION,
                },
            )
            raise CalculationRevisionPersistenceError(
                "calculation-revision catalogue envelope version unsupported",
                translated_message=_CALCULATION_PERSISTENCE_MESSAGE,
                context={
                    "reason": "unsupported_envelope_version",
                    "stored_schema_version": envelope.schema_version,
                    "max_supported_version": _CALCULATION_CATALOGUE_VERSION,
                },
            )
        # Post-roundtrip coverage gate: every loaded revision's bundled
        # ledger evidence must cover the same contributor set as its
        # fingerprint snapshot. A row silently dropped after persistence
        # surfaces here on load rather than shipping an unexplainable casilla.
        for revision in envelope.payload.values():
            assert_revision_snapshot_evidence_coverage(revision)
        return envelope.payload

    def save(self, catalogue: CalculationRevisionCatalogue) -> None:
        """Persist the calculation-revision catalogue to encrypted storage.

        Wraps the catalogue (the keyed collection of a modelo's dated calculation
        revisions) in an ``Envelope`` stamped with the current schema version, write
        time, and FINANCIAL sensitivity classification, then writes the serialised
        envelope to the encrypted store under this repository's namespace and key.
        An existing catalogue object at that location is overwritten.

        Args:
            catalogue: The ``CalculationRevisionCatalogue`` to serialise and store.
        """
        from ...adapters.persistence.storage import Envelope, SensitivityClass

        envelope = Envelope[CalculationRevisionCatalogue](
            schema_version=_CALCULATION_CATALOGUE_VERSION,
            written_at=now(),
            classification=SensitivityClass.FINANCIAL,
            payload=catalogue,
        )
        self._objects.save(
            namespace=_CALCULATION_NAMESPACE,
            object_key=_CALCULATION_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_CALCULATION_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

    def to_secure_object_write(self, catalogue: CalculationRevisionCatalogue) -> SecureObjectWrite:
        """Return the :class:`SecureObjectWrite` upsert for ``catalogue`` without committing it.

        Mirrors the bucket-event-history repository so the catalogue save can be
        co-emitted with related secure objects (e.g. the participation index) in
        one ``save_with_secure_object_writes`` unit of work.
        """
        from ...adapters.persistence.storage import Envelope, SecureObjectWrite, SensitivityClass

        envelope = Envelope[CalculationRevisionCatalogue](
            schema_version=_CALCULATION_CATALOGUE_VERSION,
            written_at=now(),
            classification=SensitivityClass.FINANCIAL,
            payload=catalogue,
        )
        return SecureObjectWrite(
            namespace=_CALCULATION_NAMESPACE,
            object_key=_CALCULATION_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_CALCULATION_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

    def save_with_secure_object_writes(
        self,
        catalogue: CalculationRevisionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Persist ``catalogue`` plus related secure objects in one unit of work.

        The catalogue save and every extra write land or fail together in a
        single SQL transaction, so the participation index co-emitted here can
        never drift from the calculation revision it indexes (per the
        composition-service single-writer discipline).
        """
        self._objects.save_many((self.to_secure_object_write(catalogue), *extra_writes))


def upsert_calculation_revision(
    catalogue: CalculationRevisionCatalogue,
    revision: CalculationRevision,
) -> CalculationRevisionCatalogue:
    """Return a new :class:`CalculationRevisionCatalogue` with ``revision`` inserted or replaced.

    Args:
        catalogue: Source catalogue to update.
        revision: The :class:`CalculationRevision` to insert or replace.
    """
    mapping = dict(catalogue.revisions)
    mapping[revision.calculation_revision_id] = revision
    return CalculationRevisionCatalogue(revisions=mapping)


__all__ = [
    "CalculationRevisionCatalogueRepository",
    "CalculationRevisionPersistenceError",
    "upsert_calculation_revision",
]
