"""Every edition of one governed fact that the registry's support envelope crosses.

A dated read resolves a fact at the date its caller holds. A dateless read, such
as admitting a vocabulary token before the record it belongs to has a date,
must not substitute the run date: the same input would then be admitted or
refused depending on when the program runs. Such a read asks instead which
editions the fact authors anywhere inside the supported filing years, and the
dated read made later refuses a value its own date does not carry.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

from ..errors import GovernedFactNotApplicableError
from ..governed_fact_scope import GovernedFactSource
from .resolution import GovernedFactQuery, ResolvedGovernedFact

_ONE_DAY = timedelta(days=1)


def resolve_support_envelope_editions(
    authority: GovernedFactSource,
    query_on: Callable[[date], GovernedFactQuery],
) -> tuple[ResolvedGovernedFact, ...]:
    """Resolve one fact at every edition window inside the support envelope, oldest first.

    The walk starts at the envelope's first date and moves from each resolved
    window to the day after it ends, so a window that changes mid-year is read
    as its own edition. A date no window holds is stepped over one day at a
    time. Without a hard ceiling the envelope stays open above its horizon, so
    an authored window that closes there is followed while its successor is
    contiguous; with a hard ceiling the walk stops at it.

    ``query_on`` builds the fact's query for one effective date; the caller
    keeps the fact identity, axis and selectors.
    """
    envelope = authority.supported_filing_years().date_envelope()
    last = envelope.horizon if envelope.hard_ceiling is None else envelope.hard_ceiling
    editions: dict[str, ResolvedGovernedFact] = {}
    cursor: date | None = envelope.floor
    while cursor is not None and (cursor <= last or envelope.hard_ceiling is None):
        try:
            resolved = authority.resolve_governed_fact(query_on(cursor))
        except GovernedFactNotApplicableError:
            cursor = cursor + _ONE_DAY if cursor < last else None
            continue
        editions.setdefault(resolved.variant_id, resolved)
        cursor = _next_coordinate(resolved, cursor, last=last)
    return tuple(editions.values())


def _next_coordinate(resolved: ResolvedGovernedFact, cursor: date, *, last: date) -> date | None:
    """Return the first date after ``resolved``'s window, or ``None`` when the walk is done."""
    if not resolved.published_on_date:
        # A standing track answers a date no window holds from its nearest
        # edition. That edition is recorded; the walk resumes at it when it lies
        # ahead, steps a day while inside the envelope, and ends above it.
        if resolved.valid_from > cursor:
            return resolved.valid_from
        return cursor + _ONE_DAY if cursor < last else None
    if resolved.valid_to is None:
        return None
    return resolved.valid_to + _ONE_DAY


__all__ = ["resolve_support_envelope_editions"]
