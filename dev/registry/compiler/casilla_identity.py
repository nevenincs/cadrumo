"""Identify raw casilla rows by declaration id and continuity lineage."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from dev.registry.compiler._toml_helpers import as_toml_table as _as_toml_table

#: The row fields that state its relationship to the immediately preceding edition.
LINEAGE_CLAIM_FIELDS: Final = frozenset({"continuidad_origin", "continuidad_evidence"})


def _same_casilla_identity(
    before: object,
    after: object,
    inherited_by_id: Mapping[str, tuple[object, ...]],
    successor_by_id: Mapping[str, tuple[object, ...]],
) -> bool:
    """Compare unique declared concepts, retaining exact ids only for unchained rows.

    Equal box numbers do not override contradictory continuity. A renumbering
    requires a unique, shared chain on both ends; absent or ambiguous targets
    cannot establish identity.
    """
    before_rows = inherited_by_id.get(before, ()) if isinstance(before, str) else ()
    after_rows = successor_by_id.get(after, ()) if isinstance(after, str) else ()
    if before == after and not before_rows and not after_rows:
        return True
    if len(before_rows) != 1 or len(after_rows) != 1:
        return False
    return _unique_rows_have_same_identity(before, after, before_rows[0], after_rows[0])


def _unique_rows_have_same_identity(before: object, after: object, before_row: object, after_row: object) -> bool:
    before_lineage = _row_lineage(before_row)
    after_lineage = _row_lineage(after_row)
    if before_lineage is not None or after_lineage is not None:
        return before_lineage is not None and before_lineage == after_lineage
    return before == after


def _casillas_by_id(rows: tuple[object, ...]) -> dict[str, tuple[object, ...]]:
    """Index casillas once while retaining duplicate rows for ambiguity checks."""
    grouped: dict[str, list[object]] = {}
    for row in rows:
        row_id = _row_id(row)
        if row_id is not None:
            grouped.setdefault(row_id, []).append(row)
    return {row_id: tuple(matches) for row_id, matches in grouped.items()}


def _row_lineage(row: object) -> str | None:
    table = _as_toml_table(row)
    lineage = None if table is None else table.get("continuidad_id")
    return lineage if isinstance(lineage, str) else None


def _row_id(row: object) -> str | None:
    table = _as_toml_table(row)
    row_id = None if table is None else table.get("id")
    return row_id if isinstance(row_id, str) else None
