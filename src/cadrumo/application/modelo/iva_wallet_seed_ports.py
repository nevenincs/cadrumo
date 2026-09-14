"""Application-owned capabilities required by IVA-wallet seed operations.

The Modelo facade owns seed, correction, and override policy.  It receives
bucket-bound repository capabilities from an outer composition root and keeps
the storage implementations, DTO translation, and persistence errors outside
the application boundary.  Observation reads and wallet-decision writes use
the shared :class:`CalculationObservationPorts` bundle rather than defining a
second pair of protocols for the same capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..calculations.observations_repository import CalculationObservationPorts
from ..calculations.iva_compensation_history_ports import IvaCompensationHistoryRepositoryProtocol


@dataclass(frozen=True, slots=True)
class ModeloIvaWalletSeedPorts:
    """Required persisted authorities for one IVA-wallet seed operation."""

    work_unit_repository: WorkUnitCatalogueRepositoryProtocol
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol
    bucket_event_repository: BucketEventHistoryRepositoryProtocol
    calculation_observation_ports: CalculationObservationPorts
    iva_compensation_history_repository: IvaCompensationHistoryRepositoryProtocol


class ModeloIvaWalletSeedPortsFactory(Protocol):
    """Construct the IVA-wallet seed authorities for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> ModeloIvaWalletSeedPorts:
        """Return the complete IVA-wallet seed bundle for ``bucket_id``."""
        ...


__all__ = ["ModeloIvaWalletSeedPorts", "ModeloIvaWalletSeedPortsFactory"]
