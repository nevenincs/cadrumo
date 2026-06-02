"""Encrypted SQL repository for the filing-record catalogue.

Persists and loads :class:`ModeloRecord` entries via
:class:`SecureObjectRepository` at :class:`SensitivityClass` FINANCIAL
using an :class:`Envelope` wrapper. The catalogue is stored as a single
encrypted BLOB per profile bucket.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.time import now

from ...core.logging import get_logger
from ._errors import ModeloError
from ._filing_record import ModeloRecord, ModeloRecordCatalogue
from ._runtime_repository import resolve_modelo_repository_bucket_id, secure_objects_for_modelo_bucket

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ...adapters.persistence.storage.sql import SecureObjectRepository

_LOGGER = get_logger(__name__)
# namespace string preserved across rename to avoid orphaning persisted envelopes
_FILING_NAMESPACE = "aeat.domain.modelos.filing_records"
_FILING_OBJECT_KEY = "catalogue"
_FILING_CATALOGUE_VERSION = 1


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
        return self._bucket_id

    def exists(self) -> bool:
        return self._objects.exists(_FILING_NAMESPACE, _FILING_OBJECT_KEY)

    def load(self) -> ModeloRecordCatalogue:
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
                f"filing-record catalogue integrity error: {type(exc).__name__}: {exc}"
            ) from exc
        if record is None:
            return ModeloRecordCatalogue()
        envelope = Envelope[ModeloRecordCatalogue].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not SensitivityClass.FINANCIAL:
            raise ModeloRecordPersistenceError(
                f"filing-record catalogue has classification {envelope.classification}; FINANCIAL expected"
            )
        if envelope.schema_version > _FILING_CATALOGUE_VERSION:
            raise ModeloRecordPersistenceError(
                f"filing-record catalogue is at version {envelope.schema_version}; "
                f"consumer supports up to {_FILING_CATALOGUE_VERSION}"
            )
        return envelope.payload

    def save(self, catalogue: ModeloRecordCatalogue) -> None:
        from ...adapters.persistence.storage import Envelope, SensitivityClass

        envelope = Envelope[ModeloRecordCatalogue](
            schema_version=_FILING_CATALOGUE_VERSION,
            written_at=now(),
            classification=SensitivityClass.FINANCIAL,
            payload=catalogue,
        )
        self._objects.save(
            namespace=_FILING_NAMESPACE,
            object_key=_FILING_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_FILING_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )


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
