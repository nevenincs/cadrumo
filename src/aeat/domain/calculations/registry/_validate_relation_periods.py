"""Relation selector helpers for resolving revision and period coverage.

The helpers select source :class:`ModeloRevision` entries from a
:class:`ModeloDefinition` and verify that their period selectors cover the
target relation window.
"""

from __future__ import annotations

from collections.abc import Iterable

from ._schema import ModeloDefinition, ModeloRevision, PeriodSelector, RelationRevisionSelector


def select_relation_source_revisions(
    modelo: ModeloDefinition,
    selector: RelationRevisionSelector,
) -> tuple[tuple[ModeloRevision, ...], list[str]]:
    selected = tuple(
        revision
        for revision in modelo.revisions.values()
        if _relation_source_revision_matches(
            revision,
            year=selector.year,
            year_from=selector.year_from,
            year_to=selector.year_to,
        )
    )
    return selected, []


def relation_filing_year_delta(selector: RelationRevisionSelector) -> int:
    return selector.filing_year_delta or 0


def relation_fixed_source_year(selector: RelationRevisionSelector) -> int | None:
    return selector.year


def validate_source_year_coverage(
    scope: str,
    *,
    target_selector: PeriodSelector,
    source_revisions: Iterable[ModeloRevision],
    source_periods: Iterable[str],
    filing_year_delta: int,
    fixed_source_year: int | None = None,
    source_is_observation_history: bool = False,
) -> list[str]:
    """Verify source-year coverage, with observation history requiring only shape coverage.

    Candidate :class:`ModeloRevision` entries are filtered by source-period
    shape before their year intervals are compared with the target selector.
    """
    source_period_set = set(source_periods)
    period_matching_revisions = tuple(
        source_revision
        for source_revision in source_revisions
        if not source_period_set or source_period_set.issubset(set(source_revision.period_selector.periods))
    )
    if source_is_observation_history:
        if source_period_set and not period_matching_revisions:
            return [
                f"{scope} previous-filing source declares periods {sorted(source_period_set)!r} "
                f"that no source revision covers",
            ]
        return []
    if fixed_source_year is None:
        required_intervals = tuple(
            (start + filing_year_delta, None if end is None else end + filing_year_delta)
            for start, end in _selector_year_intervals(target_selector)
        )
    else:
        required_intervals = ((fixed_source_year, fixed_source_year),)
    covered_intervals = tuple(
        interval
        for source_revision in period_matching_revisions
        for interval in _selector_year_intervals(source_revision.period_selector)
    )
    failures: list[str] = []
    for start, end in required_intervals:
        if not _interval_is_covered(start, end, covered_intervals):
            if end is None:
                failures.append(f"{scope} lacks source revision year coverage from {start}")
            elif start == end:
                failures.append(f"{scope} lacks source revision year coverage for {start}")
            else:
                failures.append(f"{scope} lacks source revision year coverage for {start}-{end}")
    return failures


def period_selectors_overlap(left: PeriodSelector, right: PeriodSelector) -> bool:
    if not set(left.periods).intersection(right.periods):
        return False
    return _year_selectors_overlap(left, right)


def _relation_source_revision_matches(
    revision: ModeloRevision,
    *,
    year: int | None,
    year_from: int | None,
    year_to: int | None,
) -> bool:
    if year is not None and not revision.period_selector.includes_year(year):
        return False
    return year_from is None or _revision_intersects_year_range(
        revision,
        year_from=year_from,
        year_to=year_to,
    )


def _selector_year_intervals(selector: PeriodSelector) -> tuple[tuple[int, int | None], ...]:
    if selector.years:
        return tuple((year, year) for year in sorted(selector.years))
    if selector.year_from is None:
        return ()
    return ((selector.year_from, selector.year_to),)


def _interval_is_covered(
    start: int,
    end: int | None,
    intervals: Iterable[tuple[int, int | None]],
) -> bool:
    remaining_start = start
    for covered_start, covered_end in sorted(intervals, key=lambda item: item[0]):
        if covered_start > remaining_start:
            continue
        if covered_end is None:
            return True
        if covered_end < remaining_start:
            continue
        remaining_start = covered_end + 1
        if end is not None and remaining_start > end:
            return True
    return False if end is None else remaining_start > end


def _revision_intersects_year_range(
    revision: ModeloRevision,
    *,
    year_from: int,
    year_to: int | None,
) -> bool:
    if revision.period_selector.years:
        years = revision.period_selector.years
        return any(year >= year_from and (year_to is None or year <= year_to) for year in years)
    revision_from = revision.period_selector.year_from
    if revision_from is None:
        return False
    revision_to = revision.period_selector.year_to
    if revision_to is not None and revision_to < year_from:
        return False
    return not (year_to is not None and revision_from > year_to)


def _year_selectors_overlap(left: PeriodSelector, right: PeriodSelector) -> bool:
    if left.years and right.years:
        return bool(set(left.years).intersection(right.years))
    if left.years:
        return any(right.includes_year(year) for year in left.years)
    if right.years:
        return any(left.includes_year(year) for year in right.years)
    left_from, right_from = left.year_from, right.year_from
    if left_from is None or right_from is None:
        return False
    left_to, right_to = left.year_to, right.year_to
    if left_to is not None and left_to < right_from:
        return False
    return not (right_to is not None and right_to < left_from)
