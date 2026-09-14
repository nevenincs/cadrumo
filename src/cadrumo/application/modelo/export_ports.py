"""Application-owned capabilities required by Modelo declaration export.

Modelo export coordinates several persisted authorities, but the use case must
not know which encrypted-storage adapters implement them.  The executable
composition root supplies one bundle for the target profile bucket.  Keeping
the bundle explicit also makes the M303 ledger projection use the same
prorrata, investment, and transaction authorities as the rest of the export.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from cadrumo.domain.calculations.registry.tax_id_format import SubjectTaxId
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.justificante.protocols import JustificanteRepositoryProtocol
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..bienes_inversion.ports import BienesInversionIvaRegisterRepositoryProtocol
from ..filing.draft_review_ports import DraftReviewPorts
from .verification_repository_ports import (
    CalculationObservationRepositoryProtocol,
    IvaWalletDecisionRepositoryProtocol,
)


@dataclass(frozen=True, slots=True)
class ModeloExportPorts:
    """Required persisted authorities for one Modelo export invocation.

    Every field is required.  The bundle is assembled by an outer composition
    root and passed unchanged through the application call chain; export never
    manufactures a repository or resolves an implicit global store.
    """

    calculation: CalculationRevisionCatalogueRepositoryProtocol
    work_unit: WorkUnitCatalogueRepositoryProtocol
    filing: ModeloRecordCatalogueRepositoryProtocol
    verification: VerificationReportCatalogueRepositoryProtocol
    bucket_event: BucketEventHistoryRepositoryProtocol
    observation: CalculationObservationRepositoryProtocol
    iva_compensation_decision: IvaWalletDecisionRepositoryProtocol
    justificante: JustificanteRepositoryProtocol
    prorrata_register: ProrrataRegisterRepositoryProtocol
    bienes_inversion: BienesInversionIvaRegisterRepositoryProtocol
    transaction: TransactionCatalogueRepositoryProtocol
    draft_review_ports: DraftReviewPorts


class ModeloExportPortsFactory(Protocol):
    """Construct one export bundle for a target bucket and taxpayer identity."""

    def __call__(
        self,
        *,
        bucket_id: str,
        m303_rectificativa_taxpayer_tax_id: SubjectTaxId,
    ) -> ModeloExportPorts:
        """Return all authorities required by one export invocation."""
        ...


__all__ = [
    "ModeloExportPorts",
    "ModeloExportPortsFactory",
]
