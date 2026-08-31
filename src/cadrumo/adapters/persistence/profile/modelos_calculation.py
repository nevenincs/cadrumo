"""Encrypted SQL repository for the calculation-revision catalogue.

:class:`CalculationRevisionCatalogueRepository` persists and loads
:class:`~CalculationRevision` records in a
:class:`~CalculationRevisionCatalogue` via
:class:`~adapters.persistence.storage.SecureObjectRepository` at
``FINANCIAL`` :class:`~adapters.persistence.storage.SensitivityClass`.
Each catalogue is wrapped in
:class:`~adapters.persistence.storage.Envelope` before being written to
the encrypted BLOB per profile bucket.

This concrete repository is the persistence adapter behind the read-side
:class:`~CalculationRevisionCatalogueRepositoryProtocol`. It
lives in the persistence adapter (not in :mod:`~domain.modelos`) because its
secure-object coupling is SQL/crypto-bound; the domain package owns only the
typed :class:`~CalculationRevisionCatalogue` model, the pure
:func:`~domain.modelos.upsert_calculation_revision` mutator, and the
:class:`~CalculationRevisionPersistenceError` boundary error.
The namespace/version constants are redeclared here as the persisted-envelope
contract; the strings are preserved to avoid orphaning persisted envelopes.

See Also:
    :mod:`~adapters.persistence.profile._modelo_runtime`
        Bucket-id resolution and runtime secure-object factory shared by modelo
        persistence adapters.
    :class:`~CalculationRevisionCatalogue`
        Domain catalogue payload encrypted by this repository.
    :class:`~CalculationRevisionCatalogueRepositoryProtocol`
        Domain port this concrete persistence adapter implements.
    :data:`~adapters.persistence.storage.MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE`
        Central namespace, sensitivity, schema-version, and singleton-key
        contract for these secure objects.
    :class:`~adapters.persistence.storage.SecureObjectRepository`
        Runtime-created encrypted storage boundary used for load/save.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ValidationError

from ....core.bucket_pointer import resolve_repository_bucket_id
from ....core.external_constants import UTF_8_ENCODING
from ....core.identity import SubjectTaxId
from ....core.logging import get_logger
from ....core.modelo import Modelo
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.modelos.calculation_repository import CalculationRevisionPersistenceError
from ....domain.modelos.calculation_revision import (
    CalculationRevisionCatalogue,
    assert_revision_snapshot_evidence_coverage,
)
from ....domain.modelos.calculation_revision_aggregate import (
    CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY,
    CalculationRevisionAggregateContext,
)
from ....domain.modelos.errors import raise_catalogue_integrity_error
from ..storage._secure_object_namespaces import MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE
from ..storage.runtime_repository import secure_object_repository_for_bucket
from ._secure_enveloped_document import ProfileEnvelopedModelSecurePersistence

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ..storage.sql import SecureObjectRepository, SecureObjectWrite

_LOGGER = get_logger(__name__)
_CALCULATION_NAMESPACE = MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.namespace
_CALCULATION_OBJECT_KEY = MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.require_default_object_key()
_CALCULATION_CATALOGUE_VERSION = MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.schema_version
_CALCULATION_CATALOGUE_SENSITIVITY = MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.sensitivity
_CALCULATION_PERSISTENCE_MESSAGE = "errors.fail.fail_modelo_calculation_revision_persistence"


class CalculationRevisionCatalogueRepository:
    """Repository over encrypted SQL-backed calculation-revision catalogue storage.

    :data:`~adapters.persistence.storage.MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE`
    is the central namespace, schema-version, sensitivity, and singleton-key
    contract for the encrypted :class:`CalculationRevisionCatalogue` row. The
    write path (``to_secure_object_write`` / ``save`` / ``exists``) composes
    :class:`~adapters.persistence.profile._secure_enveloped_document.ProfileEnvelopedModelSecurePersistence`
    for the shared Envelope-construction mechanic; ``load`` stays hand-rolled
    here because it translates a classification or schema-version mismatch
    into :class:`CalculationRevisionPersistenceError` via
    :func:`~domain.modelos.raise_catalogue_integrity_error`, and runs the
    post-load ledger-evidence coverage gate
    (:func:`~domain.modelos.assert_revision_snapshot_evidence_coverage`) the
    shared kernel has no domain knowledge of. The class exposes the concrete
    load/save implementation behind
    :class:`~CalculationRevisionCatalogueRepositoryProtocol`.
    """

    def __init__(
        self,
        *,
        bucket_id: str | None = None,
        objects: SecureObjectRepository | None = None,
        m303_rectificativa_taxpayer_tax_id: SubjectTaxId | None = None,
    ) -> None:
        """Bind the repository to a bucket id and/or an explicit secure-object store."""
        self._bucket_id = bucket_id.strip() if bucket_id is not None else None
        self._m303_rectificativa_taxpayer_tax_id = m303_rectificativa_taxpayer_tax_id
        if objects is not None:
            self._objects = objects
        else:
            self._bucket_id = resolve_repository_bucket_id(
                bucket_id,
                error_type=CalculationRevisionPersistenceError,
            )
            self._objects = secure_object_repository_for_bucket(self._bucket_id)
        self._storage = ProfileEnvelopedModelSecurePersistence(
            objects=self._objects,
            definition=MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE,
            model_type=CalculationRevisionCatalogue,
            empty_document=CalculationRevisionCatalogue,
            serialization_context={"secure_calculation_revision": True},
        )

    @property
    def bucket_id(self) -> str | None:
        """Identifier of the per-profile storage bucket this repository reads and writes.

        A modelo (an AEAT tax form or declaration) carries calculation revisions
        per filing profile, and each profile owns its own encrypted bucket. This
        property exposes the resolved bucket identifier, or ``None`` when the
        repository was constructed against a caller-supplied
        :class:`~adapters.persistence.storage.SecureObjectRepository`
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
        return self._storage.exists()

    def load(self) -> CalculationRevisionCatalogue:
        """Load and decrypt the persisted calculation-revision catalogue.

        A calculation revision is a dated, computed version of a modelo's casilla
        values (a casilla is a numbered box on an AEAT form); the catalogue is the
        keyed collection of those revisions. The stored record is decrypted, its
        :class:`~adapters.persistence.storage.Envelope` parsed, and its
        sensitivity classification and schema version checked before the payload
        is returned. When nothing has been persisted yet, an empty
        :class:`CalculationRevisionCatalogue` is returned rather than raising.

        Returns:
            The persisted :class:`CalculationRevisionCatalogue`, or an empty one when no
            record exists.

        Raises:
            :class:`~CalculationRevisionPersistenceError`: If
                the stored record fails the FINANCIAL classification check, or its
                envelope schema version exceeds the version this consumer
                supports, or an integrity error surfaces while decrypting and
                decoding the record.
        """
        from ..storage._schema_lineage import (
            inner_envelope_classification_is_expected,
            inner_envelope_version_is_current,
        )
        from ..storage.envelope._envelope import Envelope
        from ..storage.errors import ClassificationError, EnvelopeVersionError

        try:
            record = self._objects.load(
                _CALCULATION_NAMESPACE,
                _CALCULATION_OBJECT_KEY,
                expected_class=_CALCULATION_CATALOGUE_SENSITIVITY,
                max_supported_version=_CALCULATION_CATALOGUE_VERSION,
            )
        except (ClassificationError, EnvelopeVersionError) as exc:
            raise_catalogue_integrity_error(
                exc,
                error_cls=CalculationRevisionPersistenceError,
                label="calculation-revision",
                translated_message=_CALCULATION_PERSISTENCE_MESSAGE,
                logger=_LOGGER,
            )
        if record is None:
            return CalculationRevisionCatalogue()
        aggregate_context = self._calculation_revision_aggregate_context()
        envelope: Envelope[CalculationRevisionCatalogue] | None = None
        validation_failed = False
        try:
            envelope = Envelope[CalculationRevisionCatalogue].model_validate_json(
                record.payload.decode(UTF_8_ENCODING),
                context={
                    CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY: aggregate_context,
                    "secure_calculation_revision": True,
                },
            )
        except ValidationError:
            validation_failed = True
        if validation_failed or envelope is None:
            raise CalculationRevisionPersistenceError(
                "calculation-revision catalogue payload is invalid",
                translated_message=_CALCULATION_PERSISTENCE_MESSAGE,
                context={"reason": "invalid_payload"},
            )
        if not inner_envelope_classification_is_expected(envelope.classification, _CALCULATION_CATALOGUE_SENSITIVITY):
            _LOGGER.error(
                "calculation-revision catalogue classification mismatch",
                extra={
                    "expected_classification": _CALCULATION_CATALOGUE_SENSITIVITY.value,
                    "actual_classification": envelope.classification.value,
                },
            )
            raise CalculationRevisionPersistenceError(
                "calculation-revision catalogue classification mismatch",
                translated_message=_CALCULATION_PERSISTENCE_MESSAGE,
                context={
                    "reason": "classification_mismatch",
                    "expected_classification": _CALCULATION_CATALOGUE_SENSITIVITY.value,
                    "actual_classification": envelope.classification.value,
                },
            )
        if not inner_envelope_version_is_current(envelope.schema_version, _CALCULATION_CATALOGUE_VERSION):
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

    def _calculation_revision_aggregate_context(self) -> CalculationRevisionAggregateContext:
        """Load every persisted authority needed to revalidate rectificativa revisions."""
        from .justificante import JustificanteRepository
        from .modelos_filing import ModeloRecordCatalogueRepository
        from .modelos_work_units import WorkUnitCatalogueRepository

        work_units = WorkUnitCatalogueRepository(objects=self._objects).load()
        filing_records = ModeloRecordCatalogueRepository(objects=self._objects).load()
        justificantes = tuple(JustificanteRepository(objects=self._objects).iter_justificantes())
        snapshots: dict[str, RegistrySnapshot] = {
            unit.work_unit_id: bundled_authority().snapshot(
                Modelo.M303.value,
                filing_year=unit.filing_year,
                period=unit.period.registry_token,
            )
            for unit in work_units.values()
            if unit.modelo == Modelo.M303.value
        }
        return CalculationRevisionAggregateContext(
            work_units=work_units,
            filing_records=filing_records,
            justificantes=justificantes,
            registry_snapshots=snapshots,
            expected_taxpayer_tax_id=self._m303_rectificativa_taxpayer_tax_id,
        )

    def save(self, catalogue: CalculationRevisionCatalogue) -> None:
        """Persist the calculation-revision catalogue to encrypted storage.

        Wraps the catalogue (the keyed collection of a modelo's dated
        calculation revisions) in an
        :class:`~adapters.persistence.storage.Envelope` stamped with the
        current schema version, write time, and ``FINANCIAL`` sensitivity
        classification, then writes the serialised envelope to the encrypted
        store under this repository's namespace and key. An existing catalogue
        object at that location is overwritten.

        Args:
            catalogue: The :class:`CalculationRevisionCatalogue` to serialise and
                store.
        """
        self._storage.save(catalogue)

    def load_revisioned(self) -> tuple[CalculationRevisionCatalogue, str]:
        """Return the catalogue and the revision id it was read at.

        The read a guarded co-commit needs. A calculate run composes this
        catalogue with the work-unit catalogue and the creation event in one
        unit of work, so it cannot use a self-committing mutation, and without
        the revision it would write back the whole catalogue and discard a
        revision another run added in between. A dropped calculation revision
        is a dropped tax computation.
        """
        return self._storage.load_revisioned()

    def to_secure_object_write(
        self,
        catalogue: CalculationRevisionCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Return the secure-object upsert for ``catalogue`` without committing it.

        The returned :class:`~adapters.persistence.storage.SecureObjectWrite`
        carries the same :class:`~adapters.persistence.storage.Envelope`
        and :class:`~adapters.persistence.storage.SensitivityClass`
        classification that :meth:`save` would persist directly. It can be
        co-emitted with related secure objects (e.g. the participation index) in
        one :meth:`save_with_secure_object_writes` unit of work.

        Pass ``expected_revision_id`` from :meth:`load_revisioned` whenever the
        catalogue was DERIVED from a read; omitting it writes the whole
        singleton row back unconditionally.
        """
        return self._storage.to_secure_object_write(catalogue, expected_revision_id=expected_revision_id)

    def save_with_secure_object_writes(
        self,
        catalogue: CalculationRevisionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
        *,
        expected_revision_id: str | None = None,
    ) -> None:
        """Persist ``catalogue`` plus related secure objects in one unit of work.

        The catalogue save and every extra write land or fail together in a
        single SQL transaction, so the participation index co-emitted here can
        never drift from the calculation revision it indexes (per the
        composition-service single-writer discipline).

        Args:
            catalogue: The :class:`CalculationRevisionCatalogue` to persist.
            extra_writes: Additional
                :class:`~adapters.persistence.storage.SecureObjectWrite`
                objects to commit atomically with the catalogue.
            expected_revision_id: The revision :meth:`load_revisioned` reported
                for the catalogue this one was derived from. Atomicity is what
                this method already gave; without the revision it still writes
                the whole singleton row back, so a revision another calculate
                run added between the read and this call is discarded -- and a
                dropped calculation revision is a dropped tax computation. Omit
                only when the catalogue was not derived from a read.
        """
        self._objects.save_many(
            (self.to_secure_object_write(catalogue, expected_revision_id=expected_revision_id), *extra_writes),
        )


__all__ = [
    "CalculationRevisionCatalogueRepository",
]
