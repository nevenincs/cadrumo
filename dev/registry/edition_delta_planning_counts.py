"""Count defaulted fields actually lifted from stated casilla rows."""

from __future__ import annotations

from collections.abc import Mapping

from . import edition_delta_fields as _edition_delta_fields
from . import edition_delta_source as _edition_delta_source
from . import edition_delta_types as _edition_delta_types


def lift_counts(
    source: _edition_delta_source._EditionSource,
    lifts: Mapping[str, _edition_delta_source._Lift],
    stated_ids: frozenset[str],
) -> _edition_delta_types.LiftCounts:
    """Count only keys the edition authors on the rows it keeps stating."""
    authored = {_edition_delta_source._row_id(row): row for row in source.stated_rows()}
    return _edition_delta_types.LiftCounts(
        row_source_refs=_count_key(_edition_delta_fields._ROW_SOURCE, False, authored, lifts, stated_ids),
        constraint_source_refs=_count_key(_edition_delta_fields._ROW_SOURCE, True, authored, lifts, stated_ids),
        row_orden_legal_refs=_count_key(_edition_delta_fields._ROW_LEGAL, False, authored, lifts, stated_ids),
        constraint_orden_legal_refs=_count_key(_edition_delta_fields._ROW_LEGAL, True, authored, lifts, stated_ids),
    )


def _count_key(
    key: str,
    constraint: bool,
    authored: Mapping[str, _edition_delta_source._Row],
    lifts: Mapping[str, _edition_delta_source._Lift],
    stated_ids: frozenset[str],
) -> int:
    total = 0
    for row_id in stated_ids:
        row = authored.get(row_id, {})
        table = row.get(_edition_delta_fields._CONSTRAINTS) if constraint else row
        keys = lifts[row_id].constraint_lift.removed if constraint else lifts[row_id].row_lift.removed
        total += key in keys and isinstance(table, dict) and key in table
    return total
