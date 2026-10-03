"""Application-owned capabilities for rebuilding the participation index.

The rebuild service reads the persisted modelo authorities and replaces a
derived transaction index.  This bundle is the application boundary for that
operation: composition roots supply bucket-bound repository implementations,
while the service remains independent of secure-object storage and adapter
types.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel

from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.participation_index import TransactionRevisionParticipationIndex
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol


class ParticipationRebuildSourceRevisions(BaseModel):
    """Opened authority revisions that must still hold when replacing the cache."""

    model_config = STRICT_FROZEN_CONFIG

    calculation: ContentDigest
    work_units: ContentDigest
    filings: ContentDigest


class ParticipationIndexRebuildRepositoryProtocol(Protocol):
    """Required replacement operation for the derived participation index."""

    @property
    def bucket_id(self) -> str | None:
        """Expose the exact persisted target, refusing unbound stores at worker admission."""
        ...

    def replace_all(
        self,
        indexes: Iterable[TransactionRevisionParticipationIndex],
        *,
        source_revisions: ParticipationRebuildSourceRevisions,
    ) -> int:
        """Replace the persisted index and return the number of stale rows removed."""
        ...


@dataclass(frozen=True, slots=True)
class ParticipationIndexRebuildPorts:
    """Required persisted authorities for one participation-index rebuild."""

    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol
    filing_repository: ModeloRecordCatalogueRepositoryProtocol
    participation_index_repository: ParticipationIndexRebuildRepositoryProtocol


class ParticipationIndexRebuildPortsFactory(Protocol):
    """Construct the complete participation-index rebuild bundle for a bucket."""

    def __call__(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> ParticipationIndexRebuildPorts:
        """Return all authorities for one bucket and its held authority operation."""
        ...


__all__ = [
    "ParticipationIndexRebuildPorts",
    "ParticipationIndexRebuildPortsFactory",
    "ParticipationIndexRebuildRepositoryProtocol",
    "ParticipationRebuildSourceRevisions",
]
