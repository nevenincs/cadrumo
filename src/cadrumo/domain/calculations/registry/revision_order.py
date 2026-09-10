"""Modelo revision ordering and period-overlap detection.

Orders a :class:`ModeloDefinition`'s revisions into validity sequence and
decides whether two revisions' declared period selectors could both be live
at once. Cross-revision divergence detection, evolution and contiguity
policy, and lineage-origin resolution all key their own checks on these two
primitives.
"""

from __future__ import annotations

from .schema import ModeloDefinition, ModeloRevision
from .schema_references import PeriodSelector

__all__ = ("ordered_revisions", "revisions_overlap")


def _period_selector_year_bounds(selector: PeriodSelector) -> tuple[int, int | None]:
    if selector.years:
        return min(selector.years), max(selector.years)
    if selector.year_from is None:
        return 0, None
    return selector.year_from, selector.year_to


def _period_selectors_overlap(left: PeriodSelector, right: PeriodSelector) -> bool:
    left_start, left_end = _period_selector_year_bounds(left)
    right_start, right_end = _period_selector_year_bounds(right)
    if left_end is not None and left_end < right_start:
        return False
    if right_end is not None and right_end < left_start:
        return False
    return bool(set(left.periods).intersection(right.periods))


def revisions_overlap(left: ModeloRevision, right: ModeloRevision) -> bool:
    """Whether two revisions' declared period selectors could both be live at once.

    ``ModeloRevision.period_selector`` is a REQUIRED field (never ``None``),
    and every real caller (all three: :func:`_pair_field_divergences`,
    ``_validate_cross_revision.py``'s ``_period_overlap_requires_evolution``,
    ``_validate_cross_revision_contiguity.py``'s ``_skipped_revisions``)
    always passes real, fully-constructed :class:`ModeloRevision` instances --
    confirmed by reading each call site, and no production code ever builds a
    ``ModeloRevision`` via ``model_construct``. Reading ``.period_selector``
    directly (never ``getattr(..., default=None)`` guarded by an
    ``isinstance`` fallback to ``True``) means a rename of the field fails
    loud instead of silently making every revision pair register as
    "overlapping" -- which is NOT a safe default here: three of the four
    consumers only run their own check when a pair does NOT overlap (the
    strict continuity-evolution requirement, the continuity-coverage
    advisory, and the contiguity gap detector this whole module's own
    docstring says exists to catch "a chain which is present, absent, then
    present again"), so a permanent ``True`` would silently disable all
    three, with nothing downstream to catch the loss.
    """
    return _period_selectors_overlap(left.period_selector, right.period_selector)


def ordered_revisions(modelo: ModeloDefinition) -> tuple[ModeloRevision, ...]:
    """Return a modelo's revisions in validity order, ties broken by id."""
    return tuple(
        sorted(modelo.revisions.values(), key=lambda revision: (revision.valid_from, revision.id)),
    )
