"""Shared descendant-fact clearing for wizard persistence projections."""

from __future__ import annotations

from collections.abc import Mapping

from ...domain.user_profile import UserProfileFact, UserProfileRecord
from ._descendant_group import DESCENDANTS_COUNT_PAGE_ID

# The descendant fact namespace: indexed rows renta_family.descendiente.{n}.*
# plus the one aggregate the projection still stores.
#
# The Art. 81.2 guardería sum used to belong here too. It is now an
# engine-derived path: nothing writes it, the calculate-time injector recomputes
# it from the per-child figures, and the profile write door refuses a value at
# it. Keeping it in this set made the clearing sweep emit a clear for a path
# that can never be present -- dead work pointed at a retired declaration.
_DESCENDANT_ROW_PREFIX = "renta_family.descendiente."
_DESCENDANT_AGGREGATE_PATHS = frozenset({"renta_family.descendientes_count"})


def _in_descendant_namespace(path: str) -> bool:
    """True when ``path`` is an indexed descendant row or a descendant aggregate."""
    return path.startswith(_DESCENDANT_ROW_PREFIX) or path in _DESCENDANT_AGGREGATE_PATHS


def descendant_clearing_facts(
    record: UserProfileRecord | None,
    answers: Mapping[str, str],
) -> tuple[UserProfileFact, ...]:
    """Return value-cleared facts for descendant rows the projection replaces.

    When the descendant group was reached (its count page carries an
    answer), the projection OWNS the entire ``renta_family.descendiente.*``
    namespace plus the two aggregates: any on-record path the fresh
    projection does not set is stale (a shrunk count, a removed optional
    field) and is cleared with a ``value=None`` fact -- the canonical
    fact-removal mechanism. Without the answer (the group was never part of
    this run) nothing is touched, so a prior descendant fact set survives a
    partial re-persist. This closes the count-shrink desync where
    ``descendant_list_from_facts`` would otherwise scan orphaned indices the
    count no longer covers.

    Args:
        record: The :class:`UserProfileRecord` to scan for stale descendant
            paths, or ``None``.
        answers: The page-keyed canonical answer map for the current run.
    """
    if record is None or DESCENDANTS_COUNT_PAGE_ID not in answers:
        return ()
    from ..user_profile.projections import record_to_path_values
    from ._persistence import descendant_facts_from_answers

    projected = {path for path, _ in descendant_facts_from_answers(answers)}
    existing = record_to_path_values(record)
    return tuple(
        UserProfileFact(path=path, value=None)
        for path in existing
        if _in_descendant_namespace(path) and path not in projected
    )


__all__ = [
    "descendant_clearing_facts",
]
