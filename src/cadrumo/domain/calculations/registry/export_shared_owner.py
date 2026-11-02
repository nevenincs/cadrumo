"""Casillas an export layout writes into several cells without a declared reason.

The fixed-width renderer reads each cell's value by casilla id, so one casilla
mapped to several cells puts one value into all of them. That is correct only
when the cells carry one concept, and the registry already says so in two ways:
each cell of a split states which part of the value it writes, and a casilla
carrying ``segmento`` was reviewed as one record segment's own box, so its cells
elsewhere repeat it. In a revision declaring no segment a box number is unique
by the casilla contract, so a repeated cell is that same box.

What remains is a box a multi-segment revision left without a segment: the
design may print that number on several sheets with a different meaning on each,
and nothing declares that the cells agree.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from ....core.casilla_id import CasillaId
from ..export_field_kind import CasillaFieldKind
from .errors import RegistryValidationError
from .export_value_policy import COMPONENT_VALUE_POLICIES
from .fixed_width_codec import render_fixed_width_export_field
from .schema_exports import ExportFieldDefinition, ExportLayoutDefinition
from .schema_surfaces import CasillaDefinition

__all__ = [
    "UnadjudicatedSharedOwner",
    "canonical_export_layout",
    "unadjudicated_shared_owners",
    "written_unadjudicated_shared_owners",
]


@dataclass(frozen=True, slots=True)
class UnadjudicatedSharedOwner:
    """A casilla written into several cells that nothing declares to share its concept."""

    casilla_id: CasillaId
    target_cells: tuple[ExportFieldDefinition, ...]

    @property
    def target_cell_ids(self) -> tuple[str, ...]:
        """Return the cell identities in layout order."""
        return tuple(str(cell.id) for cell in self.target_cells)


def canonical_export_layout(layouts: Iterable[ExportLayoutDefinition]) -> ExportLayoutDefinition | None:
    """Return the one layout a revision exports through, or ``None`` when it declares none."""
    ordered = sorted(layouts, key=lambda layout: layout.id)
    return ordered[0] if ordered else None


def unadjudicated_shared_owners(
    layout: ExportLayoutDefinition,
    casillas: Iterable[CasillaDefinition],
) -> tuple[UnadjudicatedSharedOwner, ...]:
    """Return every owner of ``layout`` whose several cells have no declared relation."""
    declared = {casilla.id: casilla for casilla in casillas}
    if not any(casilla.segmento is not None for casilla in declared.values()):
        return ()
    cells_by_owner: defaultdict[CasillaId, list[tuple[str, ExportFieldDefinition]]] = defaultdict(list)
    for record in layout.records:
        for field in record.fields:
            if field.kind is CasillaFieldKind.CASILLA and field.casilla_id is not None:
                cells_by_owner[field.casilla_id].append((str(record.id), field))
    return tuple(
        UnadjudicatedSharedOwner(casilla_id=casilla_id, target_cells=tuple(cell for _record, cell in cells))
        for casilla_id, cells in cells_by_owner.items()
        if len(cells) > 1 and not _relation_is_declared(declared.get(casilla_id), cells)
    )


def written_unadjudicated_shared_owners(
    layout: ExportLayoutDefinition,
    casillas: Iterable[CasillaDefinition],
    values: Mapping[CasillaId, object],
) -> tuple[UnadjudicatedSharedOwner, ...]:
    """Return the unadjudicated owners whose value would state something in their cells."""
    return tuple(
        owner
        for owner in unadjudicated_shared_owners(layout, casillas)
        if _states_something(owner.target_cells, values.get(owner.casilla_id))
    )


def _relation_is_declared(
    casilla: CasillaDefinition | None,
    cells: Sequence[tuple[str, ExportFieldDefinition]],
) -> bool:
    if casilla is not None and casilla.segmento is not None:
        return True
    return len({record for record, _cell in cells}) == 1 and all(
        cell.value_policy in COMPONENT_VALUE_POLICIES for _record, cell in cells
    )


def _states_something(cells: Iterable[ExportFieldDefinition], value: object) -> bool:
    """Say whether ``value`` reaches any cell as anything other than that cell's absent fill.

    Compared through the codec rather than by asking whether the value is zero:
    what makes a zero harmless is that the filing carries the same bytes as if the
    casilla had never been supplied, and a text cell would print it as a ``0``.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return False
    return any(_differs_from_absent(cell, value) for cell in cells)


def _differs_from_absent(cell: ExportFieldDefinition, value: object) -> bool:
    try:
        return render_fixed_width_export_field(cell, value) != render_fixed_width_export_field(cell, None)
    except RegistryValidationError:
        return True
