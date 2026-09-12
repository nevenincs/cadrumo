"""Whether two period selectors could both be live at once.

The primitive every revision-overlap decision keys on. It reads selectors
only, so the modelo schema's own validators and the revision-ordering helpers
built over typed revisions share one definition of overlap.
"""

from __future__ import annotations

from .schema_references import PeriodSelector

__all__ = ("period_selectors_overlap",)


def _period_selector_year_bounds(selector: PeriodSelector) -> tuple[int, int | None]:
    if selector.years:
        return min(selector.years), max(selector.years)
    if selector.year_from is None:
        return 0, None
    return selector.year_from, selector.year_to


def _overridden_years(left: PeriodSelector, right: PeriodSelector) -> tuple[int, ...]:
    return tuple(sorted({override.year for selector in (left, right) for override in selector.period_overrides}))


def period_selectors_overlap(left: PeriodSelector, right: PeriodSelector) -> bool:
    """Whether the two selectors share a filing year and at least one period code in it.

    Overrides make the shared period surface year-dependent, so the shared
    years are decided in two bands rather than one. Each overridden year either
    side names is tested on its own surface, and the remaining shared years --
    where both selectors serve their flat tuple -- are tested once, which keeps
    the decision finite for an open-ended ``year_from`` range.
    """
    left_start, left_end = _period_selector_year_bounds(left)
    right_start, right_end = _period_selector_year_bounds(right)
    if left_end is not None and left_end < right_start:
        return False
    if right_end is not None and right_end < left_start:
        return False
    overridden = _overridden_years(left, right)
    if any(
        left.includes_year(year)
        and right.includes_year(year)
        and set(left.periods_for_year(year)).intersection(right.periods_for_year(year))
        for year in overridden
    ):
        return True
    if not overridden:
        return bool(set(left.periods).intersection(right.periods))
    # The shared span still holds a year neither selector overrides whenever it
    # is wider than the overridden set, and there both serve their flat tuples.
    shared_start = max(left_start, right_start)
    declared_ends = [end for end in (left_end, right_end) if end is not None]
    shared_end = min(declared_ends) if declared_ends else None
    if shared_end is not None:
        shared_years = {
            year
            for year in range(shared_start, shared_end + 1)
            if left.includes_year(year) and right.includes_year(year)
        }
        if shared_years.issubset(overridden):
            return False
    return bool(set(left.periods).intersection(right.periods))
