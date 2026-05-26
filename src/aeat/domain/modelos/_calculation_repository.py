"""Encrypted SQL repository for the calculation-revision catalogue."""

from __future__ import annotations

from datetime import UTC, datetime

from ...adapters.persistence.storage import Envelope, SensitivityClass
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core.logging import get_logger
from ._calculation_revision import CalculationRevision, CalculationRevisionCatalogue
from ._errors import ModeloError
from ._runtime_repository import resolve_modelo_repository_bucket_id, secure_objects_for_modelo_bucket

_LOGGER = get_logger(__name__)
_CALCULATION_NAMESPACE = "aeat.domain.modelos.calculation_revisions"
_CALCULATION_OBJECT_KEY = "catalogue"
_CALCULATION_CATALOGUE_VERSION = 1


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
        return self._bucket_id

    def exists(self) -> bool:
        return self._objects.exists(_CALCULATION_NAMESPACE, _CALCULATION_OBJECT_KEY)

    def load(self) -> CalculationRevisionCatalogue:
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
                f"calculation-revision catalogue integrity error: {type(exc).__name__}: {exc}"
            ) from exc
        if record is None:
            return CalculationRevisionCatalogue()
        envelope = Envelope[CalculationRevisionCatalogue].model_validate_json(record.payload.decode("utf-8"))
        if envelope.classification is not SensitivityClass.FINANCIAL:
            raise CalculationRevisionPersistenceError(
                f"calculation-revision catalogue has classification {envelope.classification}; FINANCIAL expected"
            )
        if envelope.schema_version > _CALCULATION_CATALOGUE_VERSION:
            raise CalculationRevisionPersistenceError(
                f"calculation-revision catalogue is at version {envelope.schema_version}; "
                f"consumer supports up to {_CALCULATION_CATALOGUE_VERSION}"
            )
        return envelope.payload

    def save(self, catalogue: CalculationRevisionCatalogue) -> None:
        envelope = Envelope[CalculationRevisionCatalogue](
            schema_version=_CALCULATION_CATALOGUE_VERSION,
            written_at=datetime.now(UTC),
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


def upsert_calculation_revision(
    catalogue: CalculationRevisionCatalogue, revision: CalculationRevision
) -> CalculationRevisionCatalogue:
    """Return a new catalogue with ``revision`` inserted or replaced."""
    mapping = dict(catalogue.revisions)
    mapping[revision.calculation_revision_id] = revision
    return CalculationRevisionCatalogue(revisions=mapping)


__all__ = [
    "CalculationRevisionCatalogueRepository",
    "CalculationRevisionPersistenceError",
    "upsert_calculation_revision",
]
