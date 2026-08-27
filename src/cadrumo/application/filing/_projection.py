"""Snapshot-owned repeated-row projection plan for filing export."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core import (
    STRICT_FROZEN_CONFIG,
    FilingProjectionRef,
    M303DifferentiatedDeductionProjectionRef,
    M303Exonerado390ActivityProjectionRef,
    M303Exonerado390OperacionesTercerosProjectionRef,
    M303ProrrataActivityProjectionRef,
    M303RegimenSimplificadoActivityProjectionRef,
    M303RegimenSimplificadoFactProjectionRef,
    M303RegimenSimplificadoModuleProjectionRef,
    Modelo,
)
from ...domain.calculations.export_field_kind import CasillaFieldKind
from ...domain.calculations.registry.ids import RecordId
from ...domain.calculations.registry.m303_differentiated_deduction_projection import (
    project_m303_differentiated_deduction_rows,
)
from ...domain.calculations.registry.m303_prorrata_activity_projection import project_m303_prorrata_activity_rows
from ...domain.calculations.registry.m303_regimen_simplificado_projection import (
    project_m303_regimen_simplificado_rows,
    validate_m303_regimen_simplificado_endpoint_epoch,
)
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition, ExportRecordDefinition
from ...domain.filing import FilingExportValidationError
from ...domain.iva import ActividadNoAgricolaSimplificado
from ._m303_exonerado_390 import project_m303_exonerado_390_value_arrival
from ._producer_snapshot import FilingProducerSnapshot, M303FilingFacts

type _RegimenSimplificadoProjectionRef = (
    M303RegimenSimplificadoActivityProjectionRef
    | M303RegimenSimplificadoFactProjectionRef
    | M303RegimenSimplificadoModuleProjectionRef
)
type _ExoneradoProjectionRef = M303Exonerado390ActivityProjectionRef | M303Exonerado390OperacionesTercerosProjectionRef


class FilingProjectionValue(BaseModel):
    """One produced repeated-row value at its exact record occurrence address."""

    model_config = STRICT_FROZEN_CONFIG

    projection_ref: FilingProjectionRef
    record_id: RecordId
    occurrence: int = Field(gt=0)
    value: str | Decimal | None

    @field_validator("projection_ref", mode="before")
    @classmethod
    def _require_typed_projection_ref(cls, value: object) -> object:
        if not isinstance(value, BaseModel):
            raise FilingExportValidationError("filing projection values require an actual typed projection_ref")
        return value


class FilingRecordRenderContext(BaseModel):
    """Snapshot-owned layout record plus its positive emitted occurrence."""

    model_config = STRICT_FROZEN_CONFIG

    registry_snapshot: RegistrySnapshot
    layout: ExportLayoutDefinition
    record: ExportRecordDefinition
    occurrence: int = Field(gt=0)

    @model_validator(mode="after")
    def _require_snapshot_owned_record(self) -> FilingRecordRenderContext:
        if not any(candidate is self.layout for candidate in self.registry_snapshot.revision.export_layouts):
            raise FilingExportValidationError("filing render context layout is not owned by its registry snapshot")
        if not any(candidate is self.record for candidate in self.layout.records):
            raise FilingExportValidationError("filing render context record is not owned by its selected layout")
        return self


class FilingProjectionPlan(BaseModel):
    """Complete projection contexts and values produced before byte rendering."""

    model_config = STRICT_FROZEN_CONFIG

    contexts: tuple[FilingRecordRenderContext, ...]
    values: tuple[FilingProjectionValue, ...]


def build_m303_filing_projection_plan(
    *,
    registry_snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
    producer_snapshot: FilingProducerSnapshot,
) -> FilingProjectionPlan:
    """Project every M303 repeated-row family from one selected snapshot and layout."""
    _validate_m303_projection_request(
        registry_snapshot=registry_snapshot,
        layout=layout,
        producer_snapshot=producer_snapshot,
    )
    _require_regimen_snapshot_matches_registry(registry_snapshot, producer_snapshot)
    contexts, values = _project_layout_records(
        registry_snapshot=registry_snapshot,
        layout=layout,
        producer_snapshot=producer_snapshot,
    )
    return FilingProjectionPlan(contexts=contexts, values=values)


def _validate_m303_projection_request(
    *,
    registry_snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
    producer_snapshot: FilingProducerSnapshot,
) -> M303FilingFacts:
    """Validate the shared snapshot/layout boundary before projecting rows."""
    facts = producer_snapshot.m303_filing_facts
    if producer_snapshot.modelo != Modelo.M303 or registry_snapshot.modelo.id != Modelo.M303 or facts is None:
        raise FilingExportValidationError("M303 filing projection requires one complete Modelo 303 snapshot")
    if (
        facts.period.filing_year != registry_snapshot.filing_year
        or facts.period.registry_token != registry_snapshot.period
    ):
        raise FilingExportValidationError("M303 filing projection snapshot does not match the filing period")
    if not any(candidate is layout for candidate in registry_snapshot.revision.export_layouts):
        raise FilingExportValidationError("M303 filing projection layout is not owned by the selected snapshot")
    return facts


def _project_layout_records(
    *,
    registry_snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
    producer_snapshot: FilingProducerSnapshot,
) -> tuple[tuple[FilingRecordRenderContext, ...], tuple[FilingProjectionValue, ...]]:
    """Project each layout record that admits a typed projection family."""
    contexts: list[FilingRecordRenderContext] = []
    values: list[FilingProjectionValue] = []
    for record in layout.records:
        refs = _record_projection_refs(record)
        if not refs:
            continue
        record_contexts, record_values = _project_record(
            registry_snapshot=registry_snapshot,
            layout=layout,
            record=record,
            refs=refs,
            producer_snapshot=producer_snapshot,
        )
        _require_required_projection_occurrence(record, record_contexts)
        contexts.extend(record_contexts)
        values.extend(record_values)
    return tuple(contexts), tuple(values)


def _require_required_projection_occurrence(
    record: ExportRecordDefinition,
    contexts: tuple[FilingRecordRenderContext, ...],
) -> None:
    if not contexts and record.required:
        raise FilingExportValidationError(
            f"required projection record {record.id!r} has no applicable emitted occurrence",
        )


def _record_projection_refs(record: ExportRecordDefinition) -> tuple[FilingProjectionRef, ...]:
    return tuple(
        field.projection_ref
        for field in record.fields
        if field.kind is CasillaFieldKind.PROJECTION and field.projection_ref is not None
    )


def _project_record(
    *,
    registry_snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
    record: ExportRecordDefinition,
    refs: tuple[FilingProjectionRef, ...],
    producer_snapshot: FilingProducerSnapshot,
) -> tuple[tuple[FilingRecordRenderContext, ...], tuple[FilingProjectionValue, ...]]:
    facts = _require_m303_projection_facts(producer_snapshot)
    ref_types = {type(ref) for ref in refs}
    if ref_types == {M303ProrrataActivityProjectionRef, M303DifferentiatedDeductionProjectionRef}:
        return _project_prorrata_and_differentiated_record(
            registry_snapshot=registry_snapshot,
            layout=layout,
            record=record,
            refs=refs,
            facts=facts,
        )
    if ref_types == {M303ProrrataActivityProjectionRef}:
        return _project_prorrata_record(
            registry_snapshot=registry_snapshot,
            layout=layout,
            record=record,
            refs=refs,
            facts=facts,
        )
    if ref_types == {M303DifferentiatedDeductionProjectionRef}:
        return _project_differentiated_record(
            registry_snapshot=registry_snapshot,
            layout=layout,
            record=record,
            refs=refs,
            facts=facts,
        )
    if ref_types.issubset(
        {
            M303RegimenSimplificadoActivityProjectionRef,
            M303RegimenSimplificadoFactProjectionRef,
            M303RegimenSimplificadoModuleProjectionRef,
        },
    ):
        return _project_regimen_record(
            registry_snapshot=registry_snapshot,
            layout=layout,
            record=record,
            refs=refs,
            facts=facts,
        )
    if ref_types.issubset({M303Exonerado390ActivityProjectionRef, M303Exonerado390OperacionesTercerosProjectionRef}):
        return _project_exonerado_record(
            registry_snapshot=registry_snapshot,
            layout=layout,
            record=record,
            refs=refs,
            facts=facts,
        )
    raise FilingExportValidationError(
        f"projection record {record.id!r} mixes or uses an unsupported projection-reference family",
    )


def _project_prorrata_and_differentiated_record(
    *,
    registry_snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
    record: ExportRecordDefinition,
    refs: tuple[FilingProjectionRef, ...],
    facts: M303FilingFacts,
) -> tuple[tuple[FilingRecordRenderContext, ...], tuple[FilingProjectionValue, ...]]:
    """Compose the two independent DP30305 value families into its one occurrence.

    The record layout owns the interleaving order.  Each canonical projector is
    called exactly once over only its closed family; this dispatcher then binds
    their typed results back to that authored order.  Any third family remains
    outside this explicit composition and is refused by :func:`_project_record`.
    """
    prorrata_contexts, prorrata_values = _project_prorrata_record(
        registry_snapshot=registry_snapshot,
        layout=layout,
        record=record,
        refs=refs,
        facts=facts,
    )
    differentiated_contexts, differentiated_values = _project_differentiated_record(
        registry_snapshot=registry_snapshot,
        layout=layout,
        record=record,
        refs=refs,
        facts=facts,
    )
    contexts = _compose_single_occurrence_contexts(
        record=record,
        prorrata_contexts=prorrata_contexts,
        differentiated_contexts=differentiated_contexts,
    )
    values_by_reference = {value.projection_ref: value for value in (*prorrata_values, *differentiated_values)}
    if len(values_by_reference) != len(prorrata_values) + len(differentiated_values):
        raise FilingExportValidationError(f"projection record {record.id!r} emitted duplicate typed projection values")
    try:
        return contexts, tuple(values_by_reference[reference] for reference in refs)
    except KeyError as exc:
        raise FilingExportValidationError(
            f"projection record {record.id!r} did not emit every authored typed projection reference",
        ) from exc


def _compose_single_occurrence_contexts(
    *,
    record: ExportRecordDefinition,
    prorrata_contexts: tuple[FilingRecordRenderContext, ...],
    differentiated_contexts: tuple[FilingRecordRenderContext, ...],
) -> tuple[FilingRecordRenderContext, ...]:
    """Require both DP30305 families to describe its same one canonical occurrence."""
    all_contexts = (*prorrata_contexts, *differentiated_contexts)
    if not all_contexts:
        return ()
    by_address = {(context.record.id, context.occurrence): context for context in all_contexts}
    if len(by_address) != 1:
        raise FilingExportValidationError(
            f"projection record {record.id!r} families do not resolve to one deterministic occurrence",
        )
    return tuple(by_address.values())


def _require_m303_projection_facts(producer_snapshot: FilingProducerSnapshot) -> M303FilingFacts:
    facts = producer_snapshot.m303_filing_facts
    if facts is None:
        raise FilingExportValidationError("M303 projection record requires complete filing facts")
    return facts


def _project_prorrata_record(
    *,
    registry_snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
    record: ExportRecordDefinition,
    refs: tuple[FilingProjectionRef, ...],
    facts: M303FilingFacts,
) -> tuple[tuple[FilingRecordRenderContext, ...], tuple[FilingProjectionValue, ...]]:
    _require_nonrepeated_projection_record(record)
    projected = project_m303_prorrata_activity_rows(
        projection_refs=tuple(ref for ref in refs if isinstance(ref, M303ProrrataActivityProjectionRef)),
        register=facts.prorrata_register,
        ejercicio=facts.period.filing_year,
    )
    fields = tuple(endpoint for row in projected for endpoint in row.endpoints)
    return _single_occurrence_projection(registry_snapshot, layout, record, fields)


def _project_differentiated_record(
    *,
    registry_snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
    record: ExportRecordDefinition,
    refs: tuple[FilingProjectionRef, ...],
    facts: M303FilingFacts,
) -> tuple[tuple[FilingRecordRenderContext, ...], tuple[FilingProjectionValue, ...]]:
    _require_nonrepeated_projection_record(record)
    projected = project_m303_differentiated_deduction_rows(
        projection_refs=tuple(ref for ref in refs if isinstance(ref, M303DifferentiatedDeductionProjectionRef)),
        register=facts.prorrata_register,
        ejercicio=facts.period.filing_year,
        contributions=facts.differentiated_contributions,
        regularisation_result=facts.regularisation_result,
    )
    fields = tuple(endpoint for row in projected for endpoint in row.endpoints)
    return _single_occurrence_projection(registry_snapshot, layout, record, fields)


def _project_regimen_record(
    *,
    registry_snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
    record: ExportRecordDefinition,
    refs: tuple[FilingProjectionRef, ...],
    facts: M303FilingFacts,
) -> tuple[tuple[FilingRecordRenderContext, ...], tuple[FilingProjectionValue, ...]]:
    if record.repeat != "projection_rows":
        raise FilingExportValidationError("regimen-simplificado projection record must repeat projection_rows")
    evidence = facts.regimen_simplificado
    regimen_refs = tuple(ref for ref in refs if isinstance(ref, _REGIMEN_REF_TYPES))
    validate_m303_regimen_simplificado_endpoint_epoch(regimen_refs, revision_id=str(registry_snapshot.revision.id))
    projected = project_m303_regimen_simplificado_rows(
        projection_refs=regimen_refs,
        rows=evidence.rows,
        orden=evidence.regimen_snapshot.orden.activities,
        agricultural_authority=evidence.regimen_snapshot.orden.agricultural_authority,
        applicable=not evidence.scope_decision.is_not_claimed,
        calculation_result=facts.regimen_simplificado_result,
        censo_iae_epigraphs=frozenset(
            row.iae_epigrafe for row in evidence.rows.activities if isinstance(row, ActividadNoAgricolaSimplificado)
        ),
    )
    contexts = tuple(_context(registry_snapshot, layout, record, row.record) for row in projected)
    values = tuple(
        FilingProjectionValue(
            projection_ref=field.projection_ref,
            record_id=record.id,
            occurrence=row.record,
            value=field.value,
        )
        for row in projected
        for field in row.fields
    )
    return contexts, values


def _project_exonerado_record(
    *,
    registry_snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
    record: ExportRecordDefinition,
    refs: tuple[FilingProjectionRef, ...],
    facts: M303FilingFacts,
) -> tuple[tuple[FilingRecordRenderContext, ...], tuple[FilingProjectionValue, ...]]:
    _require_nonrepeated_projection_record(record)
    evidence = facts.regimen_simplificado.regimen_snapshot
    projected = project_m303_exonerado_390_value_arrival(
        registry_snapshot=registry_snapshot,
        projection_refs=tuple(ref for ref in refs if isinstance(ref, _EXONERADO_REF_TYPES)),
        evidence=facts.exonerado_390,
        record_design=evidence.record_design,
    )
    return _single_occurrence_projection(
        registry_snapshot,
        layout,
        record,
        () if projected is None else projected.fields,
    )


_REGIMEN_REF_TYPES = (
    M303RegimenSimplificadoActivityProjectionRef,
    M303RegimenSimplificadoFactProjectionRef,
    M303RegimenSimplificadoModuleProjectionRef,
)
_EXONERADO_REF_TYPES = (M303Exonerado390ActivityProjectionRef, M303Exonerado390OperacionesTercerosProjectionRef)


def _single_occurrence_projection(
    registry_snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
    record: ExportRecordDefinition,
    fields: tuple[object, ...],
) -> tuple[tuple[FilingRecordRenderContext, ...], tuple[FilingProjectionValue, ...]]:
    if not fields:
        return (), ()
    context = _context(registry_snapshot, layout, record, 1)
    values: list[FilingProjectionValue] = []
    for field in fields:
        projection_ref = getattr(field, "projection_ref", None)
        if not isinstance(projection_ref, BaseModel):
            raise FilingExportValidationError("projector returned a field without an actual typed projection_ref")
        values.append(
            FilingProjectionValue(
                projection_ref=cast(FilingProjectionRef, projection_ref),
                record_id=record.id,
                occurrence=1,
                value=getattr(field, "value", None),
            ),
        )
    return (context,), tuple(values)


def _context(
    snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
    record: ExportRecordDefinition,
    occurrence: int,
) -> FilingRecordRenderContext:
    return FilingRecordRenderContext(
        registry_snapshot=snapshot,
        layout=layout,
        record=record,
        occurrence=occurrence,
    )


def _require_nonrepeated_projection_record(record: ExportRecordDefinition) -> None:
    if record.repeat is not None:
        raise FilingExportValidationError(
            f"projection record {record.id!r} uses repeat={record.repeat!r} for a non-repeated family",
        )


def _require_regimen_snapshot_matches_registry(
    registry_snapshot: RegistrySnapshot,
    producer_snapshot: FilingProducerSnapshot,
) -> None:
    facts = producer_snapshot.m303_filing_facts
    if facts is None:
        raise FilingExportValidationError("M303 projection requires complete filing facts")
    evidence = facts.regimen_simplificado.regimen_snapshot
    record_design = registry_snapshot.sources.get(evidence.record_design.id)
    if record_design is None or record_design != evidence.record_design:
        raise FilingExportValidationError("M303 filing evidence record design is not owned by the selected snapshot")
    if (
        evidence.orden.ejercicio != registry_snapshot.filing_year
        or evidence.orden.registry_revision_id != registry_snapshot.revision.id
        or evidence.orden.source_ref not in registry_snapshot.sources
    ):
        raise FilingExportValidationError("M303 filing evidence annual Orden does not match the selected snapshot")


__all__ = [
    "FilingProjectionPlan",
    "FilingProjectionValue",
    "FilingRecordRenderContext",
    "build_m303_filing_projection_plan",
]
