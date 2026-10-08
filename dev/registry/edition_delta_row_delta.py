"""Coordinate safe casilla row drops, overrides, removals, and order proof."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from cadrumo.domain.calculations.registry.lineage_attestation import LineageAttestation
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from . import edition_delta_row_delta_reconstruction as _edition_delta_row_delta_reconstruction
from . import edition_delta_row_delta_selection as _edition_delta_row_delta_selection
from . import edition_delta_source as _edition_delta_source
from . import edition_delta_types as _edition_delta_types


def _unretired_withdrawal(
    inherited: Sequence[_edition_delta_source._Placed],
    full_rows: Sequence[_edition_delta_source._Row],
    source: _edition_delta_source._EditionSource,
    storage_only: bool,
) -> bool:
    if storage_only:
        return False
    stated_lineages = {_edition_delta_source._lineage(row) for row in full_rows}
    return any(
        (lineage := _edition_delta_source._lineage(placed.row)) is not None
        and lineage not in stated_lineages
        and lineage not in source.retired
        for placed in inherited
    )


def _choose_drops(
    *,
    definition: ModeloDefinition,
    revision_id: str,
    predecessor: str,
    inherited: Sequence[_edition_delta_source._Placed],
    full_rows: Sequence[_edition_delta_source._Row],
    lifts: Mapping[str, _edition_delta_source._Lift],
    source: _edition_delta_source._EditionSource,
    defaults: _edition_delta_source._Defaults,
    normalise_order: bool = False,
    storage_only: bool = False,
) -> tuple[
    list[_edition_delta_types.BlockedCause],
    set[str],
    Counter[_edition_delta_types.KeptReason],
    list[str],
    tuple[_edition_delta_source._Row, ...],
    tuple[_edition_delta_source._Row, ...],
    tuple[_edition_delta_source._Row, ...],
    tuple[LineageAttestation, ...],
    tuple[str, ...],
    bool,
]:
    del definition  # Materialisation and identity are supplied by the typed source rows.
    if _unretired_withdrawal(inherited, full_rows, source, storage_only):
        return [_edition_delta_types.BlockedCause.UNRETIRED_WITHDRAWAL], set(), Counter(), [], (), (), (), (), (), False
    context = _edition_delta_row_delta_selection.selection_context(
        revision_id, predecessor, inherited, lifts, source, defaults, storage_only
    )
    selection = _edition_delta_row_delta_selection.select_drops(context, full_rows)
    removals, positions, reconstructed_order = _edition_delta_row_delta_reconstruction.reconstruct_drops(
        revision_id=revision_id,
        predecessor=predecessor,
        inherited=inherited,
        full_rows=full_rows,
        lifts=lifts,
        source=source,
        defaults=defaults,
        normalise_order=normalise_order,
        storage_only=storage_only,
        selection=selection,
    )
    return (
        [],
        selection.drops,
        selection.kept,
        selection.not_exact,
        tuple(selection.overrides),
        removals,
        positions,
        tuple(selection.attestations),
        reconstructed_order,
        normalise_order,
    )
