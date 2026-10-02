"""The modelo-independent form layout generator: one seed ladder for every revision.

The generator reads official anchors in a fixed order and declares a
:class:`~cadrumo.domain.calculations.registry.schema_form_layouts.FormLayoutDefinition`
for one revision. It has no per-modelo code; every decision is taken from the
revision's own typed declarations and the official sources it cites.

The ladder, per casilla:

1. an export field of the revision's derived layout (record order, offset),
   joined to the record-design row at the same record and offset;
2. for an XML-dictionary revision, the dictionary line that names the casilla;
3. the design row whose description prints the casilla's box ``[NN]`` -- used
   only when exactly one row prints it and no other casilla already sits there,
   otherwise the casilla is declared unplaced as ambiguous;
4. for a revision with no design, export record or dictionary line of its own,
   the declared predecessor's position of the same continuing box, kept only
   where a form the revision cites prints that page's label, the box and its
   apartado on one page (:mod:`.predecessor_layout`);
5. the casilla's numeric box number alone, placed on a numbered-boxes page;
6. otherwise a working figure when the casilla is not operator-entered, or
   unplaced without an official anchor when it is.

Pages are the design's records (or the dictionary's element groups); sections
are the contiguous runs of rows sharing a heading path; grids are rows whose
columns match the shared column vocabulary or repeat on the page. Manual-input
bindings no casilla owns become binding inputs; row-set sources and repeating
export records become repeating groups, never flattened rows.

Where a design names a part in no form the ladder can read, a reviewer's quote
of the official words (``official_headings.toml``) heads it, after the quote is
verified on the cited line of a source the revision cites.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.export_layout_format import ExportLayoutFormat
from cadrumo.domain.calculations.registry.binding_value_contract import BindingValueChannel
from cadrumo.domain.calculations.registry.export import derive_export_layouts_from_bindings
from cadrumo.domain.calculations.registry.export_parse import xml_dictionary_entries
from cadrumo.domain.calculations.registry.form_layout_integrity import form_layout_source_digest
from cadrumo.domain.calculations.registry.revision_contracts import DeclaredPredecessor
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
)
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FORM_LAYOUT_GENERATOR_VERSION,
    FormAliasPosition,
    FormBindingInputsBlock,
    FormBlockDefinition,
    FormCell,
    FormCellKind,
    FormDesignSource,
    FormFieldBlock,
    FormGridBlock,
    FormGridColumn,
    FormGridRow,
    FormLayoutDefinition,
    FormLayoutReviewState,
    FormLayoutSeedSource,
    FormPageCondition,
    FormPageDefinition,
    FormPlacementDefinition,
    FormPlacementKind,
    FormRepeatingColumn,
    FormRepeatingGroupBlock,
    FormRepeatingRowSource,
    FormSectionDefinition,
    FormUnplacedReason,
)
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.schema_references import SourceReference

from ..record_design_labels import (
    RecordDesignRow,
    RecordDesignUnavailableError,
    read_record_design,
    record_design_sidecars,
)
from .column_vocabulary import SHARED_COLUMN_HEADING_KEY_PREFIX, SHARED_COLUMN_KEYS, shared_column_key
from .official_form_pages import OfficialFormUnavailableError
from .official_headings import OfficialHeadingRefusedError, QuotedHeading, read_official_headings, verify_quote
from .official_text import clean_official_text, description_box, description_path, node_slug
from .predecessor_layout import ContinuedLayout, PredecessorLayout, continue_predecessor_layout

__all__ = [
    "GENERATED_LAYOUT_ID",
    "LayoutGeneration",
    "generate_modelo_layouts",
    "generate_revision_layout",
]

GENERATED_LAYOUT_ID: Final[str] = "form-layout"
_NUMBERED_PAGE: Final[str] = "numbered-boxes"
_INPUTS_PAGE: Final[str] = "other-inputs"
_GENERAL_SECTION: Final[str] = "general"
_RECORD_MATCH_FLOOR: Final[float] = 0.6
_LABEL_MATCH_FLOOR: Final[float] = 0.5
_LABEL_MATCH_MARGIN: Final[float] = 0.2
_DICTIONARY_LINE: Final = re.compile(
    r"^(?P<field>[^=]+)=\[(?P<path>[^\]]*)\]\[[^\]]*\]\[(?P<box>[^\]]*)\]\[(?P<text>.*)\]\s*$"
)
_DIGITS: Final = re.compile(r"^\d{1,16}$")
_BOX: Final = re.compile(r"\[\s*\d{1,5}\s*\]")


@dataclass(frozen=True, slots=True)
class LayoutGeneration:
    """One revision's generation outcome: a layout, or the reason there is none."""

    modelo_id: str
    revision_id: str
    layout: FormLayoutDefinition | None
    failure: str | None = None
    notes: tuple[str, ...] = ()


