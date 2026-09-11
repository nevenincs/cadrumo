"""Modelo revision ordering and period-overlap detection.

Orders a :class:`ModeloDefinition`'s revisions into validity sequence and
decides whether two revisions' declared period selectors could both be live
at once. Cross-revision divergence detection, evolution and contiguity
policy, and lineage-origin resolution all key their own checks on these two
primitives.
"""

from __future__ import annotations

from .period_selector_overlap import period_selectors_overlap
from .schema import ModeloDefinition, ModeloRevision

__all__ = ("ordered_revisions", "revisions_overlap")


def revisions_overlap(left: ModeloRevision, right: ModeloRevision) -> bool:
    """Whether two revisions' declared period selectors could both be live at once.

    ``ModeloRevision.period_selector`` is a REQUIRED field (never ``None``),
    and every real caller (all three: :func:`_pair_field_divergences`,
    ``validate_cross_revision.py``'s ``_period_overlap_requires_evolution``,
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
    return period_selectors_overlap(left.period_selector, right.period_selector)


def ordered_revisions(modelo: ModeloDefinition) -> tuple[ModeloRevision, ...]:
    """Return a modelo's revisions in validity order, ties broken by id."""
    return tuple(
        sorted(modelo.revisions.values(), key=lambda revision: (revision.valid_from, revision.id)),
    )
