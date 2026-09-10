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


def period_selectors_overlap(left: PeriodSelector, right: PeriodSelector) -> bool:
    """Whether the two selectors share a year range and at least one period code."""
    left_start, left_end = _period_selector_year_bounds(left)
    right_start, right_end = _period_selector_year_bounds(right)
    if left_end is not None and left_end < right_start:
        return False
    if right_end is not None and right_end < left_start:
        return False
    return bool(set(left.periods).intersection(right.periods))
