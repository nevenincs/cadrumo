"""Encrypted SQL repository for the modelo filing-record catalogue.

:class:`ModeloRecordCatalogueRepository` persists and loads
:class:`ModeloRecord` entries in a :class:`ModeloRecordCatalogue` via
:class:`~adapters.persistence.storage.SecureObjectRepository` at
``FINANCIAL`` :class:`~adapters.persistence.storage.SensitivityClass`
using an :class:`~adapters.persistence.storage.Envelope` wrapper. The
catalogue is stored as a single encrypted BLOB per profile bucket.

This concrete repository is the persistence adapter behind the read-side
:class:`~domain.modelos.ModeloRecordCatalogueRepositoryProtocol`. It lives
in the persistence adapter (not in :mod:`~domain.modelos`) because its
secure-object coupling is SQL/crypto-bound; the domain package owns only the
typed :class:`ModeloRecordCatalogue` model and its pure mutators.

See Also:
    :mod:`~adapters.persistence.profile._modelo_runtime`
        Bucket-id resolution and runtime secure-object factory shared by modelo
        persistence adapters.
    :class:`~domain.modelos.ModeloRecordCatalogue`
        Domain catalogue payload encrypted by this repository.
    :class:`~domain.modelos.ModeloRecordCatalogueRepositoryProtocol`
        Domain port this concrete persistence adapter implements.
    :data:`~adapters.persistence.storage.MODELO_FILING_RECORD_CATALOGUE_NAMESPACE`
        Central namespace, sensitivity, schema-version, and singleton-key
        contract for these secure objects.
    :mod:`~adapters.persistence.profile.modelos_work_units`
        Sibling work-unit catalogue repository whose current/filed pointers
        reference filing records stored here.
    :func:`~application.modelo.file_modelo_revision`
        Application service that writes local/internal filing state through the
        modelo catalogue repositories.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....core.bucket_pointer import resolve_repository_bucket_id
from ....core.external_constants import UTF_8_ENCODING
from ....core.logging import get_logger
from ....domain.modelos import (
    ModeloRecordCatalogue,
    ModeloRecordPersistenceError,
    raise_catalogue_integrity_error,
)
from ..storage import MODELO_FILING_RECORD_CATALOGUE_NAMESPACE, secure_object_repository_for_bucket
from ._secure_enveloped_document import ProfileEnvelopedModelSecurePersistence

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from collections.abc import Callable

    from ..storage import SecureObjectRepository, SecureObjectWrite

_LOGGER = get_logger(__name__)
_FILING_NAMESPACE = MODELO_FILING_RECORD_CATALOGUE_NAMESPACE.namespace
_FILING_OBJECT_KEY = MODELO_FILING_RECORD_CATALOGUE_NAMESPACE.require_default_object_key()
_FILING_CATALOGUE_VERSION = MODELO_FILING_RECORD_CATALOGUE_NAMESPACE.schema_version
_FILING_CATALOGUE_SENSITIVITY = MODELO_FILING_RECORD_CATALOGUE_NAMESPACE.sensitivity
_FILING_PERSISTENCE_MESSAGE = "errors.fail.fail_modelo_filing_record_persistence"


class ModeloRecordCatalogueRepository:
    """Repository over encrypted SQL-backed filing-record catalogue storage.

    :data:`~adapters.persistence.storage.MODELO_FILING_RECORD_CATALOGUE_NAMESPACE`
    is the central namespace, schema-version, sensitivity, and singleton-key
    contract for the encrypted :class:`ModeloRecordCatalogue` row. The
    catalogue payload keeps member-scoped current/history lookups in the domain
    type. The write path (``to_secure_object_write`` / ``save`` / ``exists``)
    composes
    :class:`~adapters.persistence.profile._secure_enveloped_document.ProfileEnvelopedModelSecurePersistence`
    for the shared Envelope-construction mechanic; ``load`` stays hand-rolled
    here because this repository translates a classification or
    schema-version mismatch into :class:`ModeloRecordPersistenceError` via
    :func:`~domain.modelos.raise_catalogue_integrity_error`, a translation the
    shared kernel does not perform. This class exposes the concrete load/save
    implementation behind
    :class:`~domain.modelos.ModeloRecordCatalogueRepositoryProtocol`.
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
            self._bucket_id = resolve_repository_bucket_id(bucket_id, error_type=ModeloRecordPersistenceError)
            self._objects = secure_object_repository_for_bucket(self._bucket_id)
        self._storage = ProfileEnvelopedModelSecurePersistence(
            objects=self._objects,
            definition=MODELO_FILING_RECORD_CATALOGUE_NAMESPACE,
            model_type=ModeloRecordCatalogue,
            empty_document=ModeloRecordCatalogue,
        )

    @property
    def bucket_id(self) -> str | None:
        """Profile bucket this repository reads from and writes to.

        A bucket is the per-profile partition that isolates one taxpayer's
        encrypted records from another's. Returns the resolved bucket
        identifier, or ``None`` when the repository was constructed against
        an injected
        :class:`~adapters.persistence.storage.SecureObjectRepository`
        and no bucket id was supplied.
        """
        return self._bucket_id

    def exists(self) -> bool:
        """Report whether a persisted filing-record catalogue exists.

        Returns ``True`` when an encrypted catalogue BLOB has already been
        written for this bucket, ``False`` otherwise. This is a presence
        check only; it neither decrypts nor validates the stored payload.
        Call ``load`` to retrieve and verify the catalogue contents.
        """
        return self._storage.exists()

    def _assert_records_belong_to_this_bucket(
        self,
        catalogue: ModeloRecordCatalogue,
        *,
        boundary: str,
    ) -> None:
        """Refuse filing records that do not belong to the bucket this repository serves.

        Every :class:`ModeloRecord` names its owning bucket, and the whole
        catalogue is one encrypted object per bucket, but nothing compared the
        two. A foreign receipt written into bucket A was therefore returned by
        A's ``current``/``history``/``list`` consumers as a local filing.

        When the repository was constructed against an injected secure-object
        store with no bucket id, there is no binding to compare against; the
        records are then required to agree on one bucket among themselves, so a
        catalogue mixing two taxpayers is still refused.

        Args:
            catalogue: The catalogue being written or read back.
            boundary: ``"save"`` or ``"load"``, recorded on the refusal context.

        Raises:
            :class:`ModeloRecordPersistenceError`: When a record names a bucket
                other than this repository's.
        """
        record_buckets = {record.bucket_id for record in catalogue.values()}
        if not record_buckets:
            return
        expected = self._bucket_id
        if expected is None:
            if len(record_buckets) == 1:
                return
            foreign = sorted(record_buckets)
        else:
            foreign = sorted(bucket for bucket in record_buckets if bucket != expected)
            if not foreign:
                return
        _LOGGER.error(
            "filing-record catalogue carries records from another bucket",
            extra={"boundary": boundary, "foreign_bucket_count": len(foreign)},
        )
        raise ModeloRecordPersistenceError(
            "filing-record catalogue carries records from another bucket",
            translated_message=_FILING_PERSISTENCE_MESSAGE,
            context={
                "reason": "foreign_bucket_record",
                "boundary": boundary,
                "expected_bucket_id": expected,
                "record_bucket_ids": foreign,
            },
        )

    def load(self) -> ModeloRecordCatalogue:
        """Load and decrypt the filing-record catalogue from storage.

        A modelo is an AEAT tax form, and each filing record is the durable
        receipt that a calculation revision (a dated, immutable result for
        that form) was filed for a given form, year, and period. The whole
        catalogue is persisted as one encrypted FINANCIAL-class BLOB and
        returned as a :class:`ModeloRecordCatalogue`.

        Returns an empty catalogue when nothing has been persisted yet.

        Returns:
            The decrypted :class:`ModeloRecordCatalogue` for this bucket.

        Raises:
            :class:`ModeloRecordPersistenceError`: If the stored envelope fails
                its sensitivity-class or schema-version integrity checks, or if
                its on-disk classification is not FINANCIAL, or if it was
                written at a schema version newer than this consumer supports.
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
                _FILING_NAMESPACE,
                _FILING_OBJECT_KEY,
                expected_class=_FILING_CATALOGUE_SENSITIVITY,
                max_supported_version=_FILING_CATALOGUE_VERSION,
            )
        except (ClassificationError, EnvelopeVersionError) as exc:
            raise_catalogue_integrity_error(
                exc,
                error_cls=ModeloRecordPersistenceError,
                label="filing-record",
                translated_message=_FILING_PERSISTENCE_MESSAGE,
                logger=_LOGGER,
            )
        if record is None:
            return ModeloRecordCatalogue()
        envelope = Envelope[ModeloRecordCatalogue].model_validate_json(record.payload.decode(UTF_8_ENCODING))
        if not inner_envelope_classification_is_expected(envelope.classification, _FILING_CATALOGUE_SENSITIVITY):
            _LOGGER.error(
                "filing-record catalogue classification mismatch",
                extra={
                    "expected_classification": _FILING_CATALOGUE_SENSITIVITY.value,
                    "actual_classification": envelope.classification.value,
                },
            )
            raise ModeloRecordPersistenceError(
                "filing-record catalogue classification mismatch",
                translated_message=_FILING_PERSISTENCE_MESSAGE,
                context={
                    "reason": "classification_mismatch",
                    "expected_classification": _FILING_CATALOGUE_SENSITIVITY.value,
                    "actual_classification": envelope.classification.value,
                },
            )
        if not inner_envelope_version_is_current(envelope.schema_version, _FILING_CATALOGUE_VERSION):
            _LOGGER.error(
                "filing-record catalogue envelope version unsupported",
                extra={
                    "stored_schema_version": envelope.schema_version,
                    "max_supported_version": _FILING_CATALOGUE_VERSION,
                },
            )
            raise ModeloRecordPersistenceError(
                "filing-record catalogue envelope version unsupported",
                translated_message=_FILING_PERSISTENCE_MESSAGE,
                context={
                    "reason": "unsupported_envelope_version",
                    "stored_schema_version": envelope.schema_version,
                    "max_supported_version": _FILING_CATALOGUE_VERSION,
                },
            )
        self._assert_records_belong_to_this_bucket(envelope.payload, boundary="load")
        return envelope.payload

    def save(self, catalogue: ModeloRecordCatalogue) -> None:
        """Persist the filing-record catalogue as a single encrypted BLOB.

        Wraps ``catalogue`` in a ``FINANCIAL``-class
        :class:`~adapters.persistence.storage.Envelope` stamped with the
        current schema version and write timestamp, then writes it through the
        secure object store. The entire catalogue is rewritten as one encrypted
        object per bucket, replacing any prior catalogue for this bucket.

        Args:
            catalogue: The :class:`ModeloRecordCatalogue` to encrypt and store.
        """
        self._objects.save_many((self.to_secure_object_write(catalogue),))

    def mutate(self, mutation: Callable[[ModeloRecordCatalogue], ModeloRecordCatalogue]) -> ModeloRecordCatalogue:
        """Apply ``mutation`` to the stored catalogue as one revision-guarded unit of work.

        The catalogue is a SINGLETON row, so stamping one filing record rewrites
        every other. Performed unguarded, a record another caller wrote in the
        interim is discarded, and nothing reports it: the survivors are each
        intact and the missing one leaves no hole.

        The bucket-ownership check runs on the mutation's OWN result rather than
        once beforehand, so a mutation introducing a foreign record is refused on
        every attempt rather than only the first.

        ``mutation`` is re-applied to the newly-current catalogue on a conflict,
        so it MUST be a pure function of what it is handed.
        """

        def _guarded(current: ModeloRecordCatalogue) -> ModeloRecordCatalogue:
            updated = mutation(current)
            self._assert_records_belong_to_this_bucket(updated, boundary="save")
            return updated

        return self._storage.mutate(_guarded)

    def load_revisioned(self) -> tuple[ModeloRecordCatalogue, str]:
        """Return the filing catalogue and the revision id it was read at.

        The read a guarded co-commit needs: a caller composing this catalogue
        into a batch cannot use the self-committing :meth:`mutate`, and without
        the revision its write puts the whole singleton row back over any
        filing record another writer added in between.
        """
        return self._storage.load_revisioned()

    def to_secure_object_write(
        self,
        catalogue: ModeloRecordCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Return the secure-object upsert for ``catalogue`` without committing it.

        The returned :class:`~adapters.persistence.storage.SecureObjectWrite`
        carries the same :class:`~adapters.persistence.storage.Envelope`
        and :class:`~adapters.persistence.storage.SensitivityClass`
        classification that :meth:`save` would persist directly.

        Pass ``expected_revision_id`` from :meth:`load_revisioned` whenever the
        catalogue was DERIVED from a read; omitting it rewrites the row
        unconditionally.
        """
        self._assert_records_belong_to_this_bucket(catalogue, boundary="save")
        return self._storage.to_secure_object_write(catalogue, expected_revision_id=expected_revision_id)

    def save_with_secure_object_writes(
        self,
        catalogue: ModeloRecordCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
        *,
        expected_revision_id: str | None = None,
    ) -> None:
        """Persist ``catalogue`` plus related secure objects in one unit of work.

        Args:
            catalogue: The :class:`ModeloRecordCatalogue` to persist.
            extra_writes: Additional
                :class:`~adapters.persistence.storage.SecureObjectWrite`
                objects to commit atomically with the catalogue.
            expected_revision_id: The revision :meth:`load_revisioned` reported
                for the catalogue this one was derived from. Atomicity is what
                this method already gave; the revision is what stops the batch
                discarding a filing record another writer committed between the
                read and this call.
        """
        self._objects.save_many(
            (self.to_secure_object_write(catalogue, expected_revision_id=expected_revision_id), *extra_writes),
        )


__all__ = [
    "ModeloRecordCatalogueRepository",
]
