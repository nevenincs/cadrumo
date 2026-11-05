"""Replay, position, and verify a selected casilla delta with the production loader."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from cadrumo.core.toml import freeze_toml_value

from . import edition_delta_errors, edition_delta_fields, edition_delta_row_delta_selection, edition_delta_source
from .compiler.casilla_identity import LINEAGE_CLAIM_FIELDS
from .compiler.casilla_inheritance import inherit_casillas


def _removals(
    inherited: Sequence[edition_delta_source.Placed],
    full_rows: Sequence[edition_delta_source.Row],
    predecessor: str,
    storage_only: bool,
    matched_storage_ids: set[str],
) -> tuple[edition_delta_source.Row, ...]:
    successor_ids = {edition_delta_source.row_id(row) for row in full_rows}
    return tuple(
        {"selector": {"revision": predecessor, "id": edition_delta_source.row_id(placed.row)}}
        for placed in inherited
        if (storage_only or edition_delta_source.lineage(placed.row) is None)
        and edition_delta_source.row_id(placed.row) not in successor_ids
        and edition_delta_source.row_id(placed.row) not in matched_storage_ids
    )


def _simulate_merge(
    revision_id: str,
    predecessor: str,
    inherited: Sequence[edition_delta_source.Placed],
    source: edition_delta_source.EditionSource,
    stated_rows: Sequence[edition_delta_source.Row],
    selection: edition_delta_row_delta_selection.DropSelection,
    removals: Sequence[edition_delta_source.Row],
) -> list[edition_delta_source.Placed]:
    return simulate_storage_output(
        revision_id=revision_id,
        predecessor=predecessor,
        inherited=inherited,
        source=source,
        stated_rows=stated_rows,
        overrides=selection.overrides,
        removals=removals,
    )


def simulate_storage_output(
    *,
    revision_id: str,
    predecessor: str,
    inherited: Sequence[edition_delta_source.Placed],
    source: edition_delta_source.EditionSource,
    stated_rows: Sequence[edition_delta_source.Row],
    overrides: Sequence[edition_delta_source.Row],
    removals: Sequence[edition_delta_source.Row],
    positions: Sequence[edition_delta_source.Row] = (),
) -> list[edition_delta_source.Placed]:
    """Replay a planned row-storage representation through the production merger."""
    successor: dict[str, object] = {
        **source.table,
        edition_delta_fields.CASILLAS: tuple(freeze_toml_value(row) for row in stated_rows),
        "casilla_overrides": tuple(freeze_toml_value(override) for override in overrides),
        "casilla_removals": tuple(freeze_toml_value(removal) for removal in removals),
        "casilla_positions": tuple(freeze_toml_value(position) for position in positions),
    }
    merged_rows, merged_origins, _text_origins = inherit_casillas(
        f"edition {revision_id!r} planned against {predecessor!r}",
        revision_id=revision_id,
        predecessor_id=predecessor,
        inherited=tuple(freeze_toml_value(placed.row) for placed in inherited),
        inherited_label_origins=tuple(placed.origin for placed in inherited),
        inherited_text_origins=None,
        successor=successor,
    )
    return [
        edition_delta_source.Placed(edition_delta_source.as_row(row), origin or revision_id)
        for row, origin in zip(merged_rows, merged_origins, strict=True)
    ]


def _restore_positions(
    merged: list[edition_delta_source.Placed], expected_ids: Sequence[str], revision_id: str, normalise_order: bool
) -> tuple[list[edition_delta_source.Placed], tuple[edition_delta_source.Row, ...]]:
    if normalise_order:
        return merged, ()
    positions: list[edition_delta_source.Row] = []
    for position, expected_id in enumerate(expected_ids):
        current = _current_position(merged, expected_id)
        if current is None:
            raise edition_delta_errors.MigrationRefusedError(
                f"edition {revision_id!r}: storage delta cannot position casilla {expected_id!r}"
            )
        if current != position:
            merged.insert(position, merged.pop(current))
            positions.append({"id": expected_id, "position": position})
    if [edition_delta_source.row_id(placed.row) for placed in merged] != list(expected_ids):
        raise edition_delta_errors.MigrationRefusedError(
            f"edition {revision_id!r}: successor-local positions do not reconstruct casilla order"
        )
    return merged, tuple(positions)


def _current_position(merged: Sequence[edition_delta_source.Placed], expected_id: str) -> int | None:
    return next(
        (index for index, placed in enumerate(merged) if edition_delta_source.row_id(placed.row) == expected_id),
        None,
    )


def _verify_materialisation(
    merged: Sequence[edition_delta_source.Placed],
    full_rows: Sequence[edition_delta_source.Row],
    attested_lineages: set[str],
    revision_id: str,
    defaults: edition_delta_source.Defaults,
    declarations: edition_delta_source.Declarations,
) -> None:
    full_by_id = {edition_delta_source.row_id(row): row for row in full_rows}
    for placed in merged:
        row = full_by_id[edition_delta_source.row_id(placed.row)]
        effective = effective_simulated_row(placed, row, attested_lineages, revision_id, defaults, declarations)
        if effective != row:
            differing = _differing_fields(row, effective)
            raise edition_delta_errors.MigrationRefusedError(
                f"edition {revision_id!r}: simulated casilla {edition_delta_source.row_id(row)!r} "
                f"does not reproduce the full copy; differing fields: {differing!r}",
            )


def effective_simulated_row(
    placed: edition_delta_source.Placed,
    row: edition_delta_source.Row,
    attested_lineages: set[str],
    revision_id: str,
    defaults: edition_delta_source.Defaults,
    declarations: edition_delta_source.Declarations,
) -> edition_delta_source.Row | None:
    """Compute the effective row an edition delta simulates for a placed inherited row."""
    simulated_row = dict(placed.row)
    if edition_delta_source.lineage(row) in attested_lineages:
        for claim_field in LINEAGE_CLAIM_FIELDS:
            if claim_field in row:
                simulated_row[claim_field] = row[claim_field]
    return edition_delta_source.edition_delta_source_effective(
        simulated_row,
        origin=placed.origin,
        revision_id=revision_id,
        defaults=defaults,
        declarations=declarations,
    )


def _differing_fields(row: Mapping[str, object], effective: Mapping[str, object] | None) -> list[str]:
    return sorted(
        key for key in set(row) | set(effective or {}) if effective is None or row.get(key) != effective.get(key)
    )


def reconstruct_drops(
    *,
    revision_id: str,
    predecessor: str,
    inherited: Sequence[edition_delta_source.Placed],
    full_rows: Sequence[edition_delta_source.Row],
    lifts: Mapping[str, edition_delta_source.Lift],
    source: edition_delta_source.EditionSource,
    defaults: edition_delta_source.Defaults,
    normalise_order: bool,
    storage_only: bool,
    selection: edition_delta_row_delta_selection.DropSelection,
) -> tuple[
    tuple[edition_delta_source.Row, ...],
    tuple[edition_delta_source.Row, ...],
    tuple[str, ...],
]:
    """Replay a selection through the loader merge and return its removals, positions and reconstructed order.

    Refuses when the simulated merge cannot position a row or does not reproduce the full copy.
    """
    removals = _removals(inherited, full_rows, predecessor, storage_only, selection.matched_storage_ids)
    stated = frozenset(edition_delta_source.row_id(row) for row in full_rows) - selection.drops
    layout = edition_delta_source.stated_layout(source, stated)
    stated_rows = [lifts[edition_delta_source.row_id(block.row)].row for _, blocks in layout for block in blocks]
    merged = _simulate_merge(revision_id, predecessor, inherited, source, stated_rows, selection, removals)
    expected_ids = [edition_delta_source.row_id(row) for row in full_rows]
    merged, positions = _restore_positions(merged, expected_ids, revision_id, normalise_order)
    attested = {str(attestation.continuidad_id) for attestation in selection.attestations}
    _verify_materialisation(merged, full_rows, attested, revision_id, defaults, source.declarations)
    return (
        tuple(removals),
        positions,
        tuple(edition_delta_source.row_id(placed.row) for placed in merged),
    )