@dataclass(slots=True)
class _Position:
    """One official position in form order: a design row or dictionary line."""

    page_key: str
    page_ref: str | None
    description: str | None
    box: str | None
    records: dict[str, ExportRecordDefinition] = field(default_factory=dict)
    casilla_ids: list[str] = field(default_factory=list)
    binding_ids: list[str] = field(default_factory=list)
    literal: str | None = None
    literal_decimals: int | None = None
    xml_container: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class _Item:
    """One thing a section shows: a casilla, a binding input, or a design constant."""

    position: int
    casilla_id: str | None = None
    binding_id: str | None = None
    literal: str | None = None
    literal_decimals: int | None = None


@dataclass(slots=True)
class _Build:
    """Mutable state of one revision's generation."""

    modelo_id: str
    revision: ModeloRevision
    positions: list[_Position] = field(default_factory=list)
    anchors: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    ambiguous: set[str] = field(default_factory=set)
    binding_primary: dict[str, int] = field(default_factory=dict)
    design_sources: list[FormDesignSource] = field(default_factory=list)
    used_design: bool = False
    used_export: bool = False
    used_dictionary: bool = False
    notes: list[str] = field(default_factory=list)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _match_records(
    records: Sequence[ExportRecordDefinition],
    design: Mapping[str, Mapping[int, RecordDesignRow]],
) -> dict[str, str]:
    """Pair each registry record with the design record whose offsets it matches best."""
    matched: dict[str, str] = {}
    for record in records:
        coordinates = [(item.offset, item.length) for item in record.fields if item.offset is not None]
        if not coordinates:
            continue
        best: tuple[float, str] | None = None
        for design_record, rows in design.items():
            hits = sum(1 for offset, length in coordinates if offset in rows and rows[offset].length in (length, None))
            ratio = hits / len(coordinates)
            if ratio >= _RECORD_MATCH_FLOOR and (best is None or ratio > best[0]):
                best = (ratio, design_record)
        if best is not None:
            matched[record.id] = best[1]
    return matched


def _record_design_positions(
    build: _Build,
    sources: Mapping[str, SourceReference],
    records: Sequence[ExportRecordDefinition],
    manual_bindings: Mapping[str, bool],
) -> None:
    """Lay out positions from the cited record design, joining export fields by record and offset."""
    try:
        sidecars = record_design_sidecars(build.revision.source_refs, sources)
    except RecordDesignUnavailableError as error:
        build.notes.append(f"record design unavailable: {error}")
        sidecars = ()
    design: dict[str, dict[int, RecordDesignRow]] = {}
    if sidecars:
        source_ref, sidecar = sidecars[0]
        rows = read_record_design(sidecar)
        for (record, offset), row in rows.items():
            design.setdefault(record, {})[offset] = row
        if design:
            build.used_design = True
            build.design_sources.append(FormDesignSource(source_ref=source_ref, sha256=_sha256_file(sidecar)))
    matched = _match_records(records, design)
    fields_at: dict[tuple[str, int], list[tuple[ExportRecordDefinition, ExportFieldDefinition]]] = defaultdict(list)
    unmatched: list[tuple[ExportRecordDefinition, ExportFieldDefinition]] = []
    for record in records:
        design_record = matched.get(record.id)
        for export_field in sorted(record.fields, key=lambda item: (item.offset or 0, item.id)):
            if design_record is not None and export_field.offset in design[design_record]:
                fields_at[(design_record, int(export_field.offset))].append((record, export_field))
            else:
                unmatched.append((record, export_field))
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
    for record, export_field in unmatched:
        position = _Position(page_key=node_slug(record.id), page_ref=record.id, description=None, box=None)
        _attach_export_field(position, record, export_field, manual_bindings)
        if position.casilla_ids or position.binding_ids:
            build.positions.append(position)


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
    build.design_sources.append(FormDesignSource(source_ref=str(source.id), sha256=_sha256_file(path)))
    for entry in entries:
        containers = tuple(segment for segment in entry.path.split("/") if segment and not segment.startswith("@"))[:-1]
        page = containers[:2] if len(containers) >= 2 else containers[:1]
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
        build.positions.append(position)


def _anchor_casillas(build: _Build) -> None:
    """Anchor casillas to positions: export or dictionary first, then a printed box.

    A printed box anchors a casilla when exactly one free design row prints it,
    within the casilla's own design record when it declares a ``segmento``. A
    box the design prints on several rows with the same description is one
    field restated, so the first row is the position and the rest are aliases;
    rows that print it with different descriptions leave the casilla ambiguous.
    """
    declared = {casilla.id for casilla in build.revision.casillas}
    for index, position in enumerate(build.positions):
        position.casilla_ids = list(dict.fromkeys(position.casilla_ids))
        position.binding_ids = list(dict.fromkeys(position.binding_ids))
        for casilla_id in position.casilla_ids:
            if casilla_id in declared:
                build.anchors[casilla_id].append(index)
    by_box: dict[str, list[int]] = defaultdict(list)
    for index, position in enumerate(build.positions):
        if position.box is not None:
            by_box[_box_key(position.box)].append(index)
    for casilla in sorted(build.revision.casillas, key=lambda item: item.id):
        if casilla.id in build.anchors:
            continue
        box = _casilla_box(casilla.number, casilla.form_number)
        printed = [] if box is None else by_box.get(_box_key(box), [])
        if not printed:
            continue
        candidates = [
            index
            for index in printed
            if not build.positions[index].casilla_ids
            and (casilla.segmento is None or build.positions[index].page_ref == casilla.segmento)
        ]
        descriptions = {clean_official_text(build.positions[index].description or "") for index in candidates}
        if len(candidates) > 1 and len(descriptions) > 1:
            candidates = _label_tie_break(casilla.label, candidates, build.positions)
        if candidates:
            for index in candidates:
                build.positions[index].casilla_ids.append(casilla.id)
                build.anchors[casilla.id].append(index)
        else:
            build.ambiguous.add(casilla.id)


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


