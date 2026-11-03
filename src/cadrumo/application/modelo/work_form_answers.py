"""Give every answer the edit surface admits a field of the form.

The edit admission admits an override for every binding whose source an
operator may replace (:func:`~.edit_admission.permitted_binding_entry`). A
declaration whose calculation reads such a binding without any field of the
form taking it would ask for an answer nobody can give: the boxes it feeds read
as not worked out, and no editor reaches the binding. So the form gathers each
admitted binding that no page, working figure or unplaced casilla takes, and no
repeating group of the layout fills row by row, as an answer of its own.

A binding is taken by a field that is addressed to it, edits it, or is fed by
it first, since an override of that field replaces exactly that binding. A
binding the calculation does not read for the target period asks nothing, so
it is not gathered, and neither is one declared with no calculation consumer:
its handoff reads the carried observation itself, never an override.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from ...domain.calculations.registry.binding_temporal import binding_applies_to_period
from ...domain.calculations.registry.schema_form_layouts import FormLayoutDefinition, FormRepeatingGroupBlock
from .edit_admission import permitted_binding_entry
from .edit_models import ModeloEditWritableBindingOverrideSurfaceEntryV1
from .work_form_field_projection import project_binding_field
from .work_form_models import ModeloFormBindingAddressV1, ModeloFormField

if TYPE_CHECKING:
    from .work_form_context import WorkFormContext


def answer_fields(
    layout: FormLayoutDefinition, context: WorkFormContext, shown: Iterable[ModeloFormField]
) -> tuple[ModeloFormField, ...]:
    """The admitted binding overrides no ``shown`` field and no repeating group takes, in declaration order."""
    taken = _taken_by_fields(shown) | _filled_by_rows(layout, context)
    revision = context.snapshot.revision
    period = context.review.period.registry_token
    return tuple(
        project_binding_field(binding.id, context)
        for binding in revision.bindings
        if binding.id not in taken
        and binding_applies_to_period(binding.applicability, period)
        and isinstance(
            permitted_binding_entry(binding, revision=revision), ModeloEditWritableBindingOverrideSurfaceEntryV1
        )
    )


def _taken_by_fields(shown: Iterable[ModeloFormField]) -> set[str]:
    taken: set[str] = set()
    for field in shown:
        for address in (field.address, field.edit_address):
            if isinstance(address, ModeloFormBindingAddressV1):
                taken.add(address.binding_id)
        if field.bindings:
            taken.add(field.bindings[0].binding_id)
    return taken


def _filled_by_rows(layout: FormLayoutDefinition, context: WorkFormContext) -> set[str]:
    """The bindings a repeating group fills row by row: its row set, its columns and its export record's fields."""
    groups = [
        block
        for page in layout.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormRepeatingGroupBlock)
    ]
    records = {group.export_record_id for group in groups if group.export_record_id is not None}
    filled: set[str] = set()
    for group in groups:
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
    filled.update(
        field.binding
        for export_layout in context.snapshot.revision.export_layouts
        for record in export_layout.records
        if record.id in records
        for field in record.fields
        if field.binding is not None
    )
    return filled


__all__ = ["answer_fields"]
