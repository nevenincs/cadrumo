"""The rule deciding an edition's shared ``source_refs`` default, with no registry imports.

The migration tool declares a family default on the manifest and the status
screen counts which members that default would lift. Both must apply one rule,
and the screen must keep measuring when the registry domain cannot be imported,
so the rule lives here on its own and depends on nothing but the standard
library.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Final

__all__ = ["edition_source_default"]

_ROW_SOURCE: Final = "source_refs"
_CONSTRAINTS: Final = "constraints"


def _source_refs(table: Mapping[str, object]) -> tuple[str, ...] | None:
    value = table.get(_ROW_SOURCE)
    return tuple(str(item) for item in value) if isinstance(value, list) else None


def edition_source_default(rows: Sequence[Mapping[str, object]]) -> tuple[tuple[str, ...] | None, str | None]:
    """The edition's shared leading ``source_refs`` run, or ``None`` and the reason none is declared.

    A default is declared when every row and constraints table states some
    ``source_refs`` and one leading run of references opens the ``source_refs``
    of more rows than any other, and of at least two; among runs opening
    equally many rows the longest is taken, and two distinct runs of that
    length are a tie and declare nothing. A run counts for a row only when the
    row's references open with it and repeat nothing, so the default followed
    by the rest reproduces them exactly.
    """
    constraints = [table for row in rows if isinstance(table := row.get(_CONSTRAINTS), dict)]
    if any(_ROW_SOURCE not in table for table in [*rows, *constraints]):
        return None, "a row or constraints table states no source_refs, so a default would add references to it"
    scores: Counter[tuple[str, ...]] = Counter()
    for row in rows:
        refs = _source_refs(row)
        if refs and len(set(refs)) == len(refs):
            scores.update(refs[:length] for length in range(1, len(refs) + 1))
    if not scores or max(scores.values()) < 2:
        return None, "no leading source_refs run is shared by two rows"
    best = max(scores.values())
    longest = max(len(run) for run, score in scores.items() if score == best)
    candidates = sorted(run for run, score in scores.items() if score == best and len(run) == longest)
    if len(candidates) > 1:
        return None, f"{len(candidates)} leading source_refs runs of length {longest} tie at {best} rows"
    return candidates[0], None
