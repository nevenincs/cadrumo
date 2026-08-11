"""Exhaustive typed applicability gate for the whole Modelo 303 export."""

from __future__ import annotations

from ...core import (
    M303DifferentiatedDeductionProjectionRef,
    M303Exonerado390ActivityProjectionRef,
    M303Exonerado390OperacionesTercerosProjectionRef,
    M303ProrrataActivityProjectionRef,
    M303RegimenSimplificadoActivityProjectionRef,
    M303RegimenSimplificadoFactProjectionRef,
    M303RegimenSimplificadoModuleProjectionRef,
    Period,
)
from ...domain.calculations.registry import (
    RegistryValidationError,
    project_m303_differentiated_deduction_rows,
    project_m303_prorrata_activity_rows,
)
from ...domain.filing import FilingExportError
from ._m303_exonerado_390 import project_m303_exonerado_390_value_arrival
from ._m303_prorrata_activity_rows import assert_m303_prorrata_activity_rows_complete
from ._m303_regimen_simplificado import (
    project_m303_regimen_simplificado_value_arrival,
)
from ._producer_snapshot import FilingProducerSnapshot
from .runtime import RegistrySchemaAccessor


def validate_m303_export_applicability(
    *,
    period: Period,
    schema_provider: RegistrySchemaAccessor,
    producer_snapshot: FilingProducerSnapshot,
) -> dict[tuple[str, int | None], object]:
    """Validate M303 facts and return exact typed projection values for rendering."""
    try:
        FilingProducerSnapshot.model_validate(dict(producer_snapshot))
    except ValueError as exc:
        raise FilingExportError(f"modelo 303 filing producer snapshot is incomplete: {exc}") from exc
    subview = schema_provider.get_subview("303")
    filing_facts = producer_snapshot.m303_filing_facts
    if filing_facts is None:
        raise FilingExportError("modelo 303 export requires internally assembled filing facts")
    projection_refs = tuple(
        field.projection_ref
        for layout in subview.export_layouts
        for record in layout.records
        for field in record.fields
        if field.projection_ref is not None
    )
    projected_values: dict[tuple[str, int | None], object] = {}
    exonerado_refs = tuple(
        ref
        for ref in projection_refs
        if isinstance(
            ref,
            M303Exonerado390ActivityProjectionRef | M303Exonerado390OperacionesTercerosProjectionRef,
        )
    )
    prorrata_refs = tuple(ref for ref in projection_refs if isinstance(ref, M303ProrrataActivityProjectionRef))
    differentiated_refs = tuple(
        ref for ref in projection_refs if isinstance(ref, M303DifferentiatedDeductionProjectionRef)
    )
    simplified_refs = tuple(
        ref
        for ref in projection_refs
        if isinstance(
            ref,
            M303RegimenSimplificadoActivityProjectionRef
            | M303RegimenSimplificadoFactProjectionRef
            | M303RegimenSimplificadoModuleProjectionRef,
        )
    )
    exonerado_projection = project_m303_exonerado_390_value_arrival(
        period=period,
        schema_provider=schema_provider,
        evidence=filing_facts.exonerado_390,
        record_design=filing_facts.regimen_simplificado.regimen_snapshot.record_design,
        projection_refs=exonerado_refs,
    )
    if filing_facts.exonerado_390.applicable:
        if exonerado_projection is None:
            raise FilingExportError("modelo 303 exonerado-390 projector omitted an applicable record")
        projected_values.update(
            ((field.projection_ref.model_dump_json(), None), field.value) for field in exonerado_projection.fields
        )
    else:
        projected_values.update(((ref.model_dump_json(), None), None) for ref in exonerado_refs)
    register = filing_facts.prorrata_register
    if register.requires_activity_rows_for(period.filing_year):
        assert_m303_prorrata_activity_rows_complete(period=period, register=register)
    try:
        prorrata_projection = project_m303_prorrata_activity_rows(
            projection_refs=prorrata_refs,
            register=register,
            ejercicio=period.filing_year,
        )
        projected_values.update(
            ((endpoint.projection_ref.model_dump_json(), None), endpoint.value)
            for row in prorrata_projection
            for endpoint in row.endpoints
        )
        if not register.requires_activity_rows_for(period.filing_year):
            projected_values.update(((ref.model_dump_json(), None), None) for ref in prorrata_refs)
    except RegistryValidationError as exc:
        raise FilingExportError(f"modelo 303 prorrata activities refused: {exc}") from exc
    if register.is_sectorized:
        register_ids = {record.identifier for record in filing_facts.bienes_register.records}
        result_ids = {row.identifier for row in filing_facts.regularisation_result.rows}
        if not result_ids.issubset(register_ids):
            raise FilingExportError("modelo 303 differentiated regularisation lacks canonical Bienes register rows")
        try:
            differentiated_projection = project_m303_differentiated_deduction_rows(
                projection_refs=differentiated_refs,
                register=register,
                ejercicio=period.filing_year,
                contributions=filing_facts.differentiated_contributions,
                regularisation_result=filing_facts.regularisation_result,
            )
            projected_values.update(
                ((endpoint.projection_ref.model_dump_json(), None), endpoint.value)
                for row in differentiated_projection
                for endpoint in row.endpoints
            )
        except RegistryValidationError as exc:
            raise FilingExportError(f"modelo 303 differentiated sectors refused: {exc}") from exc
    else:
        projected_values.update(((ref.model_dump_json(), None), None) for ref in differentiated_refs)
    simplified_projection = project_m303_regimen_simplificado_value_arrival(
        period=period,
        schema_provider=schema_provider,
        evidence=filing_facts.regimen_simplificado,
        projection_refs=simplified_refs,
    )
    if not filing_facts.regimen_simplificado.scope_decision.is_not_claimed and not simplified_projection:
        raise FilingExportError("modelo 303 regimen simplificado projector omitted applicable record occurrences")
    projected_values.update(
        ((field.projection_ref.model_dump_json(), row.record - 1), field.value)
        for row in simplified_projection
        for field in row.fields
    )
    return projected_values


__all__ = ["validate_m303_export_applicability"]