def _anchor_row_fields(build: _Build, records: Sequence[ExportRecordDefinition]) -> None:
    """Anchor casillas a repeating record projects per row, after that record's own positions."""
    for record in records:
        members = [
            casilla_id for casilla_id in record.row_field_casilla_ids.values() if casilla_id not in build.anchors
        ]
        if not members or record.repeat is None:
            continue
        last = max(
            (index for index, position in enumerate(build.positions) if record.id in position.records),
            default=None,
        )
        page_key = node_slug(record.id) if last is None else build.positions[last].page_key
        page_ref = record.id if last is None else build.positions[last].page_ref
        insert_at = len(build.positions) if last is None else last + 1
        for offset, casilla_id in enumerate(dict.fromkeys(members)):
            position = _Position(page_key=page_key, page_ref=page_ref, description=None, box=None)
            position.records[record.id] = record
            position.casilla_ids.append(casilla_id)
            build.positions.insert(insert_at + offset, position)


def _binding_primary(build: _Build) -> dict[str, int]:
    """Return the first position of each binding input, which is the one that shows it."""
    found: dict[str, int] = {}
    for index, position in enumerate(build.positions):
        for binding_id in position.binding_ids:
            found.setdefault(binding_id, index)
    return found


@dataclass(slots=True)
class _SectionDraft:
    key: tuple[str, ...]
    heading: str | None
    positions: list[int] = field(default_factory=list)
    items: list[_Item] = field(default_factory=list)


def _section_key(position: _Position) -> tuple[str, ...]:
    if position.xml_container is not None:
        return position.xml_container[2:3]
    return description_path(position.description).section


def _items_for(build: _Build, index: int, primary: Mapping[str, int]) -> list[_Item]:
    position = build.positions[index]
    items = [
        _Item(
            position=index, casilla_id=casilla_id, literal=position.literal, literal_decimals=position.literal_decimals
        )
        for casilla_id in position.casilla_ids
        if primary.get(casilla_id) == index
    ]
    items.extend(
        _Item(position=index, binding_id=binding_id)
        for binding_id in position.binding_ids
        if build.binding_primary.get(binding_id) == index
    )
    if not items and position.literal is not None and position.box is not None:
        items.append(_Item(position=index, literal=position.literal, literal_decimals=position.literal_decimals))
    return items


def _page_sections(build: _Build, indexes: Sequence[int], primary: Mapping[str, int]) -> list[_SectionDraft]:
    """Group a page's positions into contiguous runs sharing a heading path."""
    aliased = {index for anchors in build.anchors.values() for index in anchors[1:]}
    drafts: list[_SectionDraft] = []
    for index in indexes:
        items = _items_for(build, index, primary)
        if not items and index not in aliased:
            continue
        key = _section_key(build.positions[index])
        if not drafts or drafts[-1].key != key:
            heading = " - ".join(key) if key and build.positions[index].xml_container is None else None
            drafts.append(_SectionDraft(key=key, heading=heading))
        drafts[-1].positions.append(index)
        drafts[-1].items.extend(items)
    return drafts


@dataclass(slots=True)
class _RowDraft:
    stem: str
    columns: list[str]
    items: list[_Item]


def _row_drafts(build: _Build, items: Sequence[_Item]) -> list[_RowDraft | _Item]:
    """Split a section's items into row candidates and lone items."""
    out: list[_RowDraft | _Item] = []
    current: _RowDraft | None = None
    for item in items:
        position = build.positions[item.position]
        path = description_path(position.description) if position.xml_container is None else description_path(None)
        if path.stem is None or path.column is None:
            current = None
            out.append(item)
            continue
        if current is None or current.stem != path.stem or path.column in current.columns:
            current = _RowDraft(stem=path.stem, columns=[], items=[])
            out.append(current)
        current.columns.append(path.column)
        current.items.append(item)
    return out


def _signature(columns: Sequence[str]) -> tuple[str, ...]:
    return tuple(shared_column_key(column) or node_slug(column) for column in columns)


def _is_subsequence(candidate: Sequence[str], whole: Sequence[str]) -> bool:
    iterator = iter(whole)
    return all(any(token == value for value in iterator) for token in candidate)


def _heading_key(modelo_id: str, *nodes: str) -> str:
    """Return a per-modelo heading key.

    Section and row keys are named by the official heading's own words rather
    than by position, so the same heading shares one translation across pages
    and editions, and a key never changes meaning when an edition reorders.
    """
    return ".".join(("modelo", "schema", modelo_id, "form", *nodes, "heading"))


