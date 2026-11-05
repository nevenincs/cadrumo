"""Coordinate safe casilla row drops, overrides, removals, and order proof."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from cadrumo.domain.calculations.registry.lineage_attestation import LineageAttestation
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from . import (
    edition_delta_row_delta_reconstruction,
    edition_delta_row_delta_selection,
    edition_delta_source,
    edition_delta_types,
)


def _unretired_withdrawal(
    inherited: Sequence[edition_delta_source.Placed],
    full_rows: Sequence[edition_delta_source.Row],
    source: edition_delta_source.EditionSource,
    storage_only: bool,
) -> bool:
    if storage_only:
        return False
    stated_lineages = {edition_delta_source.lineage(row) for row in full_rows}
    return any(
        (lineage := edition_delta_source.lineage(placed.row)) is not None
        and lineage not in stated_lineages
        and lineage not in source.retired
        for placed in inherited
    )


def choose_drops(
    *,
    definition: ModeloDefinition,
    revision_id: str,
    predecessor: str,
    inherited: Sequence[edition_delta_source.Placed],
    full_rows: Sequence[edition_delta_source.Row],
    lifts: Mapping[str, edition_delta_source.Lift],
    source: edition_delta_source.EditionSource,
    defaults: edition_delta_source.Defaults,
    normalise_order: bool = False,
    storage_only: bool = False,
) -> tuple[
    list[edition_delta_types.BlockedCause],
    set[str],
    Counter[edition_delta_types.KeptReason],
    list[str],
    tuple[edition_delta_source.Row, ...],
    tuple[edition_delta_source.Row, ...],
    tuple[edition_delta_source.Row, ...],
    tuple[LineageAttestation, ...],
    tuple[str, ...],
    bool,
]:
    del definition  # Materialisation and identity are supplied by the typed source rows.
    if _unretired_withdrawal(inherited, full_rows, source, storage_only):
        return [edition_delta_types.BlockedCause.UNRETIRED_WITHDRAWAL], set(), Counter(), [], (), (), (), (), (), False
    context = edition_delta_row_delta_selection.selection_context(
        revision_id, predecessor, inherited, lifts, source, defaults, storage_only
    )
    selection = edition_delta_row_delta_selection.select_drops(context, full_rows)
    removals, positions, reconstructed_order = edition_delta_row_delta_reconstruction.reconstruct_drops(
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
