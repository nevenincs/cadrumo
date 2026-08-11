"""M303 regimen-simplificado typed value arrival before export targets."""

from __future__ import annotations

from ...core import Period
from ...domain.calculations.registry import (
    M303RegimenSimplificadoRecordProjection,
    RegistryValidationError,
    extract_record_design,
    project_m303_regimen_simplificado_rows,
    resolve_record_design_binary,
)
from ...domain.filing import FilingExportError
from ...domain.iva import ActividadNoAgricolaSimplificado
from ...domain.modelos import M303RegimenSimplificadoFilingEvidence
from .runtime import RegistrySchemaAccessor


def project_m303_regimen_simplificado_value_arrival(
    *,
    period: Period,
    schema_provider: RegistrySchemaAccessor,
    evidence: M303RegimenSimplificadoFilingEvidence,
) -> tuple[M303RegimenSimplificadoRecordProjection, ...]:
    """Project the persisted S58 evidence through its exact S59 source snapshot."""
    if evidence.rows.ejercicio != period.filing_year:
        raise FilingExportError("modelo 303 regimen simplificado rows do not match the filing year")
    if schema_provider.source_root is None:
        raise FilingExportError("modelo 303 regimen simplificado projection requires the registry source root")
    authority = evidence.regimen_snapshot
    subview = schema_provider.get_subview("303")
    source = authority.record_design
    if source.id not in subview.source_ref_ids:
        raise FilingExportError("modelo 303 regimen simplificado record design is not cited by the active revision")
    registry_source = schema_provider.sources.get(source.id)
    if registry_source is None or registry_source.kind != "record_design":
        raise FilingExportError("modelo 303 regimen simplificado requires a cited record-design source")
    if registry_source != source:
        raise FilingExportError("modelo 303 regimen simplificado resolved record design no longer matches the registry")
    source_epoch = source.record_design_epoch
    if source_epoch is None:
        raise FilingExportError("modelo 303 regimen simplificado resolved record design has no design epoch")
    resolved = resolve_record_design_binary(
        schema_provider.source_root,
        schema_provider.sources,
        source_ref=source.id,
        filing_year=period.filing_year,
        design_epoch=source_epoch,
    )
    try:
        sheet = next(item for item in extract_record_design(resolved.path) if item.name == "DP30302")
        return project_m303_regimen_simplificado_rows(
            sheet,
            design_epoch=source_epoch,
            expected_design_epoch=authority.record_design.record_design_epoch or "",
            rows=evidence.rows,
            orden=authority.orden.activities,
            applicable=not evidence.scope_decision.is_not_claimed,
            censo_iae_epigraphs=frozenset(
                activity.iae_epigrafe
                for activity in evidence.rows.activities
                if isinstance(activity, ActividadNoAgricolaSimplificado)
            ),
        )
    except (StopIteration, RegistryValidationError) as exc:
        raise FilingExportError(f"modelo 303 regimen simplificado projection refused: {exc}") from exc


__all__ = ["project_m303_regimen_simplificado_value_arrival"]
