"""Closed validity windows for registry records that carry their own grounding.

A registry corpus that lives outside a modelo revision has no revision window to
inherit, so a record in one states the span it is asserted over itself.
:class:`ValidityWindow` is that statement, and it is deliberately narrow: two
inclusive dates, both required.

**Why both bounds are required, and why neither may be open.** An omissible
start sorts as :data:`datetime.date.min` in every ordering helper that has ever
been written for this shape, so the first undated row written after any dated one
persists without error and never resolves as effective again -- a partial
adoption that does not announce itself. An omissible end is worse in a different
way: it silently converts "grounded for the years I read" into "grounded until
further notice", which is exactly the claim a registry record must never make by
default. Requiring both makes the span an assertion the author had to type, and
therefore one a gate can hold them to.

**A window is a grounding claim, not a convenience.** The span says the cited
evidence supports the record across it. Widening one is not a formatting change;
it is a new claim about the law, and the gates that read these windows treat it
that way.

The type carries no notion of "now" and no clock. Coverage is asked as a
question about a filing year, because that is the axis the registry corpora are
selected on.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from pydantic import BaseModel, model_validator

from .models import STRICT_FROZEN_CONFIG


class ValidityWindow(BaseModel):
    """The closed, inclusive date span over which a grounded record is asserted.

    Attributes:
        valid_from: First date the record is asserted to hold. Required.
        valid_to: Last date the record is asserted to hold, inclusive. Required.
    """

    model_config = STRICT_FROZEN_CONFIG

    valid_from: date
    valid_to: date

    @model_validator(mode="after")
    def _span_runs_forwards(self) -> ValidityWindow:
        """Refuse a window that ends before it starts.

        An inverted span covers nothing, so every coverage question over it
        answers ``False`` and the record silently disappears from every year
        rather than failing where it was written.
        """
        if self.valid_to < self.valid_from:
            raise ValueError(
                f"validity window ends before it starts: valid_from={self.valid_from.isoformat()} "
                f"valid_to={self.valid_to.isoformat()}",
            )
        return self

    def covers(self, moment: date) -> bool:
        """Return whether ``moment`` falls inside the closed span.

        Returns:
            ``True`` when ``moment`` is on or after :attr:`valid_from` and on or
            before :attr:`valid_to`.
        """
        return self.valid_from <= moment <= self.valid_to

    def covers_year(self, year: int) -> bool:
        """Return whether the span overlaps any part of the filing ``year``.

        Overlap rather than containment is the right question: a provision that
        takes effect in July is in force for that filing year, and a window
        clipped to its own effective date would otherwise report the year
        uncovered.

        Returns:
            ``True`` when the span intersects ``year``.
        """
        return self.valid_from.year <= year <= self.valid_to.year

    def years(self) -> tuple[int, ...]:
        """Return every filing year the span touches, ascending.

        Returns:
            The years from :attr:`valid_from` to :attr:`valid_to` inclusive.
        """
        return tuple(range(self.valid_from.year, self.valid_to.year + 1))


def years_covered_by_any(windows: Iterable[ValidityWindow]) -> frozenset[int]:
    """Return every filing year at least one window touches.

    Returns:
        The union of each window's :meth:`ValidityWindow.years`.
    """
    covered: set[int] = set()
    for window in windows:
        covered.update(window.years())
    return frozenset(covered)


def years_covered_by_every_group(groups: Iterable[Iterable[ValidityWindow]]) -> frozenset[int]:
    """Return the years every group covers with at least one of its windows.

    A corpus is resolvable for a year only when *each* of its grounded records
    has evidence for that year, so the corpus-level answer is an intersection of
    per-record unions rather than one flat union. A single record whose evidence
    stops earlier stops the whole corpus, which is the honest reading: the
    corpus cannot be assembled for that year.

    An empty group contributes no years and therefore empties the result, which
    is correct -- a record with no window at all is grounded nowhere. An empty
    sequence of groups yields the empty set rather than "everything".

    Returns:
        The intersection across groups of the years each group covers.
    """
    covered: frozenset[int] | None = None
    for group in groups:
        group_years = years_covered_by_any(group)
        covered = group_years if covered is None else (covered & group_years)
        if not covered:
            return frozenset[int]()
    return covered if covered is not None else frozenset[int]()


__all__ = [
    "ValidityWindow",
    "years_covered_by_any",
    "years_covered_by_every_group",
]
