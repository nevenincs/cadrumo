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

from collections.abc import Mapping
from datetime import date

from ...core.filing_projection_ref import FilingProjectionRef
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.queries import RegistryQueryService
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition
from .producer_snapshot import FilingProducerSnapshot, Modelo296ProfileFacts
from .projection import FilingProjectionPlan, FilingProjectionValue, FilingRecordRenderContext

__all__ = ["build_m296_filing_projection_plan"]


def _registry_m296_projection_catalogue(
    effective_date: date,
    *,
    period: str | None = None,
) -> Mapping[str, str]:
    """Resolve detail-row collections from the selected registry authority."""
    authority = bundled_authority()
    query_service = RegistryQueryService(authority)
    if period is None:
        query_service.describe_modelo("296", as_of=effective_date)
    else:
        query_service.describe_modelo_for_scope(
            "296",
            filing_year=effective_date.year,
            period=period,
            as_of=effective_date,
        )
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="modelo-296-detail-collection-mapping",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("Modelo 296 detail collections must resolve as a mapping fact")
    prefix = "modelo.296.projection."
    suffix = ".collection"
    collection_by_kind: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise TypeError("Modelo 296 projection declarations must be string-to-string")
        if not entry.key.startswith(prefix) or not entry.key.endswith(suffix):
            continue
        kind = entry.key[len(prefix) : -len(suffix)]
        collection = entry.value.strip()
        if not kind.strip() or not collection or kind in collection_by_kind:
            raise ValueError(f"duplicate or empty Modelo 296 collection declaration {entry.key!r}")
        collection_by_kind[kind] = collection
    if not collection_by_kind:
        raise ValueError("Modelo 296 projection mapping contains no collection declarations")
    return collection_by_kind


def _rows_for(
    profile: object,
    kind: str,
    *,
    collection_by_kind: Mapping[str, str],
) -> tuple[object, ...]:
    """Return the rows a projection kind draws on, empty when the filing carries none."""
    if not isinstance(profile, Modelo296ProfileFacts):
        return ()
    collection = collection_by_kind.get(kind)
    if collection is None:
        return ()
    return tuple(getattr(profile, collection, ()) or ())


def _m296_field_name(reference: FilingProjectionRef) -> str:
    """Return the row-attribute name carried by a registry projection reference."""
    field_name = getattr(reference.field, "value", reference.field)
    if not isinstance(field_name, str) or not field_name:
        raise ValueError("Modelo 296 projection reference has no row field")
    return field_name


def build_m296_filing_projection_plan(
    *,
    registry_snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
    producer_snapshot: FilingProducerSnapshot,
) -> FilingProjectionPlan:
    """Project one record occurrence per row, for every modelo 296 detail family."""
    profile = producer_snapshot.model_profile
    filing_period = registry_snapshot.filing_period
    effective_date = (
        filing_period.end_date
        if filing_period is not None and filing_period.has_date_span()
        else date(registry_snapshot.filing_year, 12, 31)
    )
    collection_by_kind = _registry_m296_projection_catalogue(
        effective_date,
        period=str(registry_snapshot.period),
    )
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
        rows = _rows_for(profile, kinds.pop(), collection_by_kind=collection_by_kind)
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