def _column_heading_key(modelo_id: str, key: str) -> str:
    if key in SHARED_COLUMN_KEYS:
        return f"{SHARED_COLUMN_HEADING_KEY_PREFIX}.{key}"
    return _heading_key(modelo_id, "column", key)


def _unique(base: str, used: set[str]) -> str:
    candidate, counter = base, 2
    while candidate in used:
        candidate = f"{base}-{counter}"
        counter += 1
    used.add(candidate)
    return candidate


def _cell(item: _Item) -> FormCell:
    if item.casilla_id is not None and item.literal is not None:
        return FormCell(
            kind=FormCellKind.DESIGN_CONSTANT,
            casilla_id=item.casilla_id,
            literal=item.literal,
            literal_decimals=item.literal_decimals,
        )
    if item.casilla_id is not None:
        return FormCell(kind=FormCellKind.CASILLA, casilla_id=item.casilla_id)
    if item.binding_id is not None:
        return FormCell(kind=FormCellKind.BINDING_INPUT, binding_id=item.binding_id)
    return FormCell(
        kind=FormCellKind.DESIGN_CONSTANT, literal=str(item.literal), literal_decimals=item.literal_decimals
    )


def _field_block(block_id: str, item: _Item) -> FormFieldBlock | None:
    if item.casilla_id is not None:
        return FormFieldBlock(
            id=block_id,
            casilla_id=item.casilla_id,
            design_constant=item.literal,
            literal_decimals=item.literal_decimals,
        )
    if item.binding_id is not None:
        return FormFieldBlock(id=block_id, binding_id=item.binding_id)
    return None


def _section_blocks(
    build: _Build,
    draft: _SectionDraft,
    *,
    page_signatures: Counter[tuple[str, ...]],
    repeating: Mapping[str, ExportRecordDefinition],
    emitted_repeating: set[str],
) -> list[FormBlockDefinition]:
    blocks: list[FormBlockDefinition] = []
    block_ids: set[str] = set()
    plain: list[_Item] = []
    for item in draft.items:
        position = build.positions[item.position]
        record = next((repeating[record_id] for record_id in position.records if record_id in repeating), None)
        if record is None:
            plain.append(item)
            continue
        if record.id in emitted_repeating:
            continue
        emitted_repeating.add(record.id)
        blocks.append(_repeating_record_block(build, record, _unique(node_slug(record.id), block_ids)))
    grid: tuple[list[str], list[tuple[_RowDraft, tuple[str, ...]]]] | None = None

    def flush_grid() -> None:
        nonlocal grid
        if grid is None:
            return
        column_keys, rows = grid
        blocks.append(_grid_block(build, column_keys, rows, _unique("grid", block_ids)))
        grid = None

    for entry in _row_drafts(build, plain):
        if isinstance(entry, _RowDraft):
            signature = _signature(entry.columns)
            shared = all(key in SHARED_COLUMN_KEYS for key in signature)
            if len(signature) >= 2 and (shared or page_signatures[signature] >= 2):
                if grid is not None and _is_subsequence(signature, grid[0]):
                    grid[1].append((entry, signature))
                else:
                    flush_grid()
                    grid = (list(signature), [(entry, signature)])
                continue
            flush_grid()
            for item in entry.items:
                block = _field_block(_unique("field", block_ids), item)
                if block is not None:
                    blocks.append(block)
            continue
        flush_grid()
        block = _field_block(_unique("field", block_ids), entry)
        if block is not None:
            blocks.append(block)
    flush_grid()
    return blocks


def _grid_block(
    build: _Build,
    column_keys: Sequence[str],
    rows: Sequence[tuple[_RowDraft, tuple[str, ...]]],
    block_id: str,
) -> FormGridBlock:
    first_row = rows[0][0]
    columns = tuple(
        FormGridColumn(
            key=key,
            heading_key=_column_heading_key(build.modelo_id, key),
            official_heading=clean_official_text(text) or None,
        )
        for key, text in zip(column_keys, first_row.columns, strict=True)
    )
    used_rows: set[str] = set()
    grid_rows: list[FormGridRow] = []
    for row, signature in rows:
        by_key = dict(zip(signature, row.items, strict=True))
        row_key = _unique(node_slug(row.stem), used_rows)
        grid_rows.append(
            FormGridRow(
                key=row_key,
                heading_key=_heading_key(build.modelo_id, "row", node_slug(row.stem)),
                official_heading=row.stem,
                cells=tuple(
                    _cell(by_key[key]) if key in by_key else FormCell(kind=FormCellKind.BLANK) for key in column_keys
                ),
            )
        )
    return FormGridBlock(id=block_id, columns=columns, rows=tuple(grid_rows))


def _repeating_record_block(build: _Build, record: ExportRecordDefinition, block_id: str) -> FormRepeatingGroupBlock:
    columns: list[FormRepeatingColumn] = []
    used: set[str] = set()
    primary = {casilla_id: anchors[0] for casilla_id, anchors in build.anchors.items()}
    for index, position in enumerate(build.positions):
        if record.id not in position.records:
            continue
        for casilla_id in position.casilla_ids:
            if primary.get(casilla_id) != index:
                continue
            text = description_path(position.description).column
            key = _unique(shared_column_key(text or "") or node_slug(text or casilla_id), used)
            columns.append(
                FormRepeatingColumn(
                    key=key,
                    heading_key=_column_heading_key(build.modelo_id, key),
                    official_heading=text,
                    casilla_id=casilla_id,
                )
            )
    return FormRepeatingGroupBlock(
        id=block_id,
        row_source=FormRepeatingRowSource.EXPORT_RECORD,
        export_record_id=record.id,
        columns=tuple(columns),
    )


