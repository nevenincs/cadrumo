"""Validate worksheet row-set ingress before delegating typed assembly.

The calculation application owns conversion of one declared row-set into typed
observations.  This module owns the preceding workbook boundary: an inbound
row-set may only address columns declared by the authoritative snapshot, and
two submitted row-set blocks must never silently claim the same logical row.
It deliberately delegates the actual conversion to the existing snapshot-bound
application command rather than growing a second assembler or a source-mesh
resolver.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import TYPE_CHECKING, NoReturn, Protocol

from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.schema import RegistrySnapshot
from ._engine import collect_row_sets

__all__ = ["assemble_row_sets_for_snapshot"]

if TYPE_CHECKING:
    from ...calculations.row_set_assembly import AssembledObservations


class _RowSetCellShape(Protocol):
    """Structural inbound-cell shape shared by worksheet transports."""

    @property
    def binding(self) -> str: ...

    @property
    def row_index(self) -> int: ...

    @property
    def value(self) -> Decimal | str | None: ...


class _RowSetShape(Protocol):
    """Structural inbound row-set shape shared by worksheet transports."""

    @property
    def grouping(self) -> str: ...

    @property
    def cells(self) -> Iterable[_RowSetCellShape]: ...


def assemble_row_sets_for_snapshot(
    row_sets: Iterable[_RowSetShape],
    snapshot: RegistrySnapshot,
) -> tuple[AssembledObservations, ...]:
    """Validate and assemble worksheet row sets against *snapshot*.

    The accepted grouping-to-binding coordinates come from the same
    ``collect_row_sets`` projection that produced the workbook.  A cell cannot
    be repurposed by placing a binding from another grouping beneath a chosen
    header, and a second input block cannot overwrite part of an already-owned
    row.  After those ingress checks, the existing observation assembler remains the one
    authority for typed row validation and observation construction.

    Returns the existing assembled-observation union once for each supplied
    row-set block.  No source resolution, persisted identity, or provenance is
    constructed here; later source-specific rows own those concerns.
    """
    bindings_by_grouping = _bindings_by_grouping(snapshot)
    grouping_by_binding = {
        binding_id: grouping for grouping, binding_ids in bindings_by_grouping.items() for binding_id in binding_ids
    }
    row_owners: dict[tuple[str, int], int] = {}
    prepared: list[tuple[str, tuple[_RowSetCellShape, ...]]] = []

    for row_set_index, row_set in enumerate(row_sets):
        grouping = str(row_set.grouping)
        cells = tuple(row_set.cells)
        allowed_bindings = bindings_by_grouping.get(grouping)
        if allowed_bindings is None:
            _raise_ingress_refusal(
                "undeclared_grouping",
                grouping=grouping,
                row_index=_first_row_index(cells),
            )

        _validate_cells(
            cells,
            grouping=grouping,
            allowed_bindings=allowed_bindings,
            grouping_by_binding=grouping_by_binding,
        )
        _claim_rows(
            cells,
            grouping=grouping,
            row_set_index=row_set_index,
            row_owners=row_owners,
        )
        prepared.append((grouping, cells))

    # ``application.calculations`` imports this storage facade for relation
    # prefill, so defer the observation assembler until that package has
    # completed initialization.
    from ...calculations.row_set_assembly import assemble_observations_for_snapshot

    return tuple(assemble_observations_for_snapshot(grouping, cells, snapshot) for grouping, cells in prepared)


def _bindings_by_grouping(snapshot: RegistrySnapshot) -> Mapping[str, frozenset[str]]:
    """Return the layout-declared binding ids available under every grouping."""
    return {
        row_set.grouping: frozenset(str(column.binding) for column in row_set.columns)
        for row_set in collect_row_sets(snapshot.revision)
    }


def _validate_cells(
    cells: tuple[_RowSetCellShape, ...],
    *,
    grouping: str,
    allowed_bindings: frozenset[str],
    grouping_by_binding: Mapping[str, str],
) -> None:
    """Refuse unowned fields and duplicate coordinates before the observation assembler can drop them."""
    claimed_cells: set[tuple[str, int]] = set()
    for cell in cells:
        binding_id = str(cell.binding)
        row_index = cell.row_index
        if binding_id not in allowed_bindings:
            declared_grouping = grouping_by_binding.get(binding_id)
            reason = "caller_binding_substitution" if declared_grouping is not None else "unknown_field"
            _raise_ingress_refusal(
                reason,
                grouping=grouping,
                row_index=row_index,
                binding_id=binding_id,
                declared_grouping=declared_grouping,
            )
        coordinate = (binding_id, row_index)
        if coordinate in claimed_cells:
            _raise_ingress_refusal(
                "duplicate_cell_coordinate",
                grouping=grouping,
                row_index=row_index,
                binding_id=binding_id,
            )
        claimed_cells.add(coordinate)


def _claim_rows(
    cells: tuple[_RowSetCellShape, ...],
    *,
    grouping: str,
    row_set_index: int,
    row_owners: dict[tuple[str, int], int],
) -> None:
    """Refuse a second submitted block claiming a grouping-and-row coordinate."""
    for row_index in {cell.row_index for cell in cells}:
        coordinate = (grouping, row_index)
        first_owner = row_owners.get(coordinate)
        if first_owner is not None:
            _raise_ingress_refusal(
                "row_ownership_collision",
                grouping=grouping,
                row_index=row_index,
                first_row_set_index=first_owner,
                second_row_set_index=row_set_index,
            )
        row_owners[coordinate] = row_set_index


def _first_row_index(cells: tuple[_RowSetCellShape, ...]) -> int:
    """Return an available row coordinate for the existing row-refusal contract."""
    return min((cell.row_index for cell in cells), default=1)


def _raise_ingress_refusal(
    reason: str,
    *,
    grouping: str,
    row_index: int,
    binding_id: str | None = None,
    declared_grouping: str | None = None,
    first_row_set_index: int | None = None,
    second_row_set_index: int | None = None,
) -> NoReturn:
    """Raise through the established localized row-assembly refusal contract."""
    context: dict[str, object] = {
        "row_index": row_index,
        "validation_error_type": "row_set_ingress",
        "validation_error_detail": reason,
        "grouping": grouping,
    }
    if binding_id is not None:
        context["binding_id"] = binding_id
    if declared_grouping is not None:
        context["declared_grouping"] = declared_grouping
    if first_row_set_index is not None:
        context["first_row_set_index"] = first_row_set_index
    if second_row_set_index is not None:
        context["second_row_set_index"] = second_row_set_index
    raise RegistryValidationError(
        translated_message="application.calculations.row_set.errors.row_assembly_failed",
        context=context,
    )
