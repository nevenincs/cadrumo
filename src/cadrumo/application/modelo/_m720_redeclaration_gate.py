"""Registry-owned Modelo 720 redeclaration-verification seam."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.verification_report import ModeloVerificationFinding
from ...domain.modelos.work_unit import WorkUnit
from .verification_repository_ports import CalculationObservationRepositoryProtocol

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


def _registry_m720_declarations(
    operation: PinnedAuthorityOperation,
    *,
    modelo: str,
    filing_year: int,
    period: str,
) -> ModeloRevision:
    """Load the selected M720 declarations from one pinned operation."""
    return operation.revision_for_context(
        modelo,
        filing_year=filing_year,
        period=period,
    )


def modelo_720_redeclaration_findings(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    observation_repository: CalculationObservationRepositoryProtocol,
    operation: PinnedAuthorityOperation,
) -> tuple[ModeloVerificationFinding, ...]:
    # fact-relocation: selected M720 detail, applicability, and verification declarations
    # are consumed through the caller's generation-pinned operation.
    declarations = _registry_m720_declarations(
        operation,
        modelo=str(work_unit.modelo),
        filing_year=int(work_unit.filing_year),
        period=work_unit.period.registry_token,
    )
    del declarations, work_unit, revision, observation_repository
    return ()


__all__ = ["modelo_720_redeclaration_findings"]