def _page_condition(records: Iterable[ExportRecordDefinition]) -> tuple[FormPageCondition, str | None]:
    """Return the page condition the page's export records structurally declare."""
    listed = list(records)
    gated = sorted({record.requires_positive_casilla_id for record in listed if record.requires_positive_casilla_id})
    if len(gated) == 1 and all(record.requires_positive_casilla_id for record in listed):
        return FormPageCondition.REQUIRES_POSITIVE_CASILLA, gated[0]
    if listed and all(not record.required for record in listed):
        return FormPageCondition.OPTIONAL_RECORD, None
    return FormPageCondition.ALWAYS, None


def _numbered_casillas(build: _Build, primary: Mapping[str, int]) -> list[str]:
    """Return casillas with a numeric box and no official position, in box order."""
    remaining = [
        casilla
        for casilla in build.revision.casillas
        if casilla.id not in primary
        and casilla.id not in build.ambiguous
        and _casilla_box(casilla.number, casilla.form_number) is not None
    ]
    remaining.sort(key=lambda casilla: (int(str(_casilla_box(casilla.number, casilla.form_number))), casilla.id))
    return [casilla.id for casilla in remaining]


def _build_pages(
    build: _Build,
    manual_bindings: Mapping[str, bool],
    repeating: Mapping[str, ExportRecordDefinition],
    continued: ContinuedLayout | None,
) -> tuple[list[FormPageDefinition], dict[int, tuple[str, str]], set[str], set[str]]:
    primary = {casilla_id: anchors[0] for casilla_id, anchors in build.anchors.items()}
    pages_by_key: dict[str, list[int]] = {}
    refs: dict[str, str | None] = {}
    for index, position in enumerate(build.positions):
        pages_by_key.setdefault(position.page_key, []).append(index)
        refs.setdefault(position.page_key, position.page_ref)
    signatures: Counter[tuple[str, ...]] = Counter()
    pages: list[FormPageDefinition] = [] if continued is None else list(continued.pages)
    section_of: dict[int, tuple[str, str]] = {}
    placed_bindings: set[str] = set()
    shown: set[str] = (
        set()
        if continued is None
        else _block_casillas(block for page in continued.pages for section in page.sections for block in section.blocks)
    )
    emitted_repeating: set[str] = set()
    used_pages: set[str] = {page.id for page in pages}
    for page_key, indexes in pages_by_key.items():
        drafts = _page_sections(build, indexes, primary)
        signatures = Counter(
            _signature(entry.columns)
            for draft in drafts
            for entry in _row_drafts(build, draft.items)
            if isinstance(entry, _RowDraft)
        )
        page_id = _unique(page_key, used_pages)
        sections: list[FormSectionDefinition] = []
        used_sections: set[str] = set()
        for draft in drafts:
            section_id = _unique(node_slug(draft.heading) if draft.heading else _section_slug(draft.key), used_sections)
            blocks = _section_blocks(
                build,
                draft,
                page_signatures=signatures,
                repeating=repeating,
                emitted_repeating=emitted_repeating,
            )
            if not blocks:
                used_sections.discard(section_id)
                continue
            for index in draft.positions:
                section_of[index] = (page_id, section_id)
            shown.update(_block_casillas(blocks))
            placed_bindings.update(_block_bindings(blocks))
            sections.append(
                FormSectionDefinition(
                    id=section_id,
                    heading_key=_heading_key(
                        build.modelo_id, "section", node_slug(draft.heading) if draft.heading else section_id
                    ),
                    official_heading=draft.heading,
                    blocks=tuple(blocks),
                )
            )
        if not sections:
            used_pages.discard(page_id)
            continue
        page_records = {
            record_id: record for index in indexes for record_id, record in build.positions[index].records.items()
        }
        condition, gate = _page_condition(page_records.values())
        pages.append(
            FormPageDefinition(
                id=page_id,
                official_ref=refs[page_key],
                heading_key=_heading_key(build.modelo_id, "page", page_id),
                condition=condition,
                condition_casilla_id=gate,
                sections=tuple(sections),
            )
        )
    placed_bindings.update(
        binding_id
        for position in build.positions
        if any(record_id in repeating for record_id in position.records)
        for binding_id in position.binding_ids
    )
    numbered = [casilla_id for casilla_id in _numbered_casillas(build, primary) if casilla_id not in shown]
    if numbered:
        pages.append(_numbered_page(build, _unique(_NUMBERED_PAGE, used_pages), numbered))
        shown.update(numbered)
    inputs_page = _inputs_page(build, _unique(_INPUTS_PAGE, used_pages), manual_bindings, placed_bindings)
    if inputs_page is not None:
        pages.append(inputs_page)
    return pages, section_of, shown, placed_bindings


