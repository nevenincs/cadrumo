"""M303 regimen-simplificado typed value arrival before export targets."""

from __future__ import annotations

from pathlib import Path

from ...core import (
    M303RegimenSimplificadoActivityProjectionRef,
    M303RegimenSimplificadoFactProjectionRef,
    M303RegimenSimplificadoModuleProjectionRef,
    Period,
)
from ...domain.calculations.registry import (
    M303RegimenSimplificadoRecordProjection,
    RegistryValidationError,
    SourceReference,
    project_m303_regimen_simplificado_rows,
    resolve_record_design_binary,
)
from ...domain.filing import FilingExportError
from ...domain.iva import ActividadNoAgricolaSimplificado
from ...domain.modelos import M303RegimenSimplificadoFilingEvidence
from .runtime import RegistrySchemaAccessor


def _validate_filing_year(
    *,
    period: Period,
    evidence: M303RegimenSimplificadoFilingEvidence,
) -> None:
    if evidence.rows.ejercicio != period.filing_year:
        raise FilingExportError("modelo 303 regimen simplificado rows do not match the filing year")


def _require_registry_source_root(schema_provider: RegistrySchemaAccessor) -> Path:
    source_root = schema_provider.source_root
    if source_root is None:
        raise FilingExportError("modelo 303 regimen simplificado projection requires the registry source root")
    return source_root


def _validate_record_design_source(
    *,
    schema_provider: RegistrySchemaAccessor,
    source: SourceReference,
) -> str:
    subview = schema_provider.get_subview("303")
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
    return source_epoch


def project_m303_regimen_simplificado_value_arrival(
    *,
    period: Period,
    schema_provider: RegistrySchemaAccessor,
    evidence: M303RegimenSimplificadoFilingEvidence,
    projection_refs: tuple[
        M303RegimenSimplificadoActivityProjectionRef
        | M303RegimenSimplificadoFactProjectionRef
        | M303RegimenSimplificadoModuleProjectionRef,
        ...,
    ],
) -> tuple[M303RegimenSimplificadoRecordProjection, ...]:
    """Project the persisted S58 evidence through its exact S59 source snapshot."""
    _validate_filing_year(period=period, evidence=evidence)
    source_root = _require_registry_source_root(schema_provider)
    authority = evidence.regimen_snapshot
    source = authority.record_design
    source_epoch = _validate_record_design_source(schema_provider=schema_provider, source=source)
    resolved = resolve_record_design_binary(
        source_root,
        schema_provider.sources,
        source_ref=source.id,
        filing_year=period.filing_year,
        design_epoch=source_epoch,
    )
    try:
        if not resolved.path.is_file():
            raise RegistryValidationError("the resolved regimen-simplificado record design is not a file")
        return project_m303_regimen_simplificado_rows(
            projection_refs=projection_refs,
            rows=evidence.rows,
            orden=authority.orden.activities,
            applicable=not evidence.scope_decision.is_not_claimed,
            censo_iae_epigraphs=frozenset(
                activity.iae_epigrafe
                for activity in evidence.rows.activities
                if isinstance(activity, ActividadNoAgricolaSimplificado)
            ),
        )
    except RegistryValidationError as exc:
        raise FilingExportError(f"modelo 303 regimen simplificado projection refused: {exc}") from exc


__all__ = ["project_m303_regimen_simplificado_value_arrival"]
