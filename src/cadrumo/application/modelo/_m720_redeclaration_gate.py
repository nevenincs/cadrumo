"""Registry-owned Modelo 720 redeclaration-verification seam."""

from __future__ import annotations

from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.verification_report import ModeloVerificationFinding
from ...domain.modelos.work_unit import WorkUnit
from ..calculations.observations_repository import CalculationObservationRepository


def modelo_720_redeclaration_findings(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    observation_repository: CalculationObservationRepository,
) -> tuple[ModeloVerificationFinding, ...]:
    # TODO(fact-relocation): resolve M720 redeclaration gate and detail obligation from selected registry revision
    return ()


__all__ = ["modelo_720_redeclaration_findings"]