def _section_slug(key: Sequence[str]) -> str:
    return node_slug("-".join(key)) if key else _GENERAL_SECTION


def _block_casillas(blocks: Iterable[FormBlockDefinition]) -> set[str]:
    found: set[str] = set()
    for block in blocks:
        if isinstance(block, FormFieldBlock) and block.casilla_id is not None:
            found.add(block.casilla_id)
        elif isinstance(block, FormGridBlock):
            found.update(cell.casilla_id for row in block.rows for cell in row.cells if cell.casilla_id is not None)
        elif isinstance(block, FormRepeatingGroupBlock):
            found.update(column.casilla_id for column in block.columns if column.casilla_id is not None)
    return found


def _block_bindings(blocks: Iterable[FormBlockDefinition]) -> set[str]:
    found: set[str] = set()
    for block in blocks:
        if isinstance(block, FormFieldBlock) and block.binding_id is not None:
            found.add(block.binding_id)
        elif isinstance(block, FormGridBlock):
            found.update(cell.binding_id for row in block.rows for cell in row.cells if cell.binding_id is not None)
    return found


def _numbered_page(build: _Build, page_id: str, casilla_ids: Sequence[str]) -> FormPageDefinition:
    """Place casillas known only by their box number, grouped by their registry section's first token."""
    by_id = {casilla.id: casilla for casilla in build.revision.casillas}
    groups: dict[str, list[str]] = {}
    for casilla_id in casilla_ids:
        section = by_id[casilla_id].section
        groups.setdefault(node_slug(section[0]) if section else _GENERAL_SECTION, []).append(casilla_id)
    sections = tuple(
        FormSectionDefinition(
            id=section_id,
            heading_key=_heading_key(build.modelo_id, "section", section_id),
            blocks=tuple(
                FormFieldBlock(id=f"field-{index + 1}", casilla_id=casilla_id)
                for index, casilla_id in enumerate(members)
            ),
        )
        for section_id, members in groups.items()
    )
    return FormPageDefinition(id=page_id, heading_key=_heading_key(build.modelo_id, "page", page_id), sections=sections)


def _inputs_page(
    build: _Build,
    page_id: str,
    manual_bindings: Mapping[str, bool],
    placed: set[str],
) -> FormPageDefinition | None:
    """Declare manual-input bindings no casilla owns and no official position holds."""
    scalar = tuple(
        sorted(binding for binding, row_set in manual_bindings.items() if not row_set and binding not in placed)
    )
    row_sets = sorted(binding for binding, row_set in manual_bindings.items() if row_set)
    blocks: list[FormBlockDefinition] = []
    used: set[str] = {"binding-inputs"}
    if scalar:
        blocks.append(FormBindingInputsBlock(id="binding-inputs", binding_ids=scalar))
    blocks.extend(
        FormRepeatingGroupBlock(
            id=_unique(node_slug(binding), used),
            row_source=FormRepeatingRowSource.ROW_SET_BINDING,
            binding_id=binding,
        )
        for binding in row_sets
    )
    if not blocks:
        return None
    section = FormSectionDefinition(
        id="inputs", heading_key=_heading_key(build.modelo_id, "section", "inputs"), blocks=tuple(blocks)
    )
    return FormPageDefinition(
        id=page_id, heading_key=_heading_key(build.modelo_id, "page", page_id), sections=(section,)
    )


def _placements(
    build: _Build,
    section_of: Mapping[int, tuple[str, str]],
    shown: set[str],
    continued_aliases: Mapping[str, tuple[FormAliasPosition, ...]],
) -> tuple[FormPlacementDefinition, ...]:
    placements: list[FormPlacementDefinition] = []
    for casilla in sorted(build.revision.casillas, key=lambda item: item.id):
        anchors = build.anchors.get(casilla.id, [])
        box = _casilla_box(casilla.number, casilla.form_number)
        if box is None and anchors:
            box = build.positions[anchors[0]].box
        if casilla.id in shown:
            primary_section = section_of.get(anchors[0]) if anchors else None
            aliases = tuple(
                dict.fromkeys(
                    FormAliasPosition(
                        page_id=section[0], section_id=section[1], official_ref=build.positions[index].page_ref
                    )
                    for index in anchors[1:]
                    if (section := section_of.get(index)) is not None and section != primary_section
                )
            ) or continued_aliases.get(casilla.id, ())
            placements.append(
                FormPlacementDefinition(
                    casilla_id=casilla.id, kind=FormPlacementKind.ON_FORM, box_number=box, aliases=aliases
                )
            )
        elif casilla.id in build.ambiguous:
            placements.append(
                FormPlacementDefinition(
                    casilla_id=casilla.id,
                    kind=FormPlacementKind.UNPLACED,
                    unplaced_reason=FormUnplacedReason.AMBIGUOUS_ANCHOR,
                    box_number=box,
                )
            )
        elif casilla.input_kind is not InputKind.MANUAL or casilla.internal_only:
            placements.append(FormPlacementDefinition(casilla_id=casilla.id, kind=FormPlacementKind.WORKING_FIGURE))
        else:
            placements.append(
                FormPlacementDefinition(
                    casilla_id=casilla.id,
                    kind=FormPlacementKind.UNPLACED,
                    unplaced_reason=FormUnplacedReason.NO_OFFICIAL_ANCHOR,
                )
            )
    return tuple(placements)


