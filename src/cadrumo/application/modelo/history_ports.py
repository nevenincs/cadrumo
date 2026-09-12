"""Application-owned capabilities required by Modelo history projections.

History reads several profile catalogues that share one bucket-scoped secure
store.  The application service owns the projection and its DTOs, while this
bundle owns only the repository capabilities it needs.  An outer composition
root supplies the concrete implementations for one bucket; history never
constructs a persistence adapter or exposes storage DTOs and errors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol


@dataclass(frozen=True, slots=True)
class ModeloHistoryPorts:
    """Required persisted authorities for one Modelo history invocation."""

    work_unit_repository: WorkUnitCatalogueRepositoryProtocol
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol
    filing_repository: ModeloRecordCatalogueRepositoryProtocol
    verification_repository: VerificationReportCatalogueRepositoryProtocol
    bucket_event_repository: BucketEventHistoryRepositoryProtocol


class ModeloHistoryPortsFactory(Protocol):
    """Construct the history authorities for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> ModeloHistoryPorts:
        """Return the complete history bundle for ``bucket_id``."""
        ...


__all__ = ["ModeloHistoryPorts", "ModeloHistoryPortsFactory"]
