"""Project modelo 296's repeated detail rows.

Modelo 296 is the IRNR annual summary of retenciones e ingresos a cuenta, and four of its
five records are lists in AEAT's own design: the Tipo 2 perceptor record and its intereses
hoja are emitted once per payee, and the two valores-negociables anexos are *relaciones*,
one row per pago and one per certificado.

All four were published as single non-repeating records, so each could hold exactly ONE
row. That failure is silent -- the emitted file is structurally valid and simply
under-declares by every row after the first -- and their fields were declared as header
producers that nothing resolved, so even the one row each could hold rendered blank.

Row identity is the render OCCURRENCE, not a slot on the reference. Unlike modelo 200's
party blocks, which AEAT prints a fixed number of times, none of these has a ceiling in the
design: the number of rows is the number of payees, pagos and certificados. That is why
none of the modelo-296 projection references carries a ``slot`` -- one would be a second row
axis always equal to 1, and at worst an invitation to cap the rows at whatever was declared.

A filing with no rows of a family emits no occurrence of that record, which is what AEAT
expects of an anexo a filer has nothing to put on; whether that absence is admissible is the
record's own ``required`` flag, checked by the renderer.
"""

from __future__ import annotations

from ...core.filing_projection_ref import FilingProjectionRef
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition
from .producer_snapshot import FilingProducerSnapshot, Modelo296ProfileFacts
from .projection import FilingProjectionPlan, FilingProjectionValue, FilingRecordRenderContext

__all__ = ["build_m296_filing_projection_plan"]

#: ``projection_kind`` -> the row collection on :class:`Modelo296ProfileFacts` serving it.
_M296_COLLECTION_BY_KIND: dict[str, str] = {
    "m296_perceptor": "perceptor_rows",
    "m296_perceptor_intereses": "perceptor_intereses_rows",
    "m296_anexo_pago": "anexo_pago_rows",
    "m296_anexo_certificado": "anexo_certificado_rows",
}


def _rows_for(profile: object, kind: str) -> tuple[object, ...]:
    """Return the rows a projection kind draws on, empty when the filing carries none."""
    if not isinstance(profile, Modelo296ProfileFacts):
        return ()
    collection = _M296_COLLECTION_BY_KIND.get(kind)
    if collection is None:
        return ()
    return tuple(getattr(profile, collection, ()) or ())


def _m296_field_name(reference: FilingProjectionRef) -> str:
    """Return the row-attribute name carried by a supported M296 reference."""
    match reference.projection_kind:
        case "m296_perceptor" | "m296_perceptor_intereses" | "m296_anexo_pago" | "m296_anexo_certificado":
            return reference.field.value
        case _:
            raise ValueError(f"unsupported modelo 296 projection kind {reference.projection_kind!r}")


def build_m296_filing_projection_plan(
    *,
    registry_snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
    producer_snapshot: FilingProducerSnapshot,
) -> FilingProjectionPlan:
    """Project one record occurrence per row, for every modelo 296 detail family."""
    profile = producer_snapshot.model_profile
    contexts: list[FilingRecordRenderContext] = []
    values: list[FilingProjectionValue] = []

    for record in layout.records:
        refs = tuple(field.projection_ref for field in record.fields if field.projection_ref is not None)
        if not refs:
            continue
        kinds = {ref.projection_kind for ref in refs}
        if len(kinds) != 1:
            # Every modelo 296 record is one family. A record mixing two would make "which
            # collection sets the depth" ambiguous, and silently answering it would be the
            # same class of guess this module exists to remove.
            raise ValueError(f"modelo 296 record {record.id!r} mixes projection kinds {sorted(kinds)}")
        rows = _rows_for(profile, kinds.pop())
        for occurrence, row in enumerate(rows, 1):
            contexts.append(
                FilingRecordRenderContext(
                    registry_snapshot=registry_snapshot,
                    layout=layout,
                    record=record,
                    occurrence=occurrence,
                ),
            )
            values.extend(
                FilingProjectionValue(
                    projection_ref=ref,
                    record_id=record.id,
                    occurrence=occurrence,
                    # The reference's field IS the row attribute -- the row types are generated
                    # from the same enums -- so a missing one is a defect rather than an absent
                    # value, and getattr without a default is what surfaces it.
                    value=getattr(row, _m296_field_name(ref)),
                )
                for ref in refs
            )

    return FilingProjectionPlan(contexts=tuple(contexts), values=tuple(values))
