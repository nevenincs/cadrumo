"""Anchor registry casillas to official export, dictionary, and design positions."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path

from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.export_layout_format import ExportLayoutFormat
from cadrumo.core.hashing import sha256_file
from cadrumo.domain.calculations.registry.binding_value_contract import BindingValueChannel
from cadrumo.domain.calculations.registry.export_parse import XmlDictionaryEntry, xml_dictionary_entries
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormDesignSource,
)
from cadrumo.domain.calculations.registry.schema_references import SourceReference
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from .generation_constants import (
    _BOX,
    _DICTIONARY_LINE,
    _DIGITS,
    _LABEL_MATCH_FLOOR,
    _LABEL_MATCH_MARGIN,
)
from .generation_models import _Build, _Position
from .official_text import clean_official_text, description_path, node_slug


def _is_box_number(value: str | None) -> bool:
    return value is not None and _DIGITS.fullmatch(value) is not None


def _box_key(value: str) -> str:
    """Compare printed boxes as the design spells them: ``[1]`` is a row ordinal, not box ``00001``."""
    return value


def _casilla_box(casilla_number: str, form_number: str | None) -> str | None:
    if _is_box_number(casilla_number):
        return casilla_number
    return form_number if _is_box_number(form_number) else None


def _manual_scalar_bindings(revision: ModeloRevision) -> dict[str, bool]:
    """Return manual-input bindings no casilla owns, mapped to whether they carry a row set."""
    owned = {
        binding
        for casilla in revision.casillas
        for binding in (casilla.binding, *casilla.alternate_bindings)
        if binding is not None
    }
    return {
        binding.id: binding.value.channel is BindingValueChannel.ROW_SET
        for binding in revision.bindings
        if binding.provider.kind == BindingSourceKind.MANUAL_INPUT and binding.id not in owned
    }


def _fixed_width_records(layouts: Sequence[ExportLayoutDefinition]) -> list[ExportRecordDefinition]:
    records = [
        record for layout in layouts if layout.format is ExportLayoutFormat.FIXED_WIDTH for record in layout.records
    ]
    return sorted(records, key=lambda record: record.order)


def _dictionary_descriptions(payload: bytes) -> dict[str, tuple[str, str]]:
    """Return each dictionary field's box token and description, keyed by field id."""
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        text = payload.decode("cp1252")
    described: dict[str, tuple[str, str]] = {}
    for line in text.splitlines():
        match = _DICTIONARY_LINE.match(line.strip())
        if match is not None:
            described.setdefault(match.group("field").strip(), (match.group("box"), match.group("text")))
    return described


def _dictionary_position_parts(entry: XmlDictionaryEntry) -> tuple[tuple[str, ...], tuple[str, ...]]:
    containers = tuple(segment for segment in entry.path.split("/") if segment and not segment.startswith("@"))[:-1]
    page = containers[:2] if len(containers) >= 2 else containers[:1]
    return containers, page


def _dictionary_position(
    build: _Build,
    entry: XmlDictionaryEntry,
    described: Mapping[str, tuple[str, str]],
) -> _Position:
    containers, page = _dictionary_position_parts(entry)
    box_token, text = described.get(entry.field_id, ("", ""))
    box_digits = re.sub(r"\D", "", box_token)
    position = _Position(
        page_key=node_slug("-".join(page) or "declaracion"),
        page_ref="/".join(page) or None,
        description=clean_official_text(text) or None,
        box=box_digits if box_token.startswith("[") and box_digits else None,
        xml_container=containers,
    )
    if entry.casilla_id is not None:
        position.casilla_ids.append(entry.casilla_id)
    return position


def _dictionary_positions(
    build: _Build,
    layout: ExportLayoutDefinition,
    sources: Mapping[str, SourceReference],
    data_root: Path,
) -> None:
    """Lay out positions from the XML dictionary's line order and element tree."""
    source = sources.get(str(layout.dictionary_source_ref))
    if source is None:
        build.notes.append(f"dictionary source {layout.dictionary_source_ref!r} is not catalogued")
        return
    path = data_root / source.corpus_path
    payload = path.read_bytes()
    entries = xml_dictionary_entries(layout, sources=sources, source_payloads={str(source.id): payload})
    described = _dictionary_descriptions(payload)
    build.used_dictionary = True
    build.design_sources.append(FormDesignSource(source_ref=str(source.id), sha256=sha256_file(path)))
    build.positions.extend(_dictionary_position(build, entry, described) for entry in entries)


def _index_position_anchors(build: _Build) -> None:
    declared = {casilla.id for casilla in build.revision.casillas}
    for index, position in enumerate(build.positions):
        position.casilla_ids = list(dict.fromkeys(position.casilla_ids))
        position.binding_ids = list(dict.fromkeys(position.binding_ids))
        for casilla_id in position.casilla_ids:
            if casilla_id in declared:
                build.anchors[casilla_id].append(index)


