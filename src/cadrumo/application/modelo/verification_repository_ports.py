"""Application-owned repository ports for modelo verification.

Verification is an application use case: it coordinates several persistence
capabilities, but it must not know which encrypted-storage adapters implement
them.  This module keeps that capability boundary in the application layer.
The outer composition root supplies the concrete implementations as one
coherent bundle for each profile bucket.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ...core.observed_header_fact import ObservedHeaderFact
from ...core.period import Period
from ...core.time.utc import UtcInstant
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry.bindings import RegistryModeloObservation
from ...domain.calculations.registry.ids import RevisionId
from ...domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from ...domain.justificante.protocols import JustificanteRepositoryProtocol
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    TransactionParticipationIndexRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..filing.draft_review_ports import DraftReviewPorts
from ..workflow.run_models import WorkflowResult

if TYPE_CHECKING:
    from .workflow_gate_ports import WorkflowGatePorts


@runtime_checkable
class CalculationObservationPayloadProtocol(Protocol):
    """Safe read DTO exposed by the calculation-observation capability."""

    observation: RegistryModeloObservation
    captured_at: UtcInstant
    source_kind: object
    member_nif: str | None
    stamped_revision_id: RevisionId
    source_metadata: Mapping[str, str]
    source_headers: tuple[ObservedHeaderFact, ...]


@runtime_checkable
class CalculationObservationRepositoryProtocol(Protocol):
    """Read-side contract for persisted calculation observations."""

    def load_observation(self, modelo: str, period: Period) -> CalculationObservationPayloadProtocol | None:
        """Return one observation for a modelo and period, when present."""
        ...

    def iter_modelo(self, modelo: str) -> Iterator[CalculationObservationPayloadProtocol]:
        """Yield every persisted observation for ``modelo``."""
        ...


@runtime_checkable
class IvaWalletDecisionRepositoryProtocol(Protocol):
    """Read-side contract for persisted IVA-wallet decisions."""

    def load_decision(
        self,
        taxpayer_nif: str,
        target_period: Period,
    ) -> IvaCompensationReconciliationDecision | None:
        """Return the latest persisted decision for one target period."""
        ...


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
    iva_compensation_decision: IvaWalletDecisionRepositoryProtocol
    participation_index: TransactionParticipationIndexRepositoryProtocol
    workflow_run: WorkflowRunRepositoryProtocol
    justificante: JustificanteRepositoryProtocol
    draft_review_ports: DraftReviewPorts
    workflow_gate_ports: WorkflowGatePorts


VerificationRepositoryBundleFactory = Callable[[str], VerificationRepositoryBundle]


__all__ = [
    "CalculationObservationRepositoryProtocol",
    "CalculationObservationPayloadProtocol",
    "IvaWalletDecisionRepositoryProtocol",
    "VerificationRepositoryBundle",
    "VerificationRepositoryBundleFactory",
    "WorkflowRunRepositoryProtocol",
]
