"""Application-owned capabilities required by Modelo amendment actions.

The amendment authority reads and co-commits several profile catalogues.  It
depends on these domain-facing protocols rather than on encrypted-storage
implementations; executable composition roots bind the concrete repositories
for the active profile bucket and pass the complete bundle through the call
chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.justificante.protocols import JustificanteRepositoryProtocol
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..calculations.iva_compensation_history_ports import IvaCompensationHistoryRepositoryProtocol
from ..calculations.observations_repository import CalculationObservationRepositoryProtocol


@dataclass(frozen=True, slots=True)
class AmendmentActionPorts:
    """Required persisted authorities for one amendment invocation."""

    work_unit_repository: WorkUnitCatalogueRepositoryProtocol
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol
    filing_repository: ModeloRecordCatalogueRepositoryProtocol
    justificante_repository: JustificanteRepositoryProtocol
    bucket_event_repository: BucketEventHistoryRepositoryProtocol
    transaction_repository: TransactionCatalogueRepositoryProtocol
    observation_repository: CalculationObservationRepositoryProtocol
    iva_compensation_history_repository: IvaCompensationHistoryRepositoryProtocol


class AmendmentActionPortsFactory(Protocol):
    """Construct the amendment authorities for one profile bucket."""

    def __call__(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> AmendmentActionPorts:
        """Return the complete amendment bundle for ``bucket_id``."""
        ...


__all__ = ["AmendmentActionPorts", "AmendmentActionPortsFactory"]
