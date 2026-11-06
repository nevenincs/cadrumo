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
    FormContextFieldBlock,
    FormFieldBlock,
    FormGridBlock,
    FormGridColumn,
    FormGridRow,
)

from .column_vocabulary import SHARED_COLUMN_KEYS, shared_column_key
from .generation_constants import GENERAL_SECTION
from .generation_models import Build, Item, Position, RowDraft, SectionDraft
from .heading_keys import column_form_heading_key, form_heading_key, unique
from .official_text import clean_official_text, description_path, node_slug
from .repeating_blocks import official_repeat_items, repeating_section_items


def _section_key(position: Position) -> tuple[str, ...]:
    if position.xml_container is not None:
        return position.xml_container[2:3]
    return description_path(position.description).section


def _items_for(build: Build, index: int, primary: Mapping[str, int]) -> list[Item]:
    position = build.positions[index]
    items = [
        Item(
            position=index, casilla_id=casilla_id, literal=position.literal, literal_decimals=position.literal_decimals
        )
        for casilla_id in position.casilla_ids
        if primary.get(casilla_id) == index
    ]
    items.extend(
        Item(position=index, binding_id=binding_id)
        for binding_id in position.binding_ids
        if build.binding_primary.get(binding_id) == index
    )
    items.extend(Item(position=index, context_field=context) for context in position.context_fields)
    if not items and position.literal is not None and position.box is not None:
        items.append(Item(position=index, literal=position.literal, literal_decimals=position.literal_decimals))
    return items


def page_sections(build: Build, indexes: Sequence[int], primary: Mapping[str, int]) -> list[SectionDraft]:
    """Group a page's positions into contiguous runs sharing a heading path."""
    aliased = {index for anchors in build.anchors.values() for index in anchors[1:]}
    drafts: list[SectionDraft] = []
    for index in indexes:
        items = _items_for(build, index, primary)
        if not items and index not in aliased:
            continue
        key = _section_key(build.positions[index])
        if not drafts or drafts[-1].key != key:
            heading = " - ".join(key) if key and build.positions[index].xml_container is None else None
            drafts.append(SectionDraft(key=key, heading=heading))
        drafts[-1].positions.append(index)
        drafts[-1].items.extend(items)
    return drafts


def row_drafts(build: Build, items: Sequence[Item]) -> list[RowDraft | Item]:
    """Split a section's items into row candidates and lone items."""
    out: list[RowDraft | Item] = []
    current: RowDraft | None = None
    for item in items:
        position = build.positions[item.position]
        path = description_path(position.description) if position.xml_container is None else description_path(None)
        if item.context_field is not None or path.stem is None or path.column is None:
            current = None
            out.append(item)
            continue
        if current is None or current.stem != path.stem or path.column in current.columns:
            current = RowDraft(stem=path.stem, columns=[], items=[])
            out.append(current)
        current.columns.append(path.column)
        current.items.append(item)
    return out


def page_sections_signature(columns: Sequence[str]) -> tuple[str, ...]:
    """Build a column signature from shared column keys or slugs."""
    return tuple(shared_column_key(column) or node_slug(column) for column in columns)


def _is_subsequence(candidate: Sequence[str], whole: Sequence[str]) -> bool:
    iterator = iter(whole)
    return all(any(token == value for value in iterator) for token in candidate)


def section_slug(key: Sequence[str]) -> str:
    """Build a section slug from its key, or the general section when it is empty."""
    return node_slug("-".join(key)) if key else GENERAL_SECTION


def _cell(item: Item) -> FormCell:
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


def _field_block(block_id: str, item: Item) -> FormFieldBlock | FormContextFieldBlock | None:
    if item.context_field is not None:
        return item.context_field.model_copy(update={"id": block_id})
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


_GridDraft = tuple[list[str], list[tuple[RowDraft, tuple[str, ...]]]]


def _flush_grid(
    build: Build,
    grid: _GridDraft | None,
    blocks: list[FormBlockDefinition],
    block_ids: set[str],
) -> None:
    if grid is None:
        return
    column_keys, rows = grid
    blocks.append(_grid_block(build, column_keys, rows, unique("grid", block_ids)))


def _grid_is_warranted(signature: tuple[str, ...], page_signatures: Counter[tuple[str, ...]]) -> bool:
    shared = all(key in SHARED_COLUMN_KEYS for key in signature)
    return len(signature) >= 2 and (shared or page_signatures[signature] >= 2)


def _append_field_items(items: Sequence[Item], blocks: list[FormBlockDefinition], block_ids: set[str]) -> None:
    for item in items:
        block = _field_block(unique("field", block_ids), item)
        if block is not None:
            blocks.append(block)


def _append_section_entry(
    build: Build,
    entry: RowDraft | Item,
    *,
    page_signatures: Counter[tuple[str, ...]],
    grid: _GridDraft | None,
    blocks: list[FormBlockDefinition],
    block_ids: set[str],
) -> _GridDraft | None:
    if not isinstance(entry, RowDraft):
        _flush_grid(build, grid, blocks, block_ids)
        _append_field_items((entry,), blocks, block_ids)
        return None
    signature = page_sections_signature(entry.columns)
    if not _grid_is_warranted(signature, page_signatures):
        _flush_grid(build, grid, blocks, block_ids)
        _append_field_items(entry.items, blocks, block_ids)
        return None
    if grid is not None and _is_subsequence(signature, grid[0]):
        grid[1].append((entry, signature))
        return grid
    _flush_grid(build, grid, blocks, block_ids)
    return (list(signature), [(entry, signature)])


def section_blocks(
    build: Build,
    draft: SectionDraft,
    *,
    page_signatures: Counter[tuple[str, ...]],
    repeating: Mapping[str, ExportRecordDefinition],
    emitted_repeating: set[str],
) -> list[FormBlockDefinition]:
    """Build the form blocks of a section draft."""
    blocks: list[FormBlockDefinition] = []
    block_ids: set[str] = set()
    plain = repeating_section_items(build, draft, repeating, emitted_repeating, blocks, block_ids)
    plain = official_repeat_items(build, plain, emitted_repeating, blocks, block_ids)
    grid: _GridDraft | None = None
    for entry in row_drafts(build, plain):
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
    build: Build,
    column_keys: Sequence[str],
    rows: Sequence[tuple[RowDraft, tuple[str, ...]]],
    block_id: str,
) -> FormGridBlock:
    first_row = rows[0][0]
    columns = tuple(
        FormGridColumn(
            key=key,
            heading_key=column_form_heading_key(build.modelo_id, key),
            official_heading=clean_official_text(text) or None,
        )
        for key, text in zip(column_keys, first_row.columns, strict=True)
    )
    used_rows: set[str] = set()
    grid_rows: list[FormGridRow] = []
    for row, signature in rows:
        by_key = dict(zip(signature, row.items, strict=True))
        row_key = unique(node_slug(row.stem), used_rows)
        grid_rows.append(
            FormGridRow(
                key=row_key,
                heading_key=form_heading_key(build.modelo_id, "row", node_slug(row.stem)),
                official_heading=row.stem,
                cells=tuple(
                    _cell(by_key[key]) if key in by_key else FormCell(kind=FormCellKind.BLANK) for key in column_keys
                ),
            )
        )
    return FormGridBlock(id=block_id, columns=columns, rows=tuple(grid_rows))
