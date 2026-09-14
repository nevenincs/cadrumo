"""Encrypted persistence bindings for application evidence-bundle ports."""

from __future__ import annotations

from collections.abc import Iterator
from typing import ClassVar, override

from ....application.evidence.models import EvidenceBundle
from ....application.evidence.ports import (
    EvidenceBundlePersistenceError,
    EvidenceBundleRepositoryPort,
    EvidenceBundleWorkUnitPort,
)
from ....domain.modelos.repository import WorkUnitPersistenceError
from ..storage.envelope.secure_bound_repository import SecureBoundRepository
from ..storage.errors import StorageError
from ..storage.secure_object_namespaces import APPLICATION_EVIDENCE_BUNDLE_NAMESPACE
from ..storage.sql.secure_objects import SecureObjectRepository
from .modelos_work_units import WorkUnitCatalogueRepository


class EvidenceBundleRepository(SecureBoundRepository[EvidenceBundle], EvidenceBundleRepositoryPort):
    """Bind encrypted secure-object storage to the evidence-bundle port."""

    namespace: ClassVar[str] = APPLICATION_EVIDENCE_BUNDLE_NAMESPACE.namespace
    sensitivity: ClassVar = APPLICATION_EVIDENCE_BUNDLE_NAMESPACE.sensitivity
    schema_version: ClassVar[int] = APPLICATION_EVIDENCE_BUNDLE_NAMESPACE.schema_version
    payload_type: ClassVar[type[EvidenceBundle]] = EvidenceBundle

    def __init__(self, *, objects: SecureObjectRepository) -> None:
        """Bind an already-composed secure-object store."""
        super().__init__(objects=objects)

    @override
    def extract_identifier(self, payload: EvidenceBundle) -> str:
        """Return the stable storage key for an evidence bundle."""
        return payload.bundle_id

    @staticmethod
    def _translate(operation: str, _error: StorageError) -> EvidenceBundlePersistenceError:
        """Translate storage-specific failures before they cross the port."""
        return EvidenceBundlePersistenceError(operation)

    def load(self, identifier: str) -> EvidenceBundle | None:
        """Load one encrypted bundle and translate storage failures."""
        try:
            return super().load(identifier)
        except StorageError as error:
            raise self._translate("load", error) from error

    def save(self, payload: EvidenceBundle) -> None:
        """Save one encrypted bundle and translate storage failures."""
        try:
            super().save(payload)
        except StorageError as error:
            raise self._translate("save", error) from error

    def iter_records(self) -> Iterator[EvidenceBundle]:
        """Iterate encrypted bundles and translate scan failures."""
        try:
            yield from super().iter_records()
        except StorageError as error:
            raise self._translate("iter_records", error) from error


class EvidenceBundleWorkUnitRepository(EvidenceBundleWorkUnitPort):
    """Adapt the encrypted work-unit catalogue to the evidence port."""

    def __init__(self, *, bucket_id: str, objects: SecureObjectRepository) -> None:
        """Bind the work-unit lookup to the same bucket-scoped store."""
        self._repository = WorkUnitCatalogueRepository(bucket_id=bucket_id, objects=objects)

    def exists(self, work_unit_id: str) -> bool:
        """Return whether the bucket's catalogue contains ``work_unit_id``."""
        try:
            return self._repository.load().get(work_unit_id) is not None
        except (StorageError, WorkUnitPersistenceError) as error:
            raise EvidenceBundlePersistenceError("work_unit_exists") from error


__all__ = ["EvidenceBundleRepository", "EvidenceBundleWorkUnitRepository"]
