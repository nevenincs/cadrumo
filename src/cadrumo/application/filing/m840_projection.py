"""Project Modelo 840's premises onto the sheets of its Anexo.

The DR840 Anexo prints a fixed number of premises slots on one sheet, numbers its sheets
on the form ("Hoja") and marks a further one "C (Compl.)". So premises fill the slots of
the first sheet in order, the next premises open a second sheet, and so on: nothing is
refused or dropped for being one too many. Each sheet closes with partial sums of the
surfaces its own slots carry.

How many slots a sheet holds is read from the layout, the highest slot any premises field
addresses, never restated here. A filing with no premises emits no sheet; whether that is
admissible is the record's own ``required`` flag, checked by the renderer.
"""

from __future__ import annotations

from decimal import Decimal

from ...core.filing_projection_m840 import (
    M840AnexoHojaField,
    M840AnexoHojaProjectionRef,
    M840LocalField,
    M840LocalProjectionRef,
)
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition, ExportRecordDefinition
from .producer_snapshot import FilingProducerSnapshot
from .producer_snapshot_m840 import Modelo840LocalRow, Modelo840ProfileFacts
from .projection import FilingProjectionPlan, FilingProjectionValue, FilingRecordRenderContext

__all__ = ["build_m840_filing_projection_plan"]

#: The premises surface each partial sum adds up, by the design's own label.
_SUMMED: dict[M840AnexoHojaField, M840LocalField] = {
    M840AnexoHojaField.SUMA_PARCIAL_TOTAL: M840LocalField.TOTAL,
    M840AnexoHojaField.SUMA_PARCIAL_RECTIFICADA: M840LocalField.RECTIFICADA,
    M840AnexoHojaField.SUMA_PARCIAL_COMPUTABLE: M840LocalField.COMPUTABLE,
}


def build_m840_filing_projection_plan(
    *,
    registry_snapshot: RegistrySnapshot,
    layout: ExportLayoutDefinition,
    producer_snapshot: FilingProducerSnapshot,
) -> FilingProjectionPlan:
    """Project the stored premises onto as many Anexo sheets as they fill.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
    """
    profile = producer_snapshot.model_profile
    rows = profile.local_rows if isinstance(profile, Modelo840ProfileFacts) else ()
    contexts: list[FilingRecordRenderContext] = []
    values: list[FilingProjectionValue] = []
    for record in layout.records:
        slots = _slot_count(record)
        if slots == 0:
            continue
        for occurrence, start in enumerate(range(0, len(rows), slots), 1):
            sheet = rows[start : start + slots]
            contexts.append(
                FilingRecordRenderContext(
                    registry_snapshot=registry_snapshot, layout=layout, record=record, occurrence=occurrence
                )
            )
            values.extend(_sheet_values(record, occurrence, sheet))
    return FilingProjectionPlan(contexts=tuple(contexts), values=tuple(values))


def _slot_count(record: ExportRecordDefinition) -> int:
    return max(
        (
            field.projection_ref.slot
            for field in record.fields
            if isinstance(field.projection_ref, M840LocalProjectionRef)
        ),
        default=0,
    )


def _sheet_values(
    record: ExportRecordDefinition, occurrence: int, sheet: tuple[Modelo840LocalRow, ...]
) -> tuple[FilingProjectionValue, ...]:
    values: list[FilingProjectionValue] = []
    for field in record.fields:
        ref = field.projection_ref
        if isinstance(ref, M840LocalProjectionRef):
            value = _row_value(sheet[ref.slot - 1], ref.field) if ref.slot <= len(sheet) else None
        elif isinstance(ref, M840AnexoHojaProjectionRef):
            value = _partial_sum(sheet, _SUMMED[ref.field])
        else:
            continue
        values.append(
            FilingProjectionValue(projection_ref=ref, record_id=record.id, occurrence=occurrence, value=value)
        )
    return tuple(values)


def _row_value(row: Modelo840LocalRow, field: M840LocalField) -> str | Decimal | None:
    value: object = getattr(row, field.value)
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return Decimal(value)
    raise TypeError(f"Modelo 840 premises member {field.value!r} is neither text nor a whole number")


def _partial_sum(sheet: tuple[Modelo840LocalRow, ...], field: M840LocalField) -> Decimal | None:
    """Add the sheet's stated surfaces; a sheet stating none of them has no partial sum."""
    stated = [value for row in sheet if (value := _row_value(row, field)) is not None]
    return sum((Decimal(value) for value in stated), Decimal(0)) if stated else None