def _positions_by_box(build: _Build) -> dict[str, list[int]]:
    by_box: dict[str, list[int]] = defaultdict(list)
    for index, position in enumerate(build.positions):
        if position.box is not None:
            by_box[_box_key(position.box)].append(index)
    return by_box


def _box_anchor_candidates(
    build: _Build, casilla: CasillaDefinition, by_box: Mapping[str, list[int]]
) -> list[int] | None:
    if casilla.id in build.anchors:
        return None
    box = _casilla_box(casilla.number, casilla.form_number)
    printed = [] if box is None else by_box.get(_box_key(box), [])
    if not printed:
        return None
    return [
        index
        for index in printed
        if not build.positions[index].casilla_ids
        and (casilla.segmento is None or build.positions[index].page_ref == casilla.segmento)
    ]


def _anchor_casilla_box(build: _Build, casilla: CasillaDefinition, by_box: Mapping[str, list[int]]) -> None:
    candidates = _box_anchor_candidates(build, casilla, by_box)
    if candidates is None:
        return
    descriptions = {clean_official_text(build.positions[index].description or "") for index in candidates}
    if len(candidates) > 1 and len(descriptions) > 1:
        candidates = _label_tie_break(casilla.label, candidates, build.positions)
    if candidates:
        for index in candidates:
            build.positions[index].casilla_ids.append(casilla.id)
            build.anchors[casilla.id].append(index)
    else:
        build.ambiguous.add(casilla.id)


def _anchor_casillas(build: _Build) -> None:
    """Anchor casillas to official positions, then resolve remaining printed boxes."""
    _index_position_anchors(build)
    by_box = _positions_by_box(build)
    for casilla in sorted(build.revision.casillas, key=lambda item: item.id):
        _anchor_casilla_box(build, casilla, by_box)


def _words(text: str) -> frozenset[str]:
    folded = unicodedata.normalize("NFKD", _BOX.sub(" ", text)).encode("ascii", "ignore").decode("ascii").lower()
    return frozenset(word for word in re.sub(r"[^a-z0-9]+", " ", folded).split() if len(word) > 2)


def _similarity(left: frozenset[str], right: frozenset[str]) -> float:
    return len(left & right) / len(left | right) if left and right else 0.0


def _label_tie_break(label: str, candidates: Sequence[int], positions: Sequence[_Position]) -> list[int]:
    """Keep the one candidate row whose own words clearly match the casilla's official label.

    A casilla's Spanish label and a design description state the same field
    in the same heading-path shape, so both whole texts and both final
    segments are compared. A candidate wins only when its best overlap is at
    least one half and beats every other candidate by a clear margin;
    otherwise the anchor stays ambiguous for a reviewer.
    """
    label_path = description_path(label)
    whole, own = _words(label), _words(label_path.column or "")
    scored = sorted(
        (
            max(
                _similarity(whole, _words(positions[index].description or "")),
                _similarity(own, _words(description_path(positions[index].description).column or "")),
            ),
            index,
        )
        for index in candidates
    )
    scored.reverse()
    if not scored or scored[0][0] < _LABEL_MATCH_FLOOR:
        return []
    if len(scored) > 1 and scored[0][0] - scored[1][0] < _LABEL_MATCH_MARGIN:
        return []
    return [scored[0][1]]


def _last_record_position(build: _Build, record: ExportRecordDefinition) -> int | None:
    return max(
        (index for index, position in enumerate(build.positions) if record.id in position.records),
        default=None,
    )


def _append_row_field_positions(
    build: _Build,
    record: ExportRecordDefinition,
    members: Sequence[str],
    last: int | None,
) -> None:
    page_key = node_slug(record.id) if last is None else build.positions[last].page_key
    page_ref = record.id if last is None else build.positions[last].page_ref
    insert_at = len(build.positions) if last is None else last + 1
    for offset, casilla_id in enumerate(dict.fromkeys(members)):
        position = _Position(page_key=page_key, page_ref=page_ref, description=None, box=None)
        position.records[record.id] = record
        position.casilla_ids.append(casilla_id)
        build.positions.insert(insert_at + offset, position)


def _anchor_one_row_fields(build: _Build, record: ExportRecordDefinition) -> None:
    members = [casilla_id for casilla_id in record.row_field_casilla_ids.values() if casilla_id not in build.anchors]
    if not members or record.repeat is None:
        return
    _append_row_field_positions(build, record, tuple(dict.fromkeys(members)), _last_record_position(build, record))


def _anchor_row_fields(build: _Build, records: Sequence[ExportRecordDefinition]) -> None:
    """Anchor casillas a repeating record projects per row, after that record's own positions."""
    for record in records:
        _anchor_one_row_fields(build, record)


def _binding_primary(build: _Build) -> dict[str, int]:
    """Return the first position of each binding input, which is the one that shows it."""
    found: dict[str, int] = {}
    for index, position in enumerate(build.positions):
        for binding_id in position.binding_ids:
            found.setdefault(binding_id, index)
    return found
