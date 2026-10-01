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

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
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
        return None if casilla_id is None else self.numbers.get(str(casilla_id))

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
        {str(placement.casilla_id): placement for placement in layout.placements}
        if layout is not None and str(layout.revision_id) == str(revision.id)
        else {}
    )
    numbers = {
        str(casilla.id): number
        for casilla in revision.casillas
        if (number := printed_box_number(casilla, placements.get(str(casilla.id)))) is not None
    }
    return PrintedBoxes(numbers=MappingProxyType(numbers))


def snapshot_printed_boxes(operation: PinnedAuthorityOperation, snapshot: RegistrySnapshot) -> PrintedBoxes:
    """The boxes the form of ``snapshot``'s revision prints, read from its published layout.

    See Also:
        :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
            The pinned registry snapshot supplying the selected modelo revision.
    """
    return printed_boxes(snapshot.revision, operation.form_layout(str(snapshot.modelo.id), str(snapshot.revision.id)))


__all__ = ["PrintedBoxes", "printed_box_number", "printed_boxes", "snapshot_printed_boxes"]
