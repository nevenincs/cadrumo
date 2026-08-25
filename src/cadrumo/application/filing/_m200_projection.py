"""Project modelo 200's repeated party, holding and establishment rows.

Modelo 200's generated layout carries 578 projection-kind fields across fourteen kinds.
``_projection_plan_for_layout`` built a plan for M303 alone, so every one of them raised
"requires a snapshot-owned render context" and the Impuesto sobre Sociedades return could
not export at all. It failed CLOSED -- refusing rather than emitting wrong bytes -- but it
did not file, and nothing detected that.

One occurrence is emitted per row a family actually carries. A family with no rows emits no
occurrence, which is what AEAT expects of a page a filer has nothing to put on; whether
that absence is admissible is the record's own ``required`` flag, checked by the caller.

Unlike modelo 296's perceptores, whose data already exists as ``Withholding296Observation``,
these rows are genuinely operator-supplied -- the application holds no administrador,
representante or participada register anywhere else -- so they are read from the typed
profile rather than projected from an existing substrate.
"""

from __future__ import annotations

from ...core import FilingProjectionRef
from ...domain.calculations.registry import ExportLayoutDefinition, RegistrySnapshot
from ._producer_snapshot import FilingProducerSnapshot, Modelo200ProfileFacts
from ._projection import FilingProjectionPlan, FilingProjectionValue, FilingRecordRenderContext

__all__ = ["build_m200_filing_projection_plan"]

#: ``projection_kind`` -> the row family on :class:`Modelo200ProjectionRows` that serves it.
_M200_FAMILY_BY_KIND: dict[str, str] = {
    "m200_administrador": "administrador",
    "m200_entidad_menor_dependiente": "entidad_menor_dependiente",
    "m200_entidad_participada": "entidad_participada",
    "m200_establecimiento_permanente": "establecimiento_permanente",
    "m200_incn_grupo_sociedad": "incn_grupo_sociedad",
    "m200_operacion_reestructuracion": "operacion_reestructuracion",
    "m200_participacion_directa": "participacion_directa",
    "m200_participacion_socio": "participacion_socio",
    "m200_participe_aie_ute": "participe_aie_ute",
    "m200_representante_legal": "representante_legal",
    "m200_secretario_consejo": "secretario_consejo",
    "m200_socio_sicav_disolucion": "socio_sicav_disolucion",
    "m200_transparencia_fiscal_internacional": "transparencia_fiscal_internacional",
}


def _m200_address(reference: FilingProjectionRef) -> tuple[int, str] | None:
    """Return the fixed row address carried by a supported M200 reference."""
    match reference.projection_kind:
        case (
            "m200_administrador"
            | "m200_entidad_menor_dependiente"
            | "m200_entidad_participada"
            | "m200_establecimiento_permanente"
            | "m200_incn_grupo_sociedad"
            | "m200_operacion_reestructuracion"
            | "m200_participacion_directa"
            | "m200_participacion_socio"
            | "m200_participe_aie_ute"
            | "m200_representante_legal"
            | "m200_secretario_consejo"
            | "m200_socio_sicav_disolucion"
            | "m200_transparencia_fiscal_internacional"
        ):
            return reference.slot, str(reference.field)
        case _:
            return None


def _rows_for(profile: object, kind: str) -> tuple[object, ...]:
    """Return the rows a projection kind draws on, empty when the filing carries none."""
    if not isinstance(profile, Modelo200ProfileFacts):
        return ()
    family = _M200_FAMILY_BY_KIND.get(kind)
    if family is None:
        return ()
    return tuple(getattr(profile.projection_rows, family, ()) or ())


def build_m200_filing_projection_plan(
    *,
    registry_snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
    producer_snapshot: FilingProducerSnapshot,
) -> FilingProjectionPlan:
    """Project every modelo 200 repeated-row family from one selected snapshot and layout."""
    profile = producer_snapshot.model_profile
    contexts: list[FilingRecordRenderContext] = []
    values: list[FilingProjectionValue] = []

    for record in layout.records:
        refs = tuple(field.projection_ref for field in record.fields if field.projection_ref is not None)
        if not refs:
            continue
        # A record's occurrence count is the deepest slot any of its families actually
        # fills -- never the layout's slot ceiling, which is what the FORM allows rather
        # than what this filer has.
        filled = 0
        for ref in refs:
            filled = max(filled, len(_rows_for(profile, ref.projection_kind)))
        depth = min(
            filled,
            max((address[0] for ref in refs if (address := _m200_address(ref)) is not None), default=0),
        )
        for occurrence in range(1, depth + 1):
            contexts.append(
                FilingRecordRenderContext(
                    registry_snapshot=registry_snapshot,
                    layout=layout,
                    record=record,
                    occurrence=occurrence,
                ),
            )
            for ref in refs:
                address = _m200_address(ref)
                if address is None:
                    continue
                slot, field_name = address
                family_rows = _rows_for(profile, ref.projection_kind)
                row = family_rows[slot - 1] if slot <= len(family_rows) else None
                values.append(
                    FilingProjectionValue(
                        projection_ref=ref,
                        record_id=record.id,
                        occurrence=occurrence,
                        value=getattr(row, field_name, None) if row is not None else None,
                    ),
                )
    return FilingProjectionPlan(contexts=tuple(contexts), values=tuple(values))
