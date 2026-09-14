"""Application-owned capabilities required by Modelo filing actions.

The filing authority coordinates several profile catalogues and a workflow-run
audit sink.  It receives those capabilities through this required bundle so it
never selects an encrypted-storage adapter or derives one repository from
another repository's implementation details.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    TransactionParticipationIndexRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..calculations.observations_repository import (
    CalculationObservationRepositoryProtocol,
    IvaWalletDecisionRepositoryProtocol,
)
from ..calculations.iva_compensation_history_ports import IvaCompensationHistoryRepositoryProtocol
from ..filing.draft_review_ports import DraftReviewPorts
from .verification_repository_ports import WorkflowRunRepositoryProtocol

if TYPE_CHECKING:
    from .workflow_gate_ports import WorkflowGatePorts


@dataclass(frozen=True, slots=True)
class FilingActionPorts:
    """Required persisted authorities for one Modelo filing invocation."""

    work_unit_repository: WorkUnitCatalogueRepositoryProtocol
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol
    filing_repository: ModeloRecordCatalogueRepositoryProtocol
    verification_repository: VerificationReportCatalogueRepositoryProtocol
    observation_repository: CalculationObservationRepositoryProtocol
    participation_index_repository: TransactionParticipationIndexRepositoryProtocol
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol
    iva_compensation_history_repository: IvaCompensationHistoryRepositoryProtocol
    bucket_event_repository: BucketEventHistoryRepositoryProtocol
    iva_compensation_decision_repository: IvaWalletDecisionRepositoryProtocol
    workflow_run_repository: WorkflowRunRepositoryProtocol
    draft_review_ports: DraftReviewPorts
    workflow_gate_ports: WorkflowGatePorts


class FilingActionPortsFactory(Protocol):
    """Construct the filing authorities for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> FilingActionPorts:
        """Return the complete filing bundle for ``bucket_id``."""
        ...


__all__ = ["FilingActionPorts", "FilingActionPortsFactory"]