def _quoted_column[C: (FormGridColumn, FormRepeatingColumn)](build: _Build, column: C, quote: QuotedHeading) -> C:
    if column.official_heading is not None:
        raise OfficialHeadingRefusedError(f"{quote.describe()}: the design already names this column")
    key = shared_column_key(quote.text) or column.key
    return column.model_copy(
        update={"official_heading": quote.text, "heading_key": _column_heading_key(build.modelo_id, key)}
    )


def _quoted_block(build: _Build, block: FormBlockDefinition, quotes: dict[str, QuotedHeading]) -> FormBlockDefinition:
    if isinstance(block, FormGridBlock):
        grid = tuple(
            _quoted_column(build, column, quotes.pop(column.key)) if column.key in quotes else column
            for column in block.columns
        )
        return block.model_copy(update={"columns": grid})
    if isinstance(block, FormRepeatingGroupBlock):
        repeating = tuple(
            _quoted_column(build, column, quotes.pop(column.key)) if column.key in quotes else column
            for column in block.columns
        )
        return block.model_copy(update={"columns": repeating})
    return block


def _quoted_section(
    build: _Build, section: FormSectionDefinition, quote: QuotedHeading | None, columns: dict[str, QuotedHeading]
) -> FormSectionDefinition:
    update: dict[str, object] = {"blocks": tuple(_quoted_block(build, block, columns) for block in section.blocks)}
    if quote is not None:
        if section.official_heading is not None:
            raise OfficialHeadingRefusedError(f"{quote.describe()}: the design already names this section")
        update["official_heading"] = quote.text
        update["heading_key"] = _heading_key(build.modelo_id, "section", node_slug(quote.text))
    return section.model_copy(update=update)


def _quoted_pages(
    build: _Build,
    pages: Sequence[FormPageDefinition],
    quotes: Sequence[QuotedHeading],
    *,
    sources: Mapping[str, SourceReference],
    data_root: Path,
) -> list[FormPageDefinition]:
    """Head each quoted part with the reviewer's verified quote, and pin the sources quoted from.

    A quote is refused when it is not grounded, when it names a part the layout
    does not have, or when the design already names that part: the design's
    own words always win, so a quote can only fill a gap.
    """
    if not quotes:
        return list(pages)
    cited = tuple(str(ref) for ref in build.revision.source_refs)
    for quote in quotes:
        pinned = verify_quote(quote, cited=cited, sources=sources, data_root=data_root)
        if all(item.source_ref != pinned.source_ref for item in build.design_sources):
            build.design_sources.append(pinned)
    pending = {(quote.page, quote.section, quote.column): quote for quote in quotes}
    if len(pending) != len(quotes):
        raise OfficialHeadingRefusedError(f"{build.modelo_id} {build.revision.id}: a part is quoted twice")
    out: list[FormPageDefinition] = []
    for page in pages:
        sections = []
        for section in page.sections:
            columns = {
                column: quote
                for (page_id, section_id, column), quote in pending.items()
                if page_id == page.id and section_id == section.id and column is not None
            }
            for column in columns:
                del pending[(page.id, section.id, column)]
            heading = pending.pop((page.id, section.id, None), None)
            sections.append(_quoted_section(build, section, heading, columns))
            if columns:
                unknown = ", ".join(sorted(columns))
                raise OfficialHeadingRefusedError(f"{build.modelo_id} {build.revision.id}: no column {unknown}")
        update: dict[str, object] = {"sections": tuple(sections)}
        page_quote = pending.pop((page.id, None, None), None)
        if page_quote is not None:
            if page.official_heading is not None:
                raise OfficialHeadingRefusedError(f"{page_quote.describe()}: the design already names this page")
            update["official_heading"] = page_quote.text
        out.append(page.model_copy(update=update))
    if pending:
        missing = ", ".join(quote.describe() for quote in pending.values())
        raise OfficialHeadingRefusedError(f"quoted parts the layout does not have: {missing}")
    return out


def _seed_source(build: _Build, continued: ContinuedLayout | None) -> FormLayoutSeedSource:
    if build.used_dictionary:
        return FormLayoutSeedSource.XML_DICTIONARY
    if build.used_design and build.used_export:
        return FormLayoutSeedSource.EXPORT_RECORD_DESIGN
    if build.used_design:
        return FormLayoutSeedSource.DESIGN_BOX_NUMBER
    if continued is not None:
        return FormLayoutSeedSource.PREDECESSOR_LAYOUT
    return FormLayoutSeedSource.CASILLA_NUMBER


