"""The bindings a form's repeating groups fill row by row.

A repeating group of the form layout opens its lines from a row-set binding,
from the bindings of its columns and grid cells, and from the fields of the
export record it prints. Those bindings stand for a column of repeated lines,
never for one scalar answer, so neither the edit surface nor the form's
answers offer a single override for them. Both read this one derivation.
"""

from __future__ import annotations

from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_form_layouts import FormLayoutDefinition, FormRepeatingGroupBlock


def _repeating_groups(layout: FormLayoutDefinition) -> tuple[FormRepeatingGroupBlock, ...]:
    return tuple(
        block
        for page in layout.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormRepeatingGroupBlock)
    )


def _group_binding_ids(group: FormRepeatingGroupBlock) -> set[str]:
    filled: set[str] = set()
    if group.binding_id is not None:
        filled.add(group.binding_id)
    filled.update(column.binding_id for column in group.columns if column.binding_id is not None)
    filled.update(
        cell.binding_id
        for grid in group.grids
        for row in grid.rows
        for cell in row.cells
        if cell.binding_id is not None
    )
    return filled


def _export_binding_ids(revision: ModeloRevision, records: set[str]) -> set[str]:
    return {
        field.binding
        for export_layout in revision.export_layouts
        for record in export_layout.records
        if record.id in records
        for field in record.fields
        if field.binding is not None
    }


def row_filled_binding_ids(revision: ModeloRevision, layout: FormLayoutDefinition | None) -> frozenset[str]:
    """The bindings a repeating group of ``layout`` fills row by row; none when the layout is not this revision's."""
    if layout is None or layout.revision_id != revision.id:
        return frozenset[str]()
    groups = _repeating_groups(layout)
    records = {group.export_record_id for group in groups if group.export_record_id is not None}
    filled: set[str] = set()
    for group in groups:
        filled.update(_group_binding_ids(group))
    filled.update(_export_binding_ids(revision, records))
    return frozenset(filled)


__all__ = ["row_filled_binding_ids"]
