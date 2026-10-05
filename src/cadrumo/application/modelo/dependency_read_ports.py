"""Explicit profile and persistence capabilities for dependency inspection.

Core types: :class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.justificante.protocols import JustificanteRepositoryProtocol
from ...domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
    VerificationReportCatalogueRepositoryProtocol,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..calculations.observations_repository import CalculationObservationRepositoryProtocol


@dataclass(frozen=True, slots=True)
class DependencyReadRepositories:
    """Only repositories consumed by canonical clean-state evaluation."""

    work_unit: WorkUnitCatalogueRepositoryProtocol
    calculation: CalculationRevisionCatalogueRepositoryProtocol
    filing: ModeloRecordCatalogueRepositoryProtocol
    verification: VerificationReportCatalogueRepositoryProtocol
    observation: CalculationObservationRepositoryProtocol
    justificante: JustificanteRepositoryProtocol


@dataclass(frozen=True, slots=True)
class DependencyReadPorts:
    """One profile's captured taxpayer and explicitly composed repositories."""

    bucket_id: str
    profile: TaxpayerProfile
    m111_no_retenciones_periods: frozenset[tuple[int, str]]
    repositories: DependencyReadRepositories


class DependencyReadPortsFactory(Protocol):
    """Compose dependency inspection under retained published authority."""

    def __call__(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> DependencyReadPorts:
        """Return only capabilities for the requested immutable worker profile."""
        ...
