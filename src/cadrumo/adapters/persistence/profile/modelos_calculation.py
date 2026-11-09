"""Encrypted SQL repository for the calculation-revision catalogue.

:class:`CalculationRevisionCatalogueRepository` persists and loads
:class:`~CalculationRevision` records in a
:class:`~CalculationRevisionCatalogue` via
:class:`~adapters.persistence.storage.sql.secure_objects.SecureObjectRepository` at
``FINANCIAL`` :class:`~core.classification.policies.SensitivityClass`.
Each catalogue is wrapped in
:class:`~adapters.persistence.storage.envelope.contract.Envelope` before being written to
the encrypted BLOB per profile bucket.

This concrete repository is the persistence adapter behind the read-side
:class:`~CalculationRevisionCatalogueRepositoryProtocol`. It
lives in the persistence adapter (not in :mod:`~domain.modelos`) because its
secure-object coupling is SQL/crypto-bound; the domain package owns only the
typed :class:`~CalculationRevisionCatalogue` model, the pure
:func:`~domain.modelos.calculation_repository.upsert_calculation_revision` mutator, and the
:class:`~CalculationRevisionPersistenceError` boundary error.
The namespace/version constants are redeclared here as the persisted-envelope
contract; the strings are preserved to avoid orphaning persisted envelopes.

See Also:
    ``adapters.persistence.profile._modelo_runtime``
        Bucket-id resolution and runtime secure-object factory shared by modelo
        persistence adapters.
    :class:`~CalculationRevisionCatalogue`
        Domain catalogue payload encrypted by this repository.
    :class:`~CalculationRevisionCatalogueRepositoryProtocol`
        Domain port this concrete persistence adapter implements.
    :data:`~adapters.persistence.storage.secure_object_namespaces.MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE`
        Central namespace, sensitivity, schema-version, and singleton-key
        contract for these secure objects.
    :class:`~adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`
        Runtime-created encrypted storage boundary used for load/save.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import date
from threading import Lock
from typing import TYPE_CHECKING

from pydantic import ValidationError

from cadrumo.domain.calculations.registry.tax_id_format import SubjectTaxId

from ....core.bucket_pointer import resolve_repository_bucket_id
from ....core.diagnostic_log import diagnostic_timing_event
from ....core.hashing import sha256_hex
from ....core.logging import get_logger
from ....core.modelo import Modelo
from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID, SecureObjectWrite
from ....core.time.clock import today_madrid
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.form_codes import form_for_role
from ....domain.calculations.registry.governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
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
from ....domain.modelos.work_unit import WorkUnitCatalogue
from ..storage.crypto.encrypted_columns import secure_object_key_digest
from ..storage.runtime_repository import secure_object_repository_for_bucket
from ..storage.secure_object_namespaces import MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE
from .secure_enveloped_document import ProfileEnvelopedModelSecurePersistence

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ..storage.sql.secure_objects import SecureObjectRepository

_LOGGER = get_logger(__name__)


def _catalogue_phase(stage: str) -> None:
    """Record bounded catalogue stages without coordinates or stored values."""
    diagnostic_timing_event(_LOGGER, "calculation_catalogue_phase", fields={"stage": stage})


_CALCULATION_PERSISTENCE_MESSAGE = "errors.fail.fail_modelo_calculation_revision_persistence"

_OVERRIDE_FREE_PAYLOADS_RETAINED = 64


class _OverrideFreePayloadDigests:
    """Bounded process memory of plaintext digests whose catalogue carries no relation override.

    Each entry is a fact about exact bytes, so it holds whichever store, profile,
    writer or authority generation meets those bytes later, and a write that never
    commits leaves a true entry no row matches. It keeps only the digest the row
    already stores beside its ciphertext.
    """

    def __init__(self) -> None:
        self._digests: OrderedDict[str, None] = OrderedDict()
        self._lock = Lock()

    def remember(self, payload: bytes, catalogue: CalculationRevisionCatalogue) -> None:
        """Record ``payload`` when its decoded ``catalogue`` carries no override at all."""
        if any(revision.relation_overrides for revision in catalogue.values()):
            return
        digest = sha256_hex(payload)
        with self._lock:
            self._digests[digest] = None
            self._digests.move_to_end(digest)
            while len(self._digests) > _OVERRIDE_FREE_PAYLOADS_RETAINED:
                self._digests.popitem(last=False)

    def __contains__(self, digest: str) -> bool:
        with self._lock:
            return digest in self._digests


_OVERRIDE_FREE_PAYLOADS = _OverrideFreePayloadDigests()


@dataclass(frozen=True, slots=True, eq=False)
class _ValidationInputs:
    """Everything one catalogue validation reads, compared by identity or value.

    The pinned operation and the governed-fact scope are compared by identity,
    so a validation is never reused under another authority reader or
    governed-fact source; the parent authorities by value, as read for this
    call. The result is held by one repository, which composition builds for
    each operation's ports.
    """

    revision_id: str
    payload_digest: str
    operation: PinnedAuthorityOperation
    governed_facts: GovernedFactSource | None
    validated_on: date
    aggregate_context: CalculationRevisionAggregateContext

    def matches(self, other: _ValidationInputs) -> bool:
        """Report whether ``other`` would validate exactly as these inputs did."""
        return (
            self.revision_id == other.revision_id
            and self.payload_digest == other.payload_digest
            and self.operation is other.operation
            and self.governed_facts is other.governed_facts
            and self.validated_on == other.validated_on
            and self.aggregate_context == other.aggregate_context
        )


@dataclass(frozen=True, slots=True, eq=False)
class _ValidatedCatalogue:
    """The immutable catalogue one repository last validated, with the inputs it was validated from."""

    inputs: _ValidationInputs
    catalogue: CalculationRevisionCatalogue


class CalculationRevisionCatalogueRepository:
    """Repository over encrypted SQL-backed calculation-revision catalogue storage.

    :data:`~adapters.persistence.storage.secure_object_namespaces.MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE`
    is the central namespace, schema-version, sensitivity, and singleton-key
    contract for the encrypted :class:`CalculationRevisionCatalogue` row. The
    write path (``to_secure_object_write`` / ``save`` / ``exists``) composes
    :class:`~adapters.persistence.profile.secure_enveloped_document.ProfileEnvelopedModelSecurePersistence`
    for the shared Envelope-construction mechanic; both read doors share
    one decoder here because it translates a classification or schema-version mismatch
    into :class:`CalculationRevisionPersistenceError` via
    :func:`~domain.modelos.errors.raise_catalogue_integrity_error`, and runs the
    post-load ledger-evidence coverage gate
    (:func:`~domain.modelos.calculation_revision.assert_revision_snapshot_evidence_coverage`) the
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
        self._last_validated: _ValidatedCatalogue | None = None
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
        :class:`~adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`
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

    def load(self, *, operation: PinnedAuthorityOperation | None = None) -> CalculationRevisionCatalogue:
        """Load and decrypt the persisted calculation-revision catalogue.

        A calculation revision is a dated, computed version of a modelo's casilla
        values (a casilla is a numbered box on an AEAT form); the catalogue is the
        keyed collection of those revisions. The stored record is decrypted, its
        :class:`~adapters.persistence.storage.envelope.contract.Envelope` parsed, and its
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
        if operation is None:
            with bundled_indexed_authority().operation() as indexed_operation:
                return self.load(operation=indexed_operation)
        catalogue, _revision_id = self._load_revisioned(operation=operation)
        return catalogue

    def _load_revisioned(self, *, operation: PinnedAuthorityOperation) -> tuple[CalculationRevisionCatalogue, str]:
        """Validate one fresh record with one captured parent catalogue for either read door.

        The row is always read and its authorities always captured afresh. Only
        when every input of the validation is the one this repository last
        validated -- the same row revision and bytes, the same pinned operation
        and governed facts, the same day and equal parent authorities -- is that
        result returned instead of decoding the same bytes again.
        """
        from ..storage.errors import ClassificationError, EnvelopeVersionError

        _catalogue_phase("load_store_begin")
        try:
            record = self._objects.load(
                MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.namespace,
                MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.require_default_object_key(),
                expected_class=MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.sensitivity,
                max_supported_version=MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.schema_version,
            )
        except (ClassificationError, EnvelopeVersionError) as exc:
            raise_catalogue_integrity_error(
                exc,
                error_cls=CalculationRevisionPersistenceError,
                label="calculation-revision",
                translated_message=_CALCULATION_PERSISTENCE_MESSAGE,
                logger=_LOGGER,
            )
        _catalogue_phase("load_store_end")
        if record is None:
            return CalculationRevisionCatalogue(), ABSENT_SECURE_OBJECT_REVISION_ID
        _catalogue_phase("load_validation_begin")
        aggregate_context = self._calculation_revision_aggregate_context(operation=operation)
        inputs = _ValidationInputs(
            revision_id=record.revision_id,
            payload_digest=sha256_hex(record.payload),
            operation=operation,
            governed_facts=governed_facts_in_scope(),
            validated_on=today_madrid(),
            aggregate_context=aggregate_context,
        )
        held = self._last_validated
        if held is not None and held.inputs.matches(inputs):
            catalogue = held.catalogue
        else:
            catalogue = self._validated_catalogue(record.payload, aggregate_context=aggregate_context)
            self._last_validated = _ValidatedCatalogue(inputs=inputs, catalogue=catalogue)
        _catalogue_phase("load_validation_end")
        _OVERRIDE_FREE_PAYLOADS.remember(record.payload, catalogue)
        return catalogue, record.revision_id

    def _validated_catalogue(
        self,
        payload: bytes,
        *,
        aggregate_context: CalculationRevisionAggregateContext,
    ) -> CalculationRevisionCatalogue:
        """Decode and validate one stored payload against the authorities it was read with."""
        from ..storage.envelope.contract import Envelope
        from ..storage.schema_lineage import (
            inner_envelope_classification_is_expected,
            inner_envelope_version_is_current,
        )

        envelope: Envelope[CalculationRevisionCatalogue] | None = None
        validation_failed = False
        try:
            envelope = Envelope[CalculationRevisionCatalogue].model_validate_json(
                payload,
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
        if not inner_envelope_classification_is_expected(
            envelope.classification, MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.sensitivity
        ):
            _LOGGER.error(
                "calculation-revision catalogue classification mismatch",
                extra={
                    "expected_classification": MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.sensitivity.value,
                    "actual_classification": envelope.classification.value,
                },
            )
            raise CalculationRevisionPersistenceError(
                "calculation-revision catalogue classification mismatch",
                translated_message=_CALCULATION_PERSISTENCE_MESSAGE,
                context={
                    "reason": "classification_mismatch",
                    "expected_classification": MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.sensitivity.value,
                    "actual_classification": envelope.classification.value,
                },
            )
        if not inner_envelope_version_is_current(
            envelope.schema_version, MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.schema_version
        ):
            _LOGGER.error(
                "calculation-revision catalogue envelope version unsupported",
                extra={
                    "stored_schema_version": envelope.schema_version,
                    "max_supported_version": MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.schema_version,
                },
            )
            raise CalculationRevisionPersistenceError(
                "calculation-revision catalogue envelope version unsupported",
                translated_message=_CALCULATION_PERSISTENCE_MESSAGE,
                context={
                    "reason": "unsupported_envelope_version",
                    "stored_schema_version": envelope.schema_version,
                    "max_supported_version": MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE.schema_version,
                },
            )
        # Post-roundtrip coverage gate: every loaded revision's bundled
        # ledger evidence must cover the same contributor set as its
        # fingerprint snapshot. A row silently dropped after persistence
        # surfaces here on load rather than shipping an unexplainable casilla.
        for revision in envelope.payload.values():
            assert_revision_snapshot_evidence_coverage(revision)
        self._require_parent_coordinates(envelope.payload, work_units=aggregate_context.work_units)
        return envelope.payload

    def stored_catalogue_is_known_override_free(self) -> bool:
        """Report whether the stored row's bytes are already known to hold no relation override.

        Reads only the row's plaintext digest, under the same session freshness and
        bucket checks as every other read, and decrypts nothing. ``False`` means
        unknown, not that an override exists.
        """
        definition = MODELO_CALCULATION_REVISION_CATALOGUE_NAMESPACE
        digest = self._objects.namespace_payload_hashes(definition.namespace).get(
            secure_object_key_digest(definition.require_default_object_key()),
        )
        return digest is not None and digest in _OVERRIDE_FREE_PAYLOADS

    def _require_parent_coordinates(
        self,
        catalogue: CalculationRevisionCatalogue,
        *,
        work_units: WorkUnitCatalogue | None = None,
    ) -> None:
        """Refuse revisions whose stamps differ from their persisted parent WorkUnits."""
        if work_units is None:
            from .modelos_work_units import WorkUnitCatalogueRepository

            work_units = WorkUnitCatalogueRepository(objects=self._objects).load()
        for revision in catalogue.values():
            work_unit = work_units.get(revision.work_unit_id)
            if work_unit is None:
                raise CalculationRevisionPersistenceError(
                    "calculation revision has no persisted parent WorkUnit",
                    translated_message=_CALCULATION_PERSISTENCE_MESSAGE,
                    context={"reason": "missing_parent_work_unit", "work_unit_id": revision.work_unit_id},
                )
            expected = RegistrySnapshotRef(
                modelo=work_unit.modelo,
                revision_id=work_unit.revision_id,
                modelo_year=work_unit.filing_year,
                period=work_unit.period.registry_token,
            )
            if revision.registry_snapshot_ref != expected:
                raise CalculationRevisionPersistenceError(
                    "calculation revision registry coordinate disagrees with its parent WorkUnit",
                    translated_message=_CALCULATION_PERSISTENCE_MESSAGE,
                    context={"reason": "parent_registry_coordinate_mismatch", "work_unit_id": revision.work_unit_id},
                )

    def _calculation_revision_aggregate_context(
        self,
        *,
        operation: PinnedAuthorityOperation,
    ) -> CalculationRevisionAggregateContext:
        """Load every persisted authority needed to revalidate rectificativa revisions."""
        from .justificante import JustificanteRepository
        from .modelos_filing import ModeloRecordCatalogueRepository
        from .modelos_work_units import WorkUnitCatalogueRepository

        work_units = WorkUnitCatalogueRepository(objects=self._objects).load()
        filing_records = ModeloRecordCatalogueRepository(objects=self._objects).load()
        justificantes = tuple(JustificanteRepository(objects=self._objects).iter_justificantes())
        snapshots: dict[str, RegistrySnapshot] = {
            unit.work_unit_id: operation.snapshot(
                Modelo("303").value,
                filing_year=unit.filing_year,
                period=unit.period.registry_token,
            )
            for unit in work_units.values()
            if unit.modelo == form_for_role("iva.periodic")
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
        :class:`~adapters.persistence.storage.envelope.contract.Envelope` stamped with the
        current schema version, write time, and ``FINANCIAL`` sensitivity
        classification, then writes the serialised envelope to the encrypted
        store under this repository's namespace and key. An existing catalogue
        object at that location is overwritten.

        Args:
            catalogue: The :class:`CalculationRevisionCatalogue` to serialise and
                store.
        """
        self._require_parent_coordinates(catalogue)
        self._storage.save(catalogue)

    def load_revisioned(
        self,
        *,
        operation: PinnedAuthorityOperation | None = None,
    ) -> tuple[CalculationRevisionCatalogue, str]:
        """Return the catalogue and the revision id it was read at.

        The read a guarded co-commit needs. A calculate run composes this
        catalogue with the work-unit catalogue and the creation event in one
        unit of work, so it cannot use a self-committing mutation, and without
        the revision it would write back the whole catalogue and discard a
        revision another run added in between. A dropped calculation revision
        is a dropped tax computation.

        Raises:
            :class:`~CalculationRevisionPersistenceError`: If the stored
                payload fails the catalogue contract, exactly as :meth:`load`
                refuses it, so no raw validation detail reaches the caller.
        """
        if operation is None:
            with bundled_indexed_authority().operation() as indexed_operation:
                return self.load_revisioned(operation=indexed_operation)
        _catalogue_phase("revisioned_begin")
        loaded = self._load_revisioned(operation=operation)
        _catalogue_phase("revisioned_end")
        return loaded

    def to_secure_object_write(
        self,
        catalogue: CalculationRevisionCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Return the secure-object upsert for ``catalogue`` without committing it.

        The returned :class:`~core.secure_object_write.SecureObjectWrite`
        carries the same :class:`~adapters.persistence.storage.envelope.contract.Envelope`
        and :class:`~core.classification.policies.SensitivityClass`
        classification that :meth:`save` would persist directly. It can be
        co-emitted with related secure objects (e.g. the participation index) in
        one :meth:`save_with_secure_object_writes` unit of work.

        Pass ``expected_revision_id`` from :meth:`load_revisioned` whenever the
        catalogue was DERIVED from a read; omitting it writes the whole
        singleton row back unconditionally.
        """
        _catalogue_phase("encode_begin")
        self._require_parent_coordinates(catalogue)
        write = self._storage.to_secure_object_write(
            catalogue,
            expected_revision_id=expected_revision_id,
        )
        _OVERRIDE_FREE_PAYLOADS.remember(write.payload, catalogue)
        _catalogue_phase("encode_end")
        return write

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
                :class:`~core.secure_object_write.SecureObjectWrite`
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
