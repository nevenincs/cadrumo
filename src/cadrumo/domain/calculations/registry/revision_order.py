"""Modelo revision ordering, period-selector overlap, and temporal coexistence.

Orders a :class:`ModeloDefinition`'s revisions into validity sequence and
offers the two distinct "are these two revisions the same period" questions
that cross-revision policy keys on: :func:`revisions_overlap`, which reads
period selectors alone, and :func:`revisions_coexist`, which additionally
requires the revisions' validity windows to intersect.
"""

from __future__ import annotations

from .period_selector_overlap import period_selectors_overlap
from .schema import ModeloDefinition, ModeloRevision

__all__ = ("ordered_revisions", "revision_windows_intersect", "revisions_coexist", "revisions_overlap")


def revisions_overlap(left: ModeloRevision, right: ModeloRevision) -> bool:
    """Whether two revisions' declared period selectors address a common period.

    This is a selector-only question: it asks whether the two revisions name
    at least one shared filing year and period code, and says NOTHING about
    when either revision is in force. Two consecutive editions of a modelo
    that serve the same period vocabulary -- successive census editions both
    serving ``alta``/``modificacion``/``baja``, or successive ad-hoc editions
    both serving ``AD-HOC`` -- overlap under this predicate even when their
    validity windows merely meet end-to-start and can never be live at the
    same time. Callers asking "could both of these be in force at once"
    want :func:`revisions_coexist` instead.

    ``ModeloRevision.period_selector`` is a REQUIRED field (never ``None``),
    and every caller passes real, fully-constructed :class:`ModeloRevision`
    instances; no production code builds a ``ModeloRevision`` via
    ``model_construct``. Reading ``.period_selector`` directly (never
    ``getattr(..., default=None)`` guarded by an ``isinstance`` fallback to
    ``True``) means a rename of the field fails loud instead of silently
    making every revision pair register as "overlapping" -- which is NOT a
    safe default here, because consumers that only run their own check when a
    pair does NOT overlap would be silently disabled, with nothing downstream
    to catch the loss.
    """
    return period_selectors_overlap(left.period_selector, right.period_selector)


def revision_windows_intersect(left: ModeloRevision, right: ModeloRevision) -> bool:
    """Whether two revisions' inclusive validity windows share at least one day.

    This is the project's single answer to "are these two revisions ever in
    force on the same day", and it says NOTHING about period selectors; pair
    it with :func:`revisions_overlap` -- or use :func:`revisions_coexist`,
    which is exactly that conjunction -- when the question is simultaneity for
    one and the same period.

    Inclusivity: ``valid_from`` and ``valid_to`` are both inclusive bounds, so
    a revision is in force ON its ``valid_to`` date. Two windows that merely
    MEET end-to-start -- one ending 2025-02-02 and the next starting
    2025-02-03 -- therefore do NOT intersect, while two that share a single
    day (``valid_to == valid_from``) DO.

    Open ends: ``valid_to`` of ``None`` denotes an open-ended window with no
    end date. An open-ended revision intersects every window that starts on or
    after its ``valid_from``, and every window that has not itself closed
    before that ``valid_from``. ``valid_from`` is required and never ``None``,
    so there is no open START to consider.

    The predicate is symmetric: ``f(a, b)`` equals ``f(b, a)`` for every pair,
    and argument order carries no "earlier"/"later" meaning. It assumes each
    revision's own window is well formed (``valid_to`` not before
    ``valid_from``); a schema-invalid inverted window is not defended against
    here, because the schema is the owner of that invariant.
    """
    if left.valid_to is not None and left.valid_to < right.valid_from:
        return False
    return not (right.valid_to is not None and right.valid_to < left.valid_from)


def revisions_coexist(left: ModeloRevision, right: ModeloRevision) -> bool:
    """Whether two revisions could both be in force for one and the same period.

    The conjunction of the two independent conditions that must both hold for
    a genuine simultaneity: the revisions' inclusive validity windows
    intersect (``valid_to`` of ``None`` meaning open-ended) AND their period
    selectors address a common period. Variant schemas that share a validity
    window are alternative shapes of one period and coexist; successive
    editions whose windows only meet end-to-start do not, however identical
    their period vocabularies happen to be.

    This is the predicate for policy that asks "is this pair simultaneous, or
    is it a real temporal succession". :func:`revisions_overlap` answers only
    the selector half and reports successive editions of a stable period
    vocabulary as overlapping.
    """
    return revision_windows_intersect(left, right) and revisions_overlap(left, right)


def ordered_revisions(modelo: ModeloDefinition) -> tuple[ModeloRevision, ...]:
    """Return a modelo's revisions in validity order, ties broken by id."""
    return tuple(
        sorted(modelo.revisions.values(), key=lambda revision: (revision.valid_from, revision.id)),
    )
