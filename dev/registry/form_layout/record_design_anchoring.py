"""Match export records to cited record designs and build their official positions."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence

from cadrumo.core.hashing import sha256_file
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportRecordDefinition,
)
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormDesignSource,
)
from cadrumo.domain.calculations.registry.schema_references import SourceReference

from ..record_design_labels import (
    RecordDesignRow,
    RecordDesignUnavailableError,
    read_record_design,
    record_design_sidecars,
)
from .generation_constants import _RECORD_MATCH_FLOOR
from .generation_models import _Build, _Position
from .official_text import description_box, node_slug


def _attach_export_field(
    position: _Position,
    record: ExportRecordDefinition,
    export_field: ExportFieldDefinition,
    manual_bindings: Mapping[str, bool],
) -> None:
    position.records.setdefault(record.id, record)
    if export_field.casilla_id is not None:
        position.casilla_ids.append(export_field.casilla_id)
    elif export_field.binding is not None and manual_bindings.get(export_field.binding) is False:
        position.binding_ids.append(export_field.binding)
    elif export_field.literal is not None and position.literal is None:
        position.literal = export_field.literal
        position.literal_decimals = export_field.decimals


def _match_records(
    records: Sequence[ExportRecordDefinition],
    design: Mapping[str, Mapping[int, RecordDesignRow]],
) -> dict[str, str]:
    """Pair each registry record with the design record whose offsets it matches best."""
    matched: dict[str, str] = {}
    for record in records:
        design_record = _best_design_record(_field_coordinates(record), design)
        if design_record is not None:
            matched[record.id] = design_record
    return matched


def _field_coordinates(record: ExportRecordDefinition) -> list[tuple[int, int | None]]:
    return [(item.offset, item.length) for item in record.fields if item.offset is not None]


def _best_design_record(
    coordinates: Sequence[tuple[int, int | None]],
    design: Mapping[str, Mapping[int, RecordDesignRow]],
) -> str | None:
    if not coordinates:
        return None
    best: tuple[float, str] | None = None
    for design_record, rows in design.items():
        hits = sum(1 for offset, length in coordinates if offset in rows and rows[offset].length in (length, None))
        ratio = hits / len(coordinates)
        if ratio >= _RECORD_MATCH_FLOOR and (best is None or ratio > best[0]):
            best = (ratio, design_record)
    return None if best is None else best[1]


def _design_rows(build: _Build, sources: Mapping[str, SourceReference]) -> dict[str, dict[int, RecordDesignRow]]:
    try:
        sidecars = record_design_sidecars(build.revision.source_refs, sources)
    except RecordDesignUnavailableError as error:
        build.notes.append(f"record design unavailable: {error}")
        return {}
    if not sidecars:
        return {}
    source_ref, sidecar = sidecars[0]
    rows = read_record_design(sidecar)
    design: dict[str, dict[int, RecordDesignRow]] = {}
    for (record, offset), row in rows.items():
        design.setdefault(record, {})[offset] = row
    if design:
        build.used_design = True
        build.design_sources.append(FormDesignSource(source_ref=source_ref, sha256=sha256_file(sidecar)))
    return design


def _field_positions_by_design(
    records: Sequence[ExportRecordDefinition],
    design: Mapping[str, Mapping[int, RecordDesignRow]],
    matched: Mapping[str, str],
) -> tuple[
    dict[tuple[str, int], list[tuple[ExportRecordDefinition, ExportFieldDefinition]]],
    list[tuple[ExportRecordDefinition, ExportFieldDefinition]],
]:
    fields_at: dict[tuple[str, int], list[tuple[ExportRecordDefinition, ExportFieldDefinition]]] = defaultdict(list)
    unmatched: list[tuple[ExportRecordDefinition, ExportFieldDefinition]] = []
    for record in records:
        design_record = matched.get(record.id)
        for export_field in sorted(record.fields, key=lambda item: (item.offset or 0, item.id)):
            if (
                design_record is not None
                and export_field.offset is not None
                and export_field.offset in design[design_record]
            ):
                fields_at[(design_record, int(export_field.offset))].append((record, export_field))
            else:
                unmatched.append((record, export_field))
    return fields_at, unmatched


def _append_design_positions(
    build: _Build,
    design: Mapping[str, Mapping[int, RecordDesignRow]],
    fields_at: Mapping[tuple[str, int], Sequence[tuple[ExportRecordDefinition, ExportFieldDefinition]]],
    manual_bindings: Mapping[str, bool],
) -> None:
    for design_record, rows in design.items():
        page_key = node_slug(design_record)
        for offset, row in rows.items():
            label = row.label or None
            position = _Position(
                page_key=page_key,
                page_ref=design_record,
                description=label,
                box=None if label is None else description_box(label),
            )
            for record, export_field in fields_at.get((design_record, offset), ()):
                _attach_export_field(position, record, export_field, manual_bindings)
            build.positions.append(position)


def _append_unmatched_positions(
    build: _Build,
    unmatched: Sequence[tuple[ExportRecordDefinition, ExportFieldDefinition]],
    manual_bindings: Mapping[str, bool],
) -> None:
    for record, export_field in unmatched:
        position = _Position(page_key=node_slug(record.id), page_ref=record.id, description=None, box=None)
        _attach_export_field(position, record, export_field, manual_bindings)
        if position.casilla_ids or position.binding_ids:
            build.positions.append(position)


def _record_design_positions(
    build: _Build,
    sources: Mapping[str, SourceReference],
    records: Sequence[ExportRecordDefinition],
    manual_bindings: Mapping[str, bool],
) -> None:
    """Lay out positions from the cited record design, joining export fields by record and offset."""
    design = _design_rows(build, sources)
    matched = _match_records(records, design)
    fields_at, unmatched = _field_positions_by_design(records, design, matched)
    _append_design_positions(build, design, fields_at, manual_bindings)
    _append_unmatched_positions(build, unmatched, manual_bindings)
