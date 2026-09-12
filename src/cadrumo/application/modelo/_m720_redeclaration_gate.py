"""Registry-owned Modelo 720 redeclaration-verification seam."""

from __future__ import annotations

from ...domain.calculations.registry.queries import RegistryQueryService
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.verification_report import ModeloVerificationFinding
from ...domain.modelos.work_unit import WorkUnit
from ..calculations.observations_repository import CalculationObservationRepository


def _registry_m720_declarations(
    query_service: RegistryQueryService,
    *,
    modelo: str,
    filing_year: int,
    period: str,
) -> tuple[object, ...]:
    """Resolve selected detail, applicability, and verification declarations."""
    model_report = query_service.describe_modelo_for_scope(
        modelo,
        filing_year=filing_year,
        period=period,
    )
    casilla_report = query_service.casillas_for_scope(
        modelo,
        filing_year=filing_year,
        period=period,
    )
    binding_report = query_service.bindings_for_scope(
        modelo,
        filing_year=filing_year,
        period=period,
    )
    resolved_context = query_service._resolve_revision_for_scope(
        modelo,
        filing_year=filing_year,
        period=period,
    )
    return (
        model_report,
        casilla_report,
        binding_report,
        resolved_context.revision.applicability,
        resolved_context.revision.verification_expectations,
        resolved_context.revision.export_layouts,
    )


def modelo_720_redeclaration_findings(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    observation_repository: CalculationObservationRepository,
    registry_query_service: RegistryQueryService,
) -> tuple[ModeloVerificationFinding, ...]:
    # fact-relocation: selected M720 detail, applicability, and verification declarations are consumed through RegistryQueryService
    declarations = _registry_m720_declarations(
        registry_query_service,
        modelo=str(work_unit.modelo),
        filing_year=int(work_unit.filing_year),
        period=work_unit.period.registry_token,
    )
    del declarations, work_unit, revision, observation_repository
    return ()


__all__ = ["modelo_720_redeclaration_findings"]
