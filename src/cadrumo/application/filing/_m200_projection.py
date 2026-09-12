"""Project modelo 200's repeated party, holding and establishment rows.

Modelo 200's generated layout carries repeated projection-kind fields.
``_projection_plan_for_layout`` built a plan for M303 alone, so every one of them raised
"requires a snapshot-owned render context" and the Impuesto sobre Sociedades return could
not export at all. It failed CLOSED -- refusing rather than emitting wrong bytes -- but it
did not file, and nothing detected that.

One occurrence is emitted per row a family actually carries. A family with no rows emits no
occurrence, which is what AEAT expects of a page a filer has nothing to put on; whether
that absence is admissible is the record's own ``required`` flag, checked by the caller.

Unlike modelo 296's perceptores, whose data already exists as ``Withholding296Observation``,
these rows are genuinely operator-supplied -- the application holds no separate detail
register elsewhere -- so they are read from the typed profile rather than projected from
an existing substrate.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from ...core.filing_projection_ref import FilingProjectionRef
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.queries import RegistryQueryService
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition, ExportRecordDefinition
from ._producer_snapshot_m200 import Modelo200ProfileFacts
from .producer_snapshot import FilingProducerSnapshot
from .projection import FilingProjectionPlan, FilingProjectionValue, FilingRecordRenderContext

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import ValidatedRegistryAuthority

__all__ = ["build_m200_filing_projection_plan"]


@dataclass(frozen=True, slots=True)
class _M200ProjectionCatalogue:
    """Generic projection of the selected M200 row-family declarations."""

    family_by_kind: Mapping[str, str]


# fact-relocation: selected M200 row-family declarations are consumed through RegistryQueryService and the dated mapping fact
def _registry_m200_projection_catalogue(
    effective_date: date,
    *,
    period: str | None = None,
    authority: ValidatedRegistryAuthority | None = None,
) -> _M200ProjectionCatalogue:
    """Resolve row-family routes from the selected registry authority."""
    selected_authority = authority or bundled_authority()
    query_service = RegistryQueryService(selected_authority)
    if period is None:
        query_service.describe_modelo("200")
    else:
        query_service.describe_modelo_for_scope(
            "200",
            filing_year=effective_date.year,
            period=period,
            as_of=effective_date,
        )
    resolved = selected_authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="m200-projection-family-catalogue",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("M200 projection declarations must resolve as a mapping fact")
    prefix = "modelo.200.projection."
    suffix = ".family"
    family_by_kind: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise TypeError("M200 projection declarations must be string-to-string")
        if not entry.key.startswith(prefix) or not entry.key.endswith(suffix):
            continue
        kind = entry.key[len(prefix) : -len(suffix)]
        if not kind.strip() or kind in family_by_kind:
            raise ValueError(f"duplicate or empty M200 projection declaration key {entry.key!r}")
        family_by_kind[kind] = entry.value.strip()
    if not family_by_kind:
        raise ValueError("M200 projection mapping contains no row-family declarations")
    return _M200ProjectionCatalogue(family_by_kind=family_by_kind)


def _m200_address(reference: FilingProjectionRef) -> tuple[int, str] | None:
    """Return the fixed row address carried by a supported M200 reference."""
    slot = getattr(reference, "slot", None)
    field = getattr(reference, "field", None)
    if not isinstance(slot, int) or slot < 1 or field is None:
        return None
    field_name = getattr(field, "value", field)
    if not isinstance(field_name, str) or not field_name:
        return None
    return slot, field_name


def _rows_for(profile: object, kind: str, *, catalogue: _M200ProjectionCatalogue) -> tuple[object, ...]:
    """Return the rows a projection kind draws on, empty when the filing carries none."""
    if not isinstance(profile, Modelo200ProfileFacts):
        return ()
    family = catalogue.family_by_kind.get(kind)
    if family is None or family == "none":
        return ()
    return tuple(getattr(profile.projection_rows, family, ()) or ())


def _m200_projection_refs(record: ExportRecordDefinition) -> tuple[FilingProjectionRef, ...]:
    return tuple(field.projection_ref for field in record.fields if field.projection_ref is not None)


def _m200_record_depth(
    profile: object,
    refs: tuple[FilingProjectionRef, ...],
    *,
    catalogue: _M200ProjectionCatalogue,
) -> int:
    filled = max(
        (len(_rows_for(profile, ref.projection_kind, catalogue=catalogue)) for ref in refs),
        default=0,
    )
    slot_ceiling = max(
        (address[0] for ref in refs if (address := _m200_address(ref)) is not None),
        default=0,
    )
    return min(filled, slot_ceiling)


def _m200_projection_values_for_occurrence(
    *,
    profile: object,
    refs: tuple[FilingProjectionRef, ...],
    record: ExportRecordDefinition,
    occurrence: int,
    catalogue: _M200ProjectionCatalogue,
) -> list[FilingProjectionValue]:
    values: list[FilingProjectionValue] = []
    for ref in refs:
        address = _m200_address(ref)
        if address is None:
            continue
        slot, field_name = address
        family_rows = _rows_for(profile, ref.projection_kind, catalogue=catalogue)
        row = family_rows[slot - 1] if slot <= len(family_rows) else None
        values.append(
            FilingProjectionValue(
                projection_ref=ref,
                record_id=record.id,
                occurrence=occurrence,
                value=getattr(row, field_name, None) if row is not None else None,
            ),
        )
    return values


def _project_m200_record(
    *,
    registry_snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
    profile: object,
    record: ExportRecordDefinition,
    catalogue: _M200ProjectionCatalogue,
) -> tuple[tuple[FilingRecordRenderContext, ...], tuple[FilingProjectionValue, ...]]:
    refs = _m200_projection_refs(record)
    if not refs:
        return (), ()
    depth = _m200_record_depth(profile, refs, catalogue=catalogue)
    contexts: list[FilingRecordRenderContext] = []
    values: list[FilingProjectionValue] = []
    for occurrence in range(1, depth + 1):
        contexts.append(
            FilingRecordRenderContext(
                registry_snapshot=registry_snapshot,
                layout=layout,
                record=record,
                occurrence=occurrence,
            ),
        )
        values.extend(
            _m200_projection_values_for_occurrence(
                profile=profile,
                refs=refs,
                record=record,
                occurrence=occurrence,
                catalogue=catalogue,
            ),
        )
    return tuple(contexts), tuple(values)


def build_m200_filing_projection_plan(
    *,
    registry_snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
    producer_snapshot: FilingProducerSnapshot,
) -> FilingProjectionPlan:
    """Project every modelo 200 repeated-row family from one selected snapshot and layout."""
    profile = producer_snapshot.model_profile
    filing_period = registry_snapshot.filing_period
    effective_date = (
        filing_period.end_date
        if filing_period is not None and filing_period.has_date_span()
        else date(registry_snapshot.filing_year, 12, 31)
    )
    catalogue = _registry_m200_projection_catalogue(
        effective_date,
        period=str(registry_snapshot.period),
    )
    contexts: list[FilingRecordRenderContext] = []
    values: list[FilingProjectionValue] = []

    for record in layout.records:
        record_contexts, record_values = _project_m200_record(
            registry_snapshot=registry_snapshot,
            layout=layout,
            profile=profile,
            record=record,
            catalogue=catalogue,
        )
        contexts.extend(record_contexts)
        values.extend(record_values)
    return FilingProjectionPlan(contexts=tuple(contexts), values=tuple(values))
