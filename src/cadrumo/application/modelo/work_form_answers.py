"""Give every answer the edit surface admits a field of the form.

The edit admission admits an override for every binding whose source an
operator may replace (:func:`~.edit_admission.permitted_binding_entry`). A
declaration whose calculation reads such a binding without any field of the
form taking it would ask for an answer nobody can give: the boxes it feeds read
as not worked out, and no editor reaches the binding. So the form gathers each
admitted binding that no page, working figure or unplaced casilla takes, and no
repeating group of the layout fills row by row, as an answer of its own.

A binding is taken by a field that is addressed to it, edits it, or is fed by
it first, since an override of that field replaces exactly that binding. The
admission refuses, and so the form does not gather, a binding the calculation
does not read for the target period or declares with no calculation consumer
(its handoff reads the carried observation itself, never an override), and one
a repeating group fills line by line, which stands for a column of lines.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from ...domain.calculations.registry.schema_form_layouts import FormLayoutDefinition
from .edit_admission import permitted_binding_entry
from .edit_models import ModeloEditWritableBindingOverrideSurfaceEntryV1
from .row_filled_bindings import row_filled_binding_ids
from .work_form_field_projection import project_binding_field
from .work_form_field_vocabulary import ModeloFormBindingAddressV1
from .work_form_models import ModeloFormField

if TYPE_CHECKING:
    from .work_form_context import WorkFormContext


def answer_fields(
    layout: FormLayoutDefinition, context: WorkFormContext, shown: Iterable[ModeloFormField]
) -> tuple[ModeloFormField, ...]:
    """The admitted binding overrides no ``shown`` field takes, in declaration order.

    The admission already leaves out what the form cannot answer: a binding a
    repeating group fills row by row and one the calculation does not read for
    the period are not writable entries, so they are not gathered here.
    """
    taken = _taken_by_fields(shown)
    revision = context.snapshot.revision
    period = context.review.period.registry_token
    row_filled = row_filled_binding_ids(revision, layout)
    return tuple(
        project_binding_field(binding.id, context)
        for binding in revision.bindings
        if binding.id not in taken
        and isinstance(
            permitted_binding_entry(binding, revision=revision, period=period, row_filled=row_filled),
            ModeloEditWritableBindingOverrideSurfaceEntryV1,
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


__all__ = ["answer_fields"]
