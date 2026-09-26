"""Application-owned repository ports for modelo verification.

Verification is an application use case: it coordinates several persistence
capabilities, but it must not know which encrypted-storage adapters implement
them.  This module keeps that capability boundary in the application layer.
The outer composition root supplies the concrete implementations as one
coherent bundle for each profile bucket.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.justificante.protocols import JustificanteRepositoryProtocol
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    TransactionParticipationIndexRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..aggregation.retencion_observations_repository import RetencionObservationPorts
from ..calculations.iva_compensation_history_ports import IvaCompensationHistoryRepositoryProtocol
from ..calculations.observations_repository import (
    CalculationObservationRepositoryProtocol,
    IvaWalletDecisionRepositoryProtocol,
)
from ..filing.draft_review_ports import DraftReviewPorts
from ..workflow.run_models import WorkflowResult

if TYPE_CHECKING:
    from .workflow_gate_ports import WorkflowGatePorts


@runtime_checkable
class WorkflowRunRepositoryProtocol(Protocol):
    """Write-side contract for verification workflow-run audit records."""

    def save(self, result: WorkflowResult, *, runs_dir: Path | None = None) -> Path:
        """Persist one workflow result and return its marker path."""
        ...


@dataclass(frozen=True, slots=True)
class VerificationRepositoryBundle:
    """All persistence capabilities required by one modelo verification run.

    Every field is required.  The bundle is assembled by an outer composition
    root against one profile bucket and passed unchanged through the
    application call chain; verification never manufactures a repository or
    resolves an implicit global store.
    """

    calculation: CalculationRevisionCatalogueRepositoryProtocol
    work_unit: WorkUnitCatalogueRepositoryProtocol
    filing: ModeloRecordCatalogueRepositoryProtocol
    transaction: TransactionCatalogueRepositoryProtocol
    verification: VerificationReportCatalogueRepositoryProtocol
    bucket_event: BucketEventHistoryRepositoryProtocol
    observation: CalculationObservationRepositoryProtocol
    iva_compensation_history: IvaCompensationHistoryRepositoryProtocol
    iva_compensation_decision: IvaWalletDecisionRepositoryProtocol
    participation_index: TransactionParticipationIndexRepositoryProtocol
    workflow_run: WorkflowRunRepositoryProtocol
    justificante: JustificanteRepositoryProtocol
    draft_review_ports: DraftReviewPorts
    workflow_gate_ports: WorkflowGatePorts
    retencion_observation_ports: RetencionObservationPorts


VerificationRepositoryBundleFactory = Callable[[str], VerificationRepositoryBundle]


__all__ = [
    "CalculationObservationRepositoryProtocol",
    "IvaWalletDecisionRepositoryProtocol",
    "VerificationRepositoryBundle",
    "VerificationRepositoryBundleFactory",
    "WorkflowRunRepositoryProtocol",
]
