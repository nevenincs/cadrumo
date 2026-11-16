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
from .work_form_facts import ModeloFormFieldFacts
from .work_form_field_projection import binding_facts
from .work_form_field_vocabulary import ModeloFormBindingAddressV1

if TYPE_CHECKING:
    from .work_form_context import WorkFormContext


def answer_facts(
    layout: FormLayoutDefinition, context: WorkFormContext, shown: Iterable[ModeloFormFieldFacts]
) -> tuple[ModeloFormFieldFacts, ...]:
    """The admitted binding overrides no ``shown`` box takes, classified, in declaration order.

    The admission already leaves out what the form cannot answer: a binding a
    repeating group fills row by row and one the calculation does not read for
    the period are not writable entries, so they are not gathered here.
    """
    taken = _taken_by_fields(shown)
    revision = context.snapshot.revision
    period = context.review.period.registry_token
    row_filled = row_filled_binding_ids(revision, layout)
    return tuple(
        binding_facts(binding.id, context)
        for binding in revision.bindings
        if binding.id not in taken
        and isinstance(
            permitted_binding_entry(binding, revision=revision, period=period, row_filled=row_filled),
            ModeloEditWritableBindingOverrideSurfaceEntryV1,
        )
    )


def _taken_by_fields(shown: Iterable[ModeloFormFieldFacts]) -> set[str]:
    """The bindings a shown box is addressed to or replaces when overridden.

    A box edits either itself or the first binding feeding it, so the binding
    an override replaces is always that first one.
    """
    taken: set[str] = set()
    for field in shown:
        if isinstance(field.address, ModeloFormBindingAddressV1):
            taken.add(field.address.binding_id)
        if field.first_binding_id is not None:
            taken.add(field.first_binding_id)
    return taken


__all__ = ["answer_facts"]