def _continued_layout(
    build: _Build,
    predecessor: PredecessorLayout | None,
    *,
    sources: Mapping[str, SourceReference],
    data_root: Path,
) -> ContinuedLayout | None:
    """Follow the predecessor only for a revision whose own anchors give no official position."""
    if predecessor is None or build.positions or build.used_design or build.used_dictionary:
        return None
    try:
        continued = continue_predecessor_layout(build.revision, predecessor, sources=sources, data_root=data_root)
    except OfficialFormUnavailableError as error:
        build.notes.append(f"official form unavailable: {error}")
        return None
    if continued is None:
        build.notes.append(f"no form the revision cites confirms a page of predecessor {predecessor.revision.id}")
        return None
    if continued.unconfirmed:
        build.notes.append(
            f"{len(continued.unconfirmed)} continuing casilla(s) not confirmed on the revision's own form: "
            + ", ".join(sorted(continued.unconfirmed))
        )
    pinned = {item.source_ref for item in build.design_sources}
    build.design_sources.extend(item for item in continued.design_sources if item.source_ref not in pinned)
    return continued


def generate_revision_layout(
    modelo_id: str,
    revision: ModeloRevision,
    *,
    sources: Mapping[str, SourceReference],
    data_root: Path,
    headings: Sequence[QuotedHeading] | None = None,
    predecessor: PredecessorLayout | None = None,
) -> LayoutGeneration:
    """Generate one revision's layout through the seed ladder.

    A revision declaring no casillas has no form to lay out and returns no
    layout with its reason, which coverage reports as undeclared. ``headings``
    replaces the reviewer's recorded quotes for this revision; by default they
    are read from ``official_headings.toml``. ``predecessor`` is the declared
    predecessor with its current layout; it is followed only when the revision
    has no official position of its own, never in place of its own design.

    Raises:
        OfficialHeadingRefusedError: When a quoted heading is not grounded on
            its cited line, or names a part the layout does not have.
    """
    if not revision.casillas:
        return LayoutGeneration(modelo_id, revision.id, None, failure="revision declares no casillas")
    build = _Build(modelo_id=modelo_id, revision=revision)
    layouts = derive_export_layouts_from_bindings(revision)
    manual_bindings = _manual_scalar_bindings(revision)
    xml_layout = next((layout for layout in layouts if layout.format is ExportLayoutFormat.XML_DICTIONARY), None)
    records = _fixed_width_records(layouts)
    if xml_layout is not None and xml_layout.dictionary_source_ref is not None:
        _dictionary_positions(build, xml_layout, sources, data_root)
    else:
        _record_design_positions(build, sources, records, manual_bindings)
    _anchor_row_fields(build, records)
    build.used_export = any(position.records for position in build.positions)
    _anchor_casillas(build)
    build.binding_primary = _binding_primary(build)
    repeating = {record.id: record for record in records if record.repeat is not None}
    continued = _continued_layout(build, predecessor, sources=sources, data_root=data_root)
    pages, section_of, shown, _placed_bindings = _build_pages(build, manual_bindings, repeating, continued)
    quotes = read_official_headings().for_revision(modelo_id, str(revision.id)) if headings is None else headings
    pages = _quoted_pages(build, pages, quotes, sources=sources, data_root=data_root)
    layout = FormLayoutDefinition(
        id=GENERATED_LAYOUT_ID,
        revision_id=revision.id,
        seed_source=_seed_source(build, continued),
        generator_version=FORM_LAYOUT_GENERATOR_VERSION,
        source_state_digest=form_layout_source_digest(revision),
        design_sources=tuple(build.design_sources),
        pages=tuple(pages),
        placements=_placements(build, section_of, shown, {} if continued is None else continued.aliases),
    )
    return LayoutGeneration(modelo_id, revision.id, layout, notes=tuple(build.notes))


def generate_modelo_layouts(
    modelo: ModeloDefinition,
    *,
    sources: Mapping[str, SourceReference],
    data_root: Path,
) -> dict[str, LayoutGeneration]:
    """Generate every revision of a modelo whose layout is not reviewed, each after its declared predecessor.

    A revision may follow its predecessor's layout, so the predecessor is
    generated first and its fresh layout is the one followed; a reviewed
    layout is never regenerated and is followed as declared.
    """
    outcomes: dict[str, LayoutGeneration] = {}

    def current(revision_id: str, visiting: frozenset[str]) -> FormLayoutDefinition | None:
        revision = modelo.revisions[revision_id]
        existing = revision.form_layouts[0] if revision.form_layouts else None
        if existing is not None and existing.review.state is FormLayoutReviewState.REVIEWED:
            return existing
        if revision_id not in outcomes:
            followed: PredecessorLayout | None = None
            declared = revision.predecessor
            if (
                isinstance(declared, DeclaredPredecessor)
                and declared.revision_id in modelo.revisions
                and declared.revision_id not in visiting
            ):
                layout = current(declared.revision_id, visiting | {revision_id})
                if layout is not None:
                    followed = PredecessorLayout(revision=modelo.revisions[declared.revision_id], layout=layout)
            outcomes[revision_id] = generate_revision_layout(
                str(modelo.id), revision, sources=sources, data_root=data_root, predecessor=followed
            )
        return outcomes[revision_id].layout

    for revision_id in sorted(modelo.revisions, key=str):
        current(revision_id, frozenset())
    return {
        revision_id: outcomes[revision_id]
        for revision_id in sorted(modelo.revisions, key=str)
        if revision_id in outcomes
    }
