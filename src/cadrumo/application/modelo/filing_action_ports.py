"""Application-owned capabilities required by Modelo filing actions.

The filing authority coordinates several profile catalogues and a workflow-run
audit sink.  It receives those capabilities through this required bundle so it
never selects an encrypted-storage adapter or derives one repository from
another repository's implementation details.
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
from ..calculations.observations_repository import (
    CalculationObservationRepositoryProtocol,
    IvaWalletDecisionRepositoryProtocol,
)
from .verification_repository_ports import WorkflowRunRepositoryProtocol


@dataclass(frozen=True, slots=True)
class FilingActionPorts:
    """Required persisted authorities for one Modelo filing invocation."""

    work_unit_repository: WorkUnitCatalogueRepositoryProtocol
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol
    filing_repository: ModeloRecordCatalogueRepositoryProtocol
    verification_repository: VerificationReportCatalogueRepositoryProtocol
    observation_repository: CalculationObservationRepositoryProtocol
    bucket_event_repository: BucketEventHistoryRepositoryProtocol
    iva_compensation_decision_repository: IvaWalletDecisionRepositoryProtocol
    workflow_run_repository: WorkflowRunRepositoryProtocol


class FilingActionPortsFactory(Protocol):
    """Construct the filing authorities for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> FilingActionPorts:
        """Return the complete filing bundle for ``bucket_id``."""
        ...


__all__ = ["FilingActionPorts", "FilingActionPortsFactory"]
