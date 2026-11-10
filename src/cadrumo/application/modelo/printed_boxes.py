"""The number the form prints for each box of a revision, read from its published layout.

Every surface that asks whether a box is printed asks here: the editor's form,
the help card, the level a calculation note takes, the notes that persist with
a calculation and the refusal that names a box. The layout's placement gives
the number when it states one; otherwise the number the registry declares for
the form, else the casilla's own number when it is a figure. A box that
resolves to no number is a working figure the form does not print, and a figure
missing there is not a filed figure missing.

See Also:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`
        The registry declaration supplying casillas, formulas, bindings and layout metadata.
    :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
        The pinned registry snapshot supplying the selected modelo revision.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.runtime_graph import expression_binding_refs, expression_casilla_refs
from ...domain.calculations.registry.schema import FormulaDefinition, ModeloRevision, RegistrySnapshot
from ...domain.calculations.registry.schema_form_layouts import FormLayoutDefinition, FormPlacementDefinition
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition


def printed_box_number(casilla: CasillaDefinition | None, placement: FormPlacementDefinition | None) -> str | None:
    """The number the form prints for ``casilla`` placed at ``placement``, or ``None`` for a working figure."""
    if placement is not None and placement.box_number is not None:
        return placement.box_number
    if casilla is None:
        return None
    if casilla.form_number is not None:
        return casilla.form_number
    return casilla.number if casilla.number.isdigit() else None


@dataclass(frozen=True, slots=True)
class PrintedBoxes:
    """The printed number of every box one revision's form prints, by casilla id."""

    numbers: Mapping[str, str]

    def number(self, casilla_id: str | None) -> str | None:
        """The number the form prints for ``casilla_id``, or ``None`` when it prints none or none is named."""
        return None if casilla_id is None else self.numbers.get(casilla_id)

    def prints(self, casilla_id: str | None) -> bool:
        """Whether the form prints ``casilla_id`` as a numbered box."""
        return self.number(casilla_id) is not None


def printed_boxes(revision: ModeloRevision, layout: FormLayoutDefinition | None) -> PrintedBoxes:
    """The boxes ``revision``'s form prints, placed by ``layout`` when it is that revision's own.

    See Also:
        :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`
            The registry declaration supplying casillas, formulas, bindings and layout metadata.
    """
    placements: dict[str, FormPlacementDefinition] = (
        {placement.casilla_id: placement for placement in layout.placements}
        if layout is not None and layout.revision_id == revision.id
        else {}
    )
    numbers = {
        casilla.id: number
        for casilla in revision.casillas
        if (number := printed_box_number(casilla, placements.get(casilla.id))) is not None
    }
    return PrintedBoxes(numbers=MappingProxyType(numbers))


def snapshot_printed_boxes(operation: PinnedAuthorityOperation, snapshot: RegistrySnapshot) -> PrintedBoxes:
    """The boxes the form of ``snapshot``'s revision prints, read from its published layout.

    See Also:
        :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
            The pinned registry snapshot supplying the selected modelo revision.
    """
    return printed_boxes(snapshot.revision, operation.form_layout(snapshot.modelo.id, snapshot.revision.id))


def first_printed_dependent(snapshot: RegistrySnapshot, binding_id: BindingId) -> CasillaId | None:
    """The nearest box the form prints whose calculation reads ``binding_id``, directly or through working figures.

    A binding that feeds a formula rather than populating a box has no box of its own, so a note
    about it names the first printed box that waits on it. Among boxes at the same distance the
    lowest casilla id is taken, so the answer does not depend on declaration order.

    ``snapshot`` is the :class:`RegistrySnapshot`, the pinned registry snapshot.
    """
    printed = printed_boxes(snapshot.revision, None)
    formulas = snapshot.revision.formulas
    frontier = sorted(
        {formula.target_casilla_id for formula in formulas if binding_id in expression_binding_refs(formula.expression)}
    )
    seen: set[CasillaId] = set()
    while frontier:
        reached = [casilla_id for casilla_id in frontier if printed.prints(casilla_id)]
        if reached:
            return reached[0]
        seen.update(frontier)
        frontier = _next_dependents(formulas, seen)
    return None


def _next_dependents(formulas: Sequence[FormulaDefinition], seen: set[CasillaId]) -> list[CasillaId]:
    """The unseen formula targets that read any casilla already reached, in casilla id order."""
    return sorted(
        {
            formula.target_casilla_id
            for formula in formulas
            if formula.target_casilla_id not in seen
            and any(casilla_id in seen for casilla_id in expression_casilla_refs(formula.expression))
        }
    )


__all__ = [
    "PrintedBoxes",
    "first_printed_dependent",
    "printed_box_number",
    "printed_boxes",
    "snapshot_printed_boxes",
]
