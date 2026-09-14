"""Persistence adapter for the Modelo taxation-comparison read capability."""

from __future__ import annotations

from ....application.modelo.taxation_comparison_ports import (
    TaxationComparisonPersistenceError,
    TaxationComparisonPorts,
    TaxationComparisonWorkUnitReader,
)
from ....domain.modelos.repository import WorkUnitPersistenceError
from ....domain.modelos.work_unit import WorkUnitCatalogue
from ..storage.errors import StorageError
from ..storage.runtime_repository import secure_object_repository_for_bucket
from .modelos_work_units import WorkUnitCatalogueRepository


class TaxationComparisonWorkUnitReaderAdapter(TaxationComparisonWorkUnitReader):
    """Translate the encrypted work-unit repository to the application port."""

    def __init__(self, *, repository: WorkUnitCatalogueRepository) -> None:
        """Bind an already-composed work-unit repository."""
        self._repository = repository

    def load(self) -> WorkUnitCatalogue:
        """Load work units while hiding persistence implementation errors."""
        try:
            return self._repository.load()
        except (WorkUnitPersistenceError, StorageError, OSError) as exc:
            raise TaxationComparisonPersistenceError("work_unit_catalogue_load") from exc


def build_taxation_comparison_ports(*, bucket_id: str) -> TaxationComparisonPorts:
    """Bind the work-unit repository to one profile bucket."""
    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    return TaxationComparisonPorts(
        work_unit_reader=TaxationComparisonWorkUnitReaderAdapter(
            repository=WorkUnitCatalogueRepository(bucket_id=normalized_bucket_id, objects=objects),
        ),
    )


__all__ = [
    "TaxationComparisonWorkUnitReaderAdapter",
    "build_taxation_comparison_ports",
]
