"""M303 regimen-simplificado typed value arrival before export targets."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG, Period
from ...domain.calculations.registry import (
    M303RegimenSimplificadoRecordProjection,
    RegistryValidationError,
    extract_record_design,
    project_m303_regimen_simplificado_rows,
    resolve_record_design_binary,
)
from ...domain.filing import FilingExportError
from ...domain.iva import ActividadOrdenAnual, IvaValidationError, RegimenSimplificadoFilingRows
from ...domain.period import period_end_date
from .runtime import RegistrySchemaAccessor


class M303RegimenSimplificadoValueArrival(BaseModel):
    """Typed filing facts and exact official-source selection for S50 projection."""

    model_config = STRICT_FROZEN_CONFIG

    rows: RegimenSimplificadoFilingRows
    orden: tuple[ActividadOrdenAnual, ...]
    applicable: bool
    censo_iae_epigraphs: frozenset[str]
    record_design_source_ref: str = Field(min_length=1)
    design_epoch: str = Field(min_length=1)


def project_m303_regimen_simplificado_value_arrival(
    *,
    period: Period,
    schema_provider: RegistrySchemaAccessor,
    value_arrival: M303RegimenSimplificadoValueArrival,
) -> tuple[M303RegimenSimplificadoRecordProjection, ...]:
    """Resolve the verified DP30302 source and project rows before target creation."""
    if value_arrival.rows.ejercicio != period.filing_year:
        raise FilingExportError("modelo 303 regimen simplificado rows do not match the filing year")
    if schema_provider.source_root is None:
        raise FilingExportError("modelo 303 regimen simplificado projection requires the registry source root")
    subview = schema_provider.get_subview("303")
    if value_arrival.record_design_source_ref not in subview.source_ref_ids:
        raise FilingExportError("modelo 303 regimen simplificado record design is not cited by the active revision")
    source = schema_provider.sources.get(value_arrival.record_design_source_ref)
    if source is None or source.kind != "record_design":
        raise FilingExportError("modelo 303 regimen simplificado requires a cited record-design source")
    source_epoch = source.record_design_epoch
    if source_epoch is None or source_epoch != value_arrival.design_epoch:
        raise FilingExportError("modelo 303 regimen simplificado value arrival carries the wrong design epoch")
    filing_date = period_end_date(period.filing_year, period.registry_token)
    applicable_sources = tuple(
        candidate
        for source_ref in subview.source_ref_ids
        if (candidate := schema_provider.sources.get(source_ref)) is not None
        and candidate.kind == "record_design"
        and candidate.applies_from is not None
        and candidate.applies_from <= filing_date
        and (candidate.applies_to is None or candidate.applies_to >= filing_date)
    )
    if not applicable_sources:
        raise FilingExportError("active modelo 303 revision cites no applicable record-design source")
    applicable_dates = tuple(
        candidate.applies_from for candidate in applicable_sources if candidate.applies_from is not None
    )
    newest_applies_from = max(applicable_dates)
    current_sources = tuple(
        candidate for candidate in applicable_sources if candidate.applies_from == newest_applies_from
    )
    if len(current_sources) != 1 or current_sources[0].id != source.id:
        raise FilingExportError("modelo 303 regimen simplificado value arrival carries a superseded design epoch")
    try:
        resolved = resolve_record_design_binary(
            schema_provider.source_root,
            schema_provider.sources,
            source_ref=value_arrival.record_design_source_ref,
            filing_year=period.filing_year,
            design_epoch=value_arrival.design_epoch,
        )
        sheet = next(item for item in extract_record_design(resolved.path) if item.name == "DP30302")
        return project_m303_regimen_simplificado_rows(
            sheet,
            design_epoch=value_arrival.design_epoch,
            expected_design_epoch=source_epoch,
            rows=value_arrival.rows,
            orden=value_arrival.orden,
            applicable=value_arrival.applicable,
            censo_iae_epigraphs=value_arrival.censo_iae_epigraphs,
        )
    except (IvaValidationError, RegistryValidationError, StopIteration) as exc:
        raise FilingExportError(f"modelo 303 regimen simplificado projection refused: {exc}") from exc


__all__ = ["M303RegimenSimplificadoValueArrival", "project_m303_regimen_simplificado_value_arrival"]
