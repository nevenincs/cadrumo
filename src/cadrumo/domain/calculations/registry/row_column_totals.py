"""Which scalar bindings of a revision stand as the total of which row columns.

A binding family that states a quantity both as one box and as one row per
occurrence declares how the two relate. The export reads that relation to
refuse a box its rows do not add up to, without naming a family or a box.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .capital_mobiliario_position_bindings import capital_mobiliario_row_totals

if TYPE_CHECKING:
    from .ids import BindingId
    from .schema import ModeloRevision

__all__ = ["RowColumnTotal", "revision_row_column_totals"]


@dataclass(frozen=True, slots=True)
class RowColumnTotal:
    """A scalar binding whose value the rows of its columns must add up to."""

    total_binding_id: BindingId
    column_binding_ids: tuple[BindingId, ...]


def revision_row_column_totals(revision: ModeloRevision) -> tuple[RowColumnTotal, ...]:
    """Return every total-to-rows relation the families of a :class:`ModeloRevision` declare."""
    return tuple(
        RowColumnTotal(total_binding_id=total, column_binding_ids=columns)
        for total, columns in capital_mobiliario_row_totals(revision)
    )
