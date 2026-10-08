"""Exact-profile catalogue and withholding capabilities for modelo aggregation.

Core types: :class:`~cadrumo.domain.transactions.models.TransactionCatalogue`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...domain.transactions.models import TransactionCatalogue
from ..aggregation.percepciones_observations_repository import (
    PercepcionObservationRepository,
)
from ..aggregation.retencion_observations_repository import (
    RetencionObservationRepository,
)
from ..aggregation.withholding_observation_service import (
    WithholdingObservationService,
)


class TransactionCatalogueReadPort(Protocol):
    """Profile-bound transaction catalogue view needed for payment capture."""

    @property
    def bucket_id(self) -> str:
        """Return the immutable profile binding of this reader."""
        ...

    def load_revision(self) -> str | None:
        """Return the exact revision of the full transaction catalogue."""
        ...

    def load_by_ids(self, transaction_ids: tuple[str, ...]) -> TransactionCatalogue:
        """Read the addressed transaction rows from this profile's catalogue."""
        ...


@dataclass(frozen=True, slots=True)
class ModeloAggregateOperationPorts:
    """Canonical profile-scoped readers and producer service for one request."""

    profile_id: str
    transaction_catalogue_repository: TransactionCatalogueReadPort
    retencion_observation_repository: RetencionObservationRepository
    percepcion_observation_repository: PercepcionObservationRepository
    withholding_observation_service: WithholdingObservationService


class ModeloAggregateOperationPortsFactory(Protocol):
    """Build every aggregate capability already bound to the requested profile."""

    def __call__(self, *, profile_id: str) -> ModeloAggregateOperationPorts:
        """Return the exact profile's aggregate read and capture capabilities."""
        ...
