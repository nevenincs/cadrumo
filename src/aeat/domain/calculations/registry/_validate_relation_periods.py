"""Relation selector helpers for resolving revision and period coverage.

The helpers select source :class:`ModeloRevision` entries from a
:class:`ModeloDefinition` and verify that their period selectors cover the
target relation window.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ._schema import ModeloDefinition, ModeloRevision, PeriodSelector


def select_relation_source_revisions(
    modelo: ModeloDefinition,
    selector: Mapping[str, str | int],
) -> tuple[tuple[ModeloRevision, ...], list[str]]:
    failures = _validate_relation_source_selector_keys(selector)
    revision_id = selector.get("revision_id", selector.get("revision"))
    year = selector.get("year")
    year_from = selector.get("year_from")
    year_to = selector.get("year_to")
    selected = tuple(
        revision
        for revision in modelo.revisions.values()
        if _relation_source_revision_matches(
            revision,
            revision_id=revision_id if isinstance(revision_id, str) else None,
            year=year if isinstance(year, int) else None,
            year_from=year_from if isinstance(year_from, int) else None,
            year_to=year_to if isinstance(year_to, int) else None,
        )
    )
    return selected, failures


def relation_filing_year_delta(selector: Mapping[str, str | int]) -> int:
    delta = 0 if "year" in selector else selector.get("filing_year_delta", 0)
    return delta if isinstance(delta, int) else 0


def relation_fixed_source_year(selector: Mapping[str, str | int]) -> int | None:
    year = selector.get("year")
    return year if isinstance(year, int) else None


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


def _validate_relation_source_selector_keys(selector: Mapping[str, str | int]) -> list[str]:
    """Return every shape failure on the relation source-revision selector dict."""
    allowed = {"revision", "revision_id", "year", "year_from", "year_to", "filing_year_delta"}
    failures = [f"selector uses unknown key {key!r}" for key in sorted(set(selector).difference(allowed))]
    revision_id = selector.get("revision_id", selector.get("revision"))
    if revision_id is not None and not isinstance(revision_id, str):
        failures.append("selector revision_id must be a string")
    for key in ("year", "year_from", "year_to"):
        value = selector.get(key)
        if value is not None and not isinstance(value, int):
            failures.append(f"selector {key} must be an integer")
    delta = selector.get("filing_year_delta")
    if delta is not None and not isinstance(delta, int):
        failures.append("selector filing_year_delta must be an integer")
    year = selector.get("year")
    year_from = selector.get("year_from")
    year_to = selector.get("year_to")
    if year is not None and (year_from is not None or year_to is not None):
        failures.append("selector must use year or year_from/year_to, not both")
    if year_to is not None and year_from is None:
        failures.append("selector year_to requires year_from")
    if isinstance(year_from, int) and isinstance(year_to, int) and year_to < year_from:
        failures.append("selector year_to must be on or after year_from")
    return failures


def _relation_source_revision_matches(
    revision: ModeloRevision,
    *,
    revision_id: str | None,
    year: int | None,
    year_from: int | None,
    year_to: int | None,
) -> bool:
    if revision_id is not None and revision.id != revision_id:
        return False
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
        return any(
            year >= year_from and (year_to is None or year <= year_to) for year in revision.period_selector.years
        )
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
    left_from = left.year_from
    right_from = right.year_from
    if left_from is None or right_from is None:
        return False
    left_to = left.year_to
    right_to = right.year_to
    if left_to is not None and left_to < right_from:
        return False
    return not (right_to is not None and right_to < left_from)
