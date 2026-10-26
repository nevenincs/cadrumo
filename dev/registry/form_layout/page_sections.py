"""Derive section rows, field blocks, shared grids, and repeating groups from positions."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from cadrumo.domain.calculations.registry.schema_exports import (
    ExportRecordDefinition,
)
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormBlockDefinition,
    FormCell,
    FormCellKind,
    FormFieldBlock,
    FormGridBlock,
    FormGridColumn,
    FormGridRow,
    FormRepeatingColumn,
    FormRepeatingGroupBlock,
    FormRepeatingRowSource,
)

from .column_vocabulary import SHARED_COLUMN_HEADING_KEY_PREFIX, SHARED_COLUMN_KEYS, shared_column_key
from .generation_constants import _GENERAL_SECTION
from .generation_models import _Build, _Item, _Position, _RowDraft, _SectionDraft
from .official_text import clean_official_text, description_path, node_slug


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


def _section_slug(key: Sequence[str]) -> str:
    return node_slug("-".join(key)) if key else _GENERAL_SECTION


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


_GridDraft = tuple[list[str], list[tuple[_RowDraft, tuple[str, ...]]]]


def _repeating_record(
    position: _Position, repeating: Mapping[str, ExportRecordDefinition]
) -> ExportRecordDefinition | None:
    return next((repeating[record_id] for record_id in position.records if record_id in repeating), None)


def _repeating_section_items(
    build: _Build,
    draft: _SectionDraft,
    repeating: Mapping[str, ExportRecordDefinition],
    emitted: set[str],
    blocks: list[FormBlockDefinition],
    block_ids: set[str],
) -> list[_Item]:
    plain: list[_Item] = []
    for item in draft.items:
        record = _repeating_record(build.positions[item.position], repeating)
        if record is None:
            plain.append(item)
            continue
        if record.id in emitted:
            continue
        emitted.add(record.id)
        block_id = _unique(node_slug(record.id), block_ids)
        blocks.append(_repeating_record_block(build, record, block_id))
    return plain


def _flush_grid(
    build: _Build,
    grid: _GridDraft | None,
    blocks: list[FormBlockDefinition],
    block_ids: set[str],
) -> None:
    if grid is None:
        return
    column_keys, rows = grid
    blocks.append(_grid_block(build, column_keys, rows, _unique("grid", block_ids)))


def _grid_is_warranted(signature: tuple[str, ...], page_signatures: Counter[tuple[str, ...]]) -> bool:
    shared = all(key in SHARED_COLUMN_KEYS for key in signature)
    return len(signature) >= 2 and (shared or page_signatures[signature] >= 2)


def _append_field_items(items: Sequence[_Item], blocks: list[FormBlockDefinition], block_ids: set[str]) -> None:
    for item in items:
        block = _field_block(_unique("field", block_ids), item)
        if block is not None:
            blocks.append(block)


def _append_section_entry(
    build: _Build,
    entry: _RowDraft | _Item,
    *,
    page_signatures: Counter[tuple[str, ...]],
    grid: _GridDraft | None,
    blocks: list[FormBlockDefinition],
    block_ids: set[str],
) -> _GridDraft | None:
    if not isinstance(entry, _RowDraft):
        _flush_grid(build, grid, blocks, block_ids)
        _append_field_items((entry,), blocks, block_ids)
        return None
    signature = _signature(entry.columns)
    if not _grid_is_warranted(signature, page_signatures):
        _flush_grid(build, grid, blocks, block_ids)
        _append_field_items(entry.items, blocks, block_ids)
        return None
    if grid is not None and _is_subsequence(signature, grid[0]):
        grid[1].append((entry, signature))
        return grid
    _flush_grid(build, grid, blocks, block_ids)
    return (list(signature), [(entry, signature)])


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
    plain = _repeating_section_items(build, draft, repeating, emitted_repeating, blocks, block_ids)
    grid: _GridDraft | None = None
    for entry in _row_drafts(build, plain):
        grid = _append_section_entry(
            build,
            entry,
            page_signatures=page_signatures,
            grid=grid,
            blocks=blocks,
            block_ids=block_ids,
        )
    _flush_grid(build, grid, blocks, block_ids)
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
