"""Encrypted SQL repository for the filing-record catalogue.

Persists and loads :class:`ModeloRecord` entries via
:class:`SecureObjectRepository` at :class:`SensitivityClass` FINANCIAL
using an :class:`Envelope` wrapper. The catalogue is stored as a single
encrypted BLOB per profile bucket.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.logging import get_logger
from ...core.time import now
from ._errors import ModeloError
from ._filing_record import ModeloRecord, ModeloRecordCatalogue
from ._runtime_repository import resolve_modelo_repository_bucket_id, secure_objects_for_modelo_bucket

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ...adapters.persistence.storage import SecureObjectRepository, SecureObjectWrite

_LOGGER = get_logger(__name__)
# namespace string preserved across rename to avoid orphaning persisted envelopes
_FILING_NAMESPACE = "aeat.domain.modelos.filing_records"
_FILING_OBJECT_KEY = "catalogue"
_FILING_CATALOGUE_VERSION = 1
_FILING_PERSISTENCE_MESSAGE = "errors.fail.fail_modelo_filing_record_persistence"


class ModeloRecordPersistenceError(ModeloError):
    """Raised when the filing-record catalogue cannot be persisted or loaded."""


class ModeloRecordCatalogueRepository:
    """Read / write the filing-record catalogue in encrypted storage."""

    def __init__(self, *, bucket_id: str | None = None, objects: SecureObjectRepository | None = None) -> None:
        self._bucket_id = bucket_id.strip() if bucket_id is not None else None
        if objects is not None:
            self._objects = objects
            return
        self._bucket_id = resolve_modelo_repository_bucket_id(bucket_id, error_type=ModeloRecordPersistenceError)
        self._objects = secure_objects_for_modelo_bucket(self._bucket_id)

    @property
    def bucket_id(self) -> str | None:
        """Profile bucket this repository reads from and writes to.

        A bucket is the per-profile partition that isolates one taxpayer's
        encrypted records from another's. Returns the resolved bucket
        identifier, or ``None`` when the repository was constructed against
        an injected ``SecureObjectRepository`` and no bucket id was supplied.
        """
        return self._bucket_id

    def exists(self) -> bool:
        """Report whether a persisted filing-record catalogue exists.

        Returns ``True`` when an encrypted catalogue BLOB has already been
        written for this bucket, ``False`` otherwise. This is a presence
        check only; it neither decrypts nor validates the stored payload.
        Call ``load`` to retrieve and verify the catalogue contents.
        """
        return self._objects.exists(_FILING_NAMESPACE, _FILING_OBJECT_KEY)

    def load(self) -> ModeloRecordCatalogue:
        """Load and decrypt the filing-record catalogue from storage.

        A modelo is an AEAT tax form, and each filing record is the durable
        receipt that a calculation revision (a dated, immutable result for
        that form) was filed for a given form, year, and period. The whole
        catalogue is persisted as one encrypted FINANCIAL-class BLOB and
        returned as a ``ModeloRecordCatalogue``.

        Returns an empty catalogue when nothing has been persisted yet.

        Returns:
            The decrypted :class:`ModeloRecordCatalogue` for this bucket.

        Raises:
            ModeloRecordPersistenceError: If the stored envelope fails its
                sensitivity-class or schema-version integrity checks, or if
                its on-disk classification is not FINANCIAL, or if it was
                written at a schema version newer than this consumer
                supports.
        """
        from ...adapters.persistence.storage import Envelope, SensitivityClass
        from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError

        try:
            record = self._objects.load(
                _FILING_NAMESPACE,
                _FILING_OBJECT_KEY,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=_FILING_CATALOGUE_VERSION,
            )
        except (ClassificationError, EnvelopeVersionError) as exc:
            _LOGGER.error("filing-record catalogue integrity error", exc_info=True)
            raise ModeloRecordPersistenceError(
                "filing-record catalogue integrity error",
                translated_message=_FILING_PERSISTENCE_MESSAGE,
                context={
                    "reason": "secure_object_integrity",
                    "cause_type": type(exc).__name__,
                },
            ) from exc
        if record is None:
            return ModeloRecordCatalogue()
        envelope = Envelope[ModeloRecordCatalogue].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not SensitivityClass.FINANCIAL:
            _LOGGER.error(
                "filing-record catalogue classification mismatch",
                extra={
                    "expected_classification": SensitivityClass.FINANCIAL.value,
                    "actual_classification": envelope.classification.value,
                },
            )
            raise ModeloRecordPersistenceError(
                "filing-record catalogue classification mismatch",
                translated_message=_FILING_PERSISTENCE_MESSAGE,
                context={
                    "reason": "classification_mismatch",
                    "expected_classification": SensitivityClass.FINANCIAL.value,
                    "actual_classification": envelope.classification.value,
                },
            )
        if envelope.schema_version > _FILING_CATALOGUE_VERSION:
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
        return envelope.payload

    def save(self, catalogue: ModeloRecordCatalogue) -> None:
        """Persist the filing-record catalogue as a single encrypted BLOB.

        Wraps ``catalogue`` in a FINANCIAL-class envelope stamped with the
        current schema version and write timestamp, then writes it through
        the secure object store. The entire catalogue is rewritten as one
        encrypted object per bucket, replacing any prior catalogue for this
        bucket.

        Args:
            catalogue: The ``ModeloRecordCatalogue`` to encrypt and store.
        """
        self._objects.save_many((self.to_secure_object_write(catalogue),))

    def to_secure_object_write(self, catalogue: ModeloRecordCatalogue) -> SecureObjectWrite:
        """Return the :class:`SecureObjectWrite` upsert for ``catalogue`` without committing it."""
        from ...adapters.persistence.storage import Envelope, SecureObjectWrite, SensitivityClass

        envelope = Envelope[ModeloRecordCatalogue](
            schema_version=_FILING_CATALOGUE_VERSION,
            written_at=now(),
            classification=SensitivityClass.FINANCIAL,
            payload=catalogue,
        )
        return SecureObjectWrite(
            namespace=_FILING_NAMESPACE,
            object_key=_FILING_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_FILING_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

    def save_with_secure_object_writes(
        self,
        catalogue: ModeloRecordCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Persist ``catalogue`` plus related secure objects in one unit of work."""
        self._objects.save_many((self.to_secure_object_write(catalogue), *extra_writes))


def upsert_filing_record(catalogue: ModeloRecordCatalogue, record: ModeloRecord) -> ModeloRecordCatalogue:
    """Return a new :class:`ModeloRecordCatalogue` with ``record`` inserted or replaced.

    Args:
        catalogue: Source catalogue to update.
        record: The :class:`ModeloRecord` to insert or replace.
    """
    mapping = dict(catalogue.records)
    mapping[record.filing_record_id] = record
    return ModeloRecordCatalogue(records=mapping)


__all__ = [
    "ModeloRecordCatalogueRepository",
    "ModeloRecordPersistenceError",
    "upsert_filing_record",
]
