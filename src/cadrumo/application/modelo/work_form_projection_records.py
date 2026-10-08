"""Read typed non-casilla activity endpoints from immutable saved evidence.

:class:`CalculationRevision` holds the saved calculation and its evidence.
:class:`RegistrySnapshot` pins the registry declarations used by the projection.
"""

from ...core.filing_projection_ref import (
    M303Exonerado390ActivityProjectionRef,
    M303Exonerado390OperacionesTercerosProjectionRef,
    M303RegimenSimplificadoActivityProjectionRef,
    M303RegimenSimplificadoFactProjectionRef,
    M303RegimenSimplificadoModuleProjectionRef,
)
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.export import derive_export_layouts_from_bindings
from ...domain.calculations.registry.form_context import resolve_form_context_field
from ...domain.calculations.registry.form_projection_fields import resolve_form_projection_fields
from ...domain.calculations.registry.m303_exonerado_390_projection import project_m303_exonerado_390_activity_rows
from ...domain.calculations.registry.m303_regimen_simplificado_projection import (
    project_m303_regimen_simplificado_rows,
    validate_m303_regimen_simplificado_endpoint_epoch,
)
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_form_layouts import FormContextFieldBlock, FormRepeatingGroupBlock
from ...domain.iva.regimen_simplificado_rows import ActividadNoAgricolaSimplificado
from ...domain.modelos.calculation_revision import CalculationRevision
from .work_form_models import ModeloFormRepeatingRow


def saved_projection_context_value(
    *, snapshot: RegistrySnapshot, revision: CalculationRevision | None, block: FormContextFieldBlock
) -> str | bool | None:
    """Read an annual activity endpoint through the complete filing projection.

    A missing slot stays unknown. The third-party declaration is a boolean
    fact, so an evidenced false decision remains distinguishable from absence.

    The ``revision`` parameter uses :class:`CalculationRevision`, which holds the saved calculation and its evidence.
    The ``snapshot`` parameter uses :class:`RegistrySnapshot`, which pins
    the registry declarations used by the projection.
    """
    field = resolve_form_context_field(snapshot.revision, block)
    supported = (M303Exonerado390ActivityProjectionRef, M303Exonerado390OperacionesTercerosProjectionRef)
    if not isinstance(field.projection_ref, supported):
        raise RegistryValidationError("unsupported scalar form projection")
    if str(snapshot.modelo.id) != "303":
        raise RegistryValidationError("annual activity projection requires Modelo 303")
    if revision is None:
        return None
    if revision.registry_snapshot_ref != snapshot.snapshot_ref:
        raise RegistryValidationError("saved projection value belongs to another registry coordinate")
    envelope = revision.filing_instance_evidence
    if envelope is None:
        return None
    if envelope.m303.period != snapshot.filing_period:
        raise RegistryValidationError("saved annual evidence belongs to another filing period")
    evidence = envelope.m303.exonerado_390
    if evidence is None:
        return None
    if evidence.applicable and str(snapshot.period) not in ("4T", "12"):
        raise RegistryValidationError("annual activity evidence requires the final filing period")
    record = next(
        record
        for layout in derive_export_layouts_from_bindings(snapshot.revision)
        if layout.id == block.export_layout_id
        for record in layout.records
        if record.id == block.export_record_id
    )
    refs = tuple(item.projection_ref for item in record.fields if isinstance(item.projection_ref, supported))
    projected = project_m303_exonerado_390_activity_rows(projection_refs=refs, evidence=evidence)
    if projected is None:
        return None
    if isinstance(field.projection_ref, M303Exonerado390OperacionesTercerosProjectionRef):
        return evidence.operaciones_terceros_declarables
    return next(item.value for item in projected.fields if item.projection_ref == field.projection_ref)


def saved_projection_form_records(
    *, snapshot: RegistrySnapshot, revision: CalculationRevision, block: FormRepeatingGroupBlock
) -> tuple[bool, tuple[ModeloFormRepeatingRow, ...]]:
    """Reuse the filing projection without opening profiles or recalculating tax.

    Unknown legacy evidence remains unknown. Explicitly unclaimed simplified
    scope is known-empty. Page occurrence numbers come from the domain owner;
    selecting a subset of fields never renumbers or joins unrelated activities.

    The ``revision`` parameter uses :class:`CalculationRevision`, which holds the saved calculation and its evidence.
    The ``snapshot`` parameter uses :class:`RegistrySnapshot`, which pins
    the registry declarations used by the projection.
    """
    if revision.registry_snapshot_ref != snapshot.snapshot_ref:
        raise RegistryValidationError("saved projection rows belong to another registry coordinate")
    fields = resolve_form_projection_fields(snapshot.revision, block)
    refs = tuple(field.projection_ref for field in fields)
    supported = (
        M303RegimenSimplificadoActivityProjectionRef,
        M303RegimenSimplificadoFactProjectionRef,
        M303RegimenSimplificadoModuleProjectionRef,
    )
    if not all(isinstance(ref, supported) for ref in refs):
        return False, ()
    if str(snapshot.modelo.id) != "303":
        raise RegistryValidationError("simplified-regime projection requires Modelo 303")
    envelope = revision.filing_instance_evidence
    if envelope is None:
        return False, ()
    facts = envelope.m303
    if facts.period != snapshot.filing_period:
        raise RegistryValidationError("saved activity evidence belongs to another filing period")
    evidence = facts.regimen_simplificado
    if (
        evidence.regimen_snapshot.registry_revision_id != snapshot.revision.id
        or evidence.regimen_snapshot.orden.registry_revision_id != snapshot.revision.id
    ):
        raise RegistryValidationError("saved activity evidence belongs to another registry revision")
    design = evidence.regimen_snapshot.record_design
    current_design = snapshot.sources.get(design.id)
    if current_design is None or current_design.sha256 != design.sha256:
        raise RegistryValidationError("saved activity evidence uses a different record-design source")
    regimen_refs = tuple(ref for ref in refs if isinstance(ref, supported))
    validate_m303_regimen_simplificado_endpoint_epoch(regimen_refs, revision_id=str(snapshot.revision.id))
    projected = project_m303_regimen_simplificado_rows(
        projection_refs=regimen_refs,
        rows=evidence.rows,
        orden=evidence.regimen_snapshot.orden.activities,
        agricultural_authority=evidence.regimen_snapshot.orden.agricultural_authority,
        applicable=not evidence.scope_decision.is_not_claimed,
        calculation_result=evidence.calculation_result,
        censo_iae_epigraphs=frozenset(
            activity.iae_epigrafe
            for activity in evidence.rows.activities
            if isinstance(activity, ActividadNoAgricolaSimplificado)
        ),
    )
    if block.max_rows is not None and any(row.record > block.max_rows for row in projected):
        raise RegistryValidationError("saved projection exceeds the declared form record capacity")
    return True, tuple(
        ModeloFormRepeatingRow(index=row.record, values=tuple(field.value for field in row.fields)) for row in projected
    )
