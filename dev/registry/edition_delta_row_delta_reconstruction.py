"""Replay, position, and verify a selected casilla delta with the production loader."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from cadrumo.core.toml import freeze_toml_value

from . import edition_delta_errors as _edition_delta_errors
from . import edition_delta_fields as _edition_delta_fields
from . import edition_delta_row_delta_selection as _edition_delta_row_delta_selection
from . import edition_delta_source as _edition_delta_source
from .compiler.casilla_identity import LINEAGE_CLAIM_FIELDS
from .compiler.casilla_inheritance import inherit_casillas


def _removals(
    inherited: Sequence[_edition_delta_source._Placed],
    full_rows: Sequence[_edition_delta_source._Row],
    predecessor: str,
    storage_only: bool,
    matched_storage_ids: set[str],
) -> tuple[_edition_delta_source._Row, ...]:
    successor_ids = {_edition_delta_source._row_id(row) for row in full_rows}
    return tuple(
        {"selector": {"revision": predecessor, "id": _edition_delta_source._row_id(placed.row)}}
        for placed in inherited
        if (storage_only or _edition_delta_source._lineage(placed.row) is None)
        and _edition_delta_source._row_id(placed.row) not in successor_ids
        and _edition_delta_source._row_id(placed.row) not in matched_storage_ids
    )


def _simulate_merge(
    revision_id: str,
    predecessor: str,
    inherited: Sequence[_edition_delta_source._Placed],
    source: _edition_delta_source._EditionSource,
    stated_rows: Sequence[_edition_delta_source._Row],
    selection: _edition_delta_row_delta_selection.DropSelection,
    removals: Sequence[_edition_delta_source._Row],
) -> list[_edition_delta_source._Placed]:
    successor: dict[str, object] = {
        **source.table,
        _edition_delta_fields._CASILLAS: tuple(freeze_toml_value(row) for row in stated_rows),
        "casilla_overrides": tuple(freeze_toml_value(override) for override in selection.overrides),
        "casilla_removals": tuple(freeze_toml_value(removal) for removal in removals),
        "casilla_positions": (),
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
        _edition_delta_source._Placed(_edition_delta_source._as_row(row), origin or revision_id)
        for row, origin in zip(merged_rows, merged_origins, strict=True)
    ]


def _restore_positions(
    merged: list[_edition_delta_source._Placed], expected_ids: Sequence[str], revision_id: str, normalise_order: bool
) -> tuple[list[_edition_delta_source._Placed], tuple[_edition_delta_source._Row, ...]]:
    if normalise_order:
        return merged, ()
    positions: list[_edition_delta_source._Row] = []
    for position, expected_id in enumerate(expected_ids):
        current = _current_position(merged, expected_id)
        if current is None:
            raise _edition_delta_errors.MigrationRefusedError(
                f"edition {revision_id!r}: storage delta cannot position casilla {expected_id!r}"
            )
        if current != position:
            merged.insert(position, merged.pop(current))
            positions.append({"id": expected_id, "position": position})
    if [_edition_delta_source._row_id(placed.row) for placed in merged] != list(expected_ids):
        raise _edition_delta_errors.MigrationRefusedError(
            f"edition {revision_id!r}: successor-local positions do not reconstruct casilla order"
        )
    return merged, tuple(positions)


def _current_position(merged: Sequence[_edition_delta_source._Placed], expected_id: str) -> int | None:
    return next(
        (index for index, placed in enumerate(merged) if _edition_delta_source._row_id(placed.row) == expected_id),
        None,
    )


def _verify_materialisation(
    merged: Sequence[_edition_delta_source._Placed],
    full_rows: Sequence[_edition_delta_source._Row],
    attested_lineages: set[str],
    revision_id: str,
    defaults: _edition_delta_source._Defaults,
    declarations: _edition_delta_source._Declarations,
) -> None:
    full_by_id = {_edition_delta_source._row_id(row): row for row in full_rows}
    for placed in merged:
        row = full_by_id[_edition_delta_source._row_id(placed.row)]
        effective = _effective_simulated_row(placed, row, attested_lineages, revision_id, defaults, declarations)
        if effective != row:
            differing = _differing_fields(row, effective)
            raise _edition_delta_errors.MigrationRefusedError(
                f"edition {revision_id!r}: simulated casilla {_edition_delta_source._row_id(row)!r} "
                f"does not reproduce the full copy; differing fields: {differing!r}",
            )


def _effective_simulated_row(
    placed: _edition_delta_source._Placed,
    row: _edition_delta_source._Row,
    attested_lineages: set[str],
    revision_id: str,
    defaults: _edition_delta_source._Defaults,
    declarations: _edition_delta_source._Declarations,
) -> _edition_delta_source._Row | None:
    simulated_row = dict(placed.row)
    if _edition_delta_source._lineage(row) in attested_lineages:
        for claim_field in LINEAGE_CLAIM_FIELDS:
            if claim_field in row:
                simulated_row[claim_field] = row[claim_field]
    return _edition_delta_source._effective(
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
    inherited: Sequence[_edition_delta_source._Placed],
    full_rows: Sequence[_edition_delta_source._Row],
    lifts: Mapping[str, _edition_delta_source._Lift],
    source: _edition_delta_source._EditionSource,
    defaults: _edition_delta_source._Defaults,
    normalise_order: bool,
    storage_only: bool,
    selection: _edition_delta_row_delta_selection.DropSelection,
) -> tuple[
    tuple[_edition_delta_source._Row, ...],
    tuple[_edition_delta_source._Row, ...],
    tuple[str, ...],
]:
    """Replay a selection through the loader merge and return its removals, positions and reconstructed order.

    Refuses when the simulated merge cannot position a row or does not reproduce the full copy.
    """
    removals = _removals(inherited, full_rows, predecessor, storage_only, selection.matched_storage_ids)
    stated = frozenset(_edition_delta_source._row_id(row) for row in full_rows) - selection.drops
    layout = _edition_delta_source._stated_layout(source, stated)
    stated_rows = [lifts[_edition_delta_source._row_id(block.row)].row for _, blocks in layout for block in blocks]
    merged = _simulate_merge(revision_id, predecessor, inherited, source, stated_rows, selection, removals)
    expected_ids = [_edition_delta_source._row_id(row) for row in full_rows]
    merged, positions = _restore_positions(merged, expected_ids, revision_id, normalise_order)
    attested = {str(attestation.continuidad_id) for attestation in selection.attestations}
    _verify_materialisation(merged, full_rows, attested, revision_id, defaults, source.declarations)
    return (
        tuple(removals),
        positions,
        tuple(_edition_delta_source._row_id(placed.row) for placed in merged),
    )
