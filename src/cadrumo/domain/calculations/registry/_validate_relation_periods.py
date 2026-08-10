"""Relation selector helpers for resolving revision and period coverage.

The helpers select source :class:`ModeloRevision` entries from a
:class:`ModeloDefinition` and verify that their period selectors cover the
target relation window.
"""

from __future__ import annotations

from collections.abc import Iterable

from ._errors import RegistryValidationError
from ._period_offset_math import apply_period_offset
from ._schema import ModeloDefinition, ModeloRevision, PeriodSelector, RelationDefinition, RelationRevisionSelector


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


def validate_relation_source_coordinate_coverage(
    scope: str,
    *,
    relation: RelationDefinition,
    target_selector: PeriodSelector,
    source_revisions: Iterable[ModeloRevision],
    source_periods: Iterable[str],
    source_is_observation_history: bool,
) -> tuple[tuple[tuple[ModeloRevision, tuple[str, ...]], ...], list[str]]:
    """Resolve exact source-revision ownership for a cross-model relation.

    A source model may partition one year across multiple revisions. Validate
    every declared or offset-derived ``(source year, source period)``
    coordinate against the *union* of those revisions, requiring exactly one
    owner for each in-modelled coordinate.

    ``source_revisions`` is the set of :class:`ModeloRevision` the source model
    partitions its years across; ownership is resolved against their union
    rather than against any one of them.

    The sole history boundary is generic: an observation-backed carry can read
    a filing before the earliest modelled source year.  That filing still has
    to use a known period shape and semantic casilla (checked by the caller),
    but it cannot be required to have an engine revision that predates the
    modelled registry.
    """
    candidates = tuple(source_revisions)
    covered_periods_by_revision: dict[str, set[str]] = {}
    revisions_by_id = {revision.id: revision for revision in candidates}
    failures: list[str] = []

    coordinates: tuple[tuple[str, int, str | None], ...]
    if relation.source_period_offset_from_target is None:
        coordinates = tuple((source_period, 0, None) for source_period in source_periods)
    else:
        derived_coordinates: list[tuple[str, int, str | None]] = []
        for target_period in relation.target_periods:
            try:
                offset_year_delta, source_period = apply_period_offset(
                    relation.source_period_offset_from_target,
                    target_period=target_period,
                )
            except RegistryValidationError:
                # The sibling period-shape validation reports this with the
                # relation id and target-period context.
                continue
            derived_coordinates.append((source_period, offset_year_delta, target_period))
        coordinates = tuple(derived_coordinates)

    for source_period, offset_year_delta, target_period in coordinates:
        period_candidates = tuple(
            revision for revision in candidates if source_period in revision.period_selector.periods
        )
        if not period_candidates:
            target_context = "" if target_period is None else f" for target period {target_period!r}"
            failures.append(
                f"{scope} derived source period {source_period!r}{target_context} "
                "is not supported by any selected source revision",
            )
            continue

        for source_start, source_end in _offset_source_year_intervals(
            target_selector,
            relation=relation,
            offset_year_delta=offset_year_delta,
        ):
            for segment_start, segment_end, owners in _coverage_segments(
                source_start,
                source_end,
                period_candidates,
            ):
                if len(owners) == 1:
                    covered_periods_by_revision.setdefault(owners[0].id, set()).add(source_period)
                    continue
                if (
                    not owners
                    and source_is_observation_history
                    and _is_pre_modelled_history(segment_end, period_candidates)
                ):
                    # There is no engine revision for this historical filing.
                    # Attach the period to the earliest compatible revision so
                    # the caller still checks the canonical source casilla.
                    earliest = min(
                        period_candidates,
                        key=lambda revision: _earliest_selector_year(revision.period_selector),
                    )
                    covered_periods_by_revision.setdefault(earliest.id, set()).add(source_period)
                    continue
                coverage = "lacks" if not owners else "has ambiguous"
                failures.append(
                    f"{scope} {coverage} exact source revision coverage for derived "
                    f"period {source_period!r} in source years {_year_interval_label(segment_start, segment_end)}",
                )

    coverage = tuple(
        (revisions_by_id[revision_id], tuple(sorted(periods)))
        for revision_id, periods in sorted(covered_periods_by_revision.items())
    )
    return coverage, failures


def period_selectors_overlap(left: PeriodSelector, right: PeriodSelector) -> bool:
    if not set(left.periods).intersection(right.periods):
        return False
    return _year_selectors_overlap(left, right)


def _offset_source_year_intervals(
    target_selector: PeriodSelector,
    *,
    relation: RelationDefinition,
    offset_year_delta: int,
) -> tuple[tuple[int, int | None], ...]:
    selector = relation.source_revision_selector
    if selector.year is not None:
        source_year = selector.year + offset_year_delta
        return ((source_year, source_year),)
    filing_year_delta = relation_filing_year_delta(selector) + offset_year_delta
    return tuple(
        (start + filing_year_delta, None if end is None else end + filing_year_delta)
        for start, end in _selector_year_intervals(target_selector)
    )


def _coverage_segments(
    start: int,
    end: int | None,
    candidates: tuple[ModeloRevision, ...],
) -> tuple[tuple[int, int | None, tuple[ModeloRevision, ...]], ...]:
    """Return maximal year segments with a stable set of revision owners."""
    boundaries = {start}
    if end is not None:
        boundaries.add(end + 1)
    for revision in candidates:
        for candidate_start, candidate_end in _selector_year_intervals(revision.period_selector):
            if candidate_start > start and (end is None or candidate_start <= end):
                boundaries.add(candidate_start)
            if candidate_end is not None:
                after_candidate = candidate_end + 1
                if after_candidate > start and (end is None or after_candidate <= end):
                    boundaries.add(after_candidate)
    ordered_boundaries = sorted(boundaries)
    segments: list[tuple[int, int | None, tuple[ModeloRevision, ...]]] = []
    for index, segment_start in enumerate(ordered_boundaries):
        if end is not None and segment_start > end:
            continue
        next_boundary = ordered_boundaries[index + 1] if index + 1 < len(ordered_boundaries) else None
        segment_end = end if next_boundary is None else next_boundary - 1
        owners = tuple(revision for revision in candidates if revision.period_selector.includes_year(segment_start))
        segments.append((segment_start, segment_end, owners))
    return tuple(segments)


def _is_pre_modelled_history(end: int | None, candidates: tuple[ModeloRevision, ...]) -> bool:
    if end is None:
        return False
    return end < min(_earliest_selector_year(revision.period_selector) for revision in candidates)


def _earliest_selector_year(selector: PeriodSelector) -> int:
    intervals = _selector_year_intervals(selector)
    if not intervals:
        raise ValueError("relation source revision must declare a year selector")
    return min(start for start, _ in intervals)


def _year_interval_label(start: int, end: int | None) -> str:
    if end is None:
        return f"{start}+"
    if start == end:
        return str(start)
    return f"{start}-{end}"


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
