"""Relation selector helpers for resolving revision and period coverage.

The helpers select source :class:`ModeloRevision` entries from a
:class:`ModeloDefinition` and verify that their period selectors cover the
target relation window.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .errors import RegistryValidationError
from .ids import ModeloId, RelationId
from .period_offset_math import apply_period_offset
from .schema import ModeloDefinition, ModeloRevision
from .schema_references import PeriodSelector
from .schema_surfaces import RelationDefinition, RelationRevisionSelector


@dataclass(frozen=True, slots=True)
class RelationCoverageFailure:
    """One relation-source coverage failure, structured for allowlist reconciliation.

    ``allowance_key`` is populated ONLY for a genuine "lacks exact source
    revision coverage" year-gap finding on a BOUNDED segment -- the one
    failure shape a documented, currently-necessary corpus gap can
    legitimately excuse. Every other failure shape (ambiguous ownership, an
    unsupported source period, an unbounded "not yet published" segment
    already excluded structurally) carries ``None`` and can never be
    allowlisted: those are either registry authoring defects or already
    structurally resolved, never a corpus gap.
    """

    message: str
    allowance_key: tuple[RelationId, ModeloId, str, int, int] | None = None


def select_relation_source_revisions(
    modelo: ModeloDefinition,
    selector: RelationRevisionSelector,
) -> tuple[tuple[ModeloRevision, ...], list[str]]:
    """Return the source modelo's matching revisions alongside any selection failures.

    Deliberately a dual return, not a candidate for the `list[str]`-only
    accumulator-convention conversion: every caller (`_validate_relation_sources`
    and several tests) needs the resolved `ModeloRevision` tuple to keep
    working -- source-year coverage, coordinate-ownership resolution, and
    downstream diagnostics all consume it -- so splitting this into a pure
    selector plus a pure validator would run the SAME revision-matching walk
    twice per relation. The failures slot is real, wired infrastructure (the
    caller already does `failures.extend(selector_failures)`), currently
    always empty only because no branch below yet has a selection failure to
    report -- not vestigial, just unexercised. The distinction matters: an
    unreachable slot (nothing ever calls the code that would populate it) is
    the defect class this registry has hit before -- a schema family with
    validation declared but no executor reaching it. This slot IS reached,
    on every call, by a real caller that already drains it; it is simply
    quiet because no selection failure has occurred yet, not because nothing
    can reach it.
    """
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


def validate_relation_source_coordinate_coverage(
    scope: str,
    *,
    relation: RelationDefinition,
    target_selector: PeriodSelector,
    source_revisions: Iterable[ModeloRevision],
    source_periods: Iterable[str],
    source_is_observation_history: bool,
) -> tuple[tuple[tuple[ModeloRevision, tuple[str, ...]], ...], list[RelationCoverageFailure]]:
    """Resolve exact source-revision ownership for a cross-model relation.

    A source model may partition one year across multiple revisions. Validate
    every declared or offset-derived ``(source year, source period)``
    coordinate against the *union* of those revisions, requiring exactly one
    owner for each in-modelled coordinate.

    ``source_revisions`` is the set of :class:`ModeloRevision` the source model
    partitions its years across; ownership is resolved against their union
    rather than against any one of them.

    Two structural boundaries are excluded before a "lacks coverage" finding
    is emitted, neither ever a candidate for the allowlist:

    - An observation-backed carry can read a filing before the earliest
      modelled source year. That filing still has to use a known period
      shape and semantic casilla (checked by the caller), but it cannot be
      required to have an engine revision that predates the modelled
      registry.
    - ANY segment entirely beyond the source modelo's own latest MODELLED
      year is not yet published by AEAT for anyone, regardless of
      ``source_is_observation_history`` -- the expected state of the world
      today, not a corpus omission, and it resolves itself the moment a new
      source revision ships. Without this, an open-ended CONSUMER reading a
      period-versioned, closed-ended SOURCE (each revision covering exactly
      one year) fails perpetually for every year beyond the source's latest
      authored revision.

    What remains after both exclusions is either genuine coverage or a real,
    currently-unmodelled gap in the SOURCE corpus -- the caller reconciles
    those against a documented allowlist keyed on ``allowance_key``.

    Deliberately a dual return, not a candidate for the `list[str]`-only
    accumulator-convention conversion: the resolved `(revision, periods)`
    coverage tuple and the failures are produced by the SAME per-coordinate
    walk over ``candidates`` (see ``_coordinate_coverage`` / segment
    resolution below) -- splitting resolution from validation would mean
    walking every coordinate's owner-segments twice, once to resolve
    coverage and once to re-derive the same failures.
    """
    candidates = tuple(source_revisions)
    covered_periods_by_revision: dict[str, set[str]] = {}
    revisions_by_id = {revision.id: revision for revision in candidates}
    failures: list[RelationCoverageFailure] = []

    for source_period, offset_year_delta, target_period in _relation_source_coordinates(relation, source_periods):
        covered_revision_ids, coordinate_failures = _coordinate_coverage(
            scope,
            relation=relation,
            target_selector=target_selector,
            candidates=candidates,
            source_period=source_period,
            offset_year_delta=offset_year_delta,
            target_period=target_period,
            source_is_observation_history=source_is_observation_history,
        )
        failures.extend(coordinate_failures)
        for revision_id in covered_revision_ids:
            covered_periods_by_revision.setdefault(revision_id, set()).add(source_period)

    coverage = tuple(
        (revisions_by_id[revision_id], tuple(sorted(periods)))
        for revision_id, periods in sorted(covered_periods_by_revision.items())
    )
    return coverage, failures


def _relation_source_coordinates(
    relation: RelationDefinition,
    source_periods: Iterable[str],
) -> tuple[tuple[str, int, str | None], ...]:
    """Return declared coordinates or the offset-derived coordinate for every target period."""
    if relation.source_period_offset_from_target is None:
        return tuple((source_period, 0, None) for source_period in source_periods)

    coordinates: list[tuple[str, int, str | None]] = []
    for target_period in relation.target_periods:
        try:
            offset_year_delta, source_period = apply_period_offset(
                relation.source_period_offset_from_target,
                target_period=target_period,
            )
        except RegistryValidationError:
            # The sibling period-shape validation reports this with the relation
            # id and target-period context.
            continue
        coordinates.append((source_period, offset_year_delta, target_period))
    return tuple(coordinates)


def _coordinate_coverage(
    scope: str,
    *,
    relation: RelationDefinition,
    target_selector: PeriodSelector,
    candidates: tuple[ModeloRevision, ...],
    source_period: str,
    offset_year_delta: int,
    target_period: str | None,
    source_is_observation_history: bool,
) -> tuple[tuple[str, ...], list[RelationCoverageFailure]]:
    """Resolve owners for one source-period coordinate across all required years."""
    period_candidates = tuple(revision for revision in candidates if source_period in revision.period_selector.periods)
    if not period_candidates:
        if len(candidates) <= 1:
            # The tree contributes at most the revision under validation, so the
            # sibling revision this coordinate resolves to is ABSENT rather than
            # missing: a cross-period carry reads the PREVIOUS period, which
            # belongs to a different revision, and generated-export-tree
            # validation mandates a candidate registry pruned to exactly one.
            # Refusing here would report the pruning, not the registry.
            #
            # Keyed on the source revision being absent, never on the tree being
            # small in general: as soon as any sibling is present the question is
            # answerable and the refusal below stands. This is the one place a
            # revision error compounds across years, so the abstention is
            # deliberately the narrowest that removes the artifact.
            return (), []
        target_context = "" if target_period is None else f" for target period {target_period!r}"
        return (), [
            RelationCoverageFailure(
                message=(
                    f"{scope} derived source period {source_period!r}{target_context} "
                    "is not supported by any selected source revision"
                ),
            ),
        ]

    covered_revision_ids: set[str] = set()
    failures: list[RelationCoverageFailure] = []
    for source_start, source_end in _offset_source_year_intervals(
        target_selector,
        relation=relation,
        offset_year_delta=offset_year_delta,
    ):
        assignments, interval_failures = _coverage_assignments(
            scope,
            relation=relation,
            source_period=source_period,
            source_start=source_start,
            source_end=source_end,
            candidates=period_candidates,
            source_is_observation_history=source_is_observation_history,
        )
        covered_revision_ids.update(assignments)
        failures.extend(interval_failures)
    return tuple(sorted(covered_revision_ids)), failures


def _coverage_assignments(
    scope: str,
    *,
    relation: RelationDefinition,
    source_period: str,
    source_start: int,
    source_end: int | None,
    candidates: tuple[ModeloRevision, ...],
    source_is_observation_history: bool,
) -> tuple[tuple[str, ...], list[RelationCoverageFailure]]:
    """Resolve one-owner segments, retaining the history exception and diagnostics."""
    assignments: set[str] = set()
    failures: list[RelationCoverageFailure] = []
    for segment_start, segment_end, owners in _coverage_segments(source_start, source_end, candidates):
        revision_id, failure = _coverage_segment_owner(
            scope,
            relation=relation,
            source_period=source_period,
            segment_start=segment_start,
            segment_end=segment_end,
            owners=owners,
            candidates=candidates,
            source_is_observation_history=source_is_observation_history,
        )
        if revision_id is not None:
            assignments.add(revision_id)
        if failure is not None:
            failures.append(failure)
    return tuple(sorted(assignments)), failures


def _coverage_segment_owner(
    scope: str,
    *,
    relation: RelationDefinition,
    source_period: str,
    segment_start: int,
    segment_end: int | None,
    owners: tuple[ModeloRevision, ...],
    candidates: tuple[ModeloRevision, ...],
    source_is_observation_history: bool,
) -> tuple[str | None, RelationCoverageFailure | None]:
    """Return the exact owner or the unchanged diagnostic for one stable segment."""
    if len(owners) == 1:
        return owners[0].id, None
    if not owners and source_is_observation_history and _is_pre_modelled_history(segment_end, candidates):
        earliest = min(candidates, key=lambda revision: _earliest_selector_year(revision.period_selector))
        return earliest.id, None
    if not owners and _is_beyond_latest_modelled_source_year(segment_start, candidates):
        # STRUCTURAL, unconditional: not yet published by AEAT for anyone,
        # self-resolving the moment a new source revision ships. Never a
        # candidate for the allowlist -- see
        # `_is_beyond_latest_modelled_source_year`.
        return None, None
    coverage = "lacks" if not owners else "has ambiguous"
    message = (
        f"{scope} {coverage} exact source revision coverage for derived "
        f"period {source_period!r} in source years {_year_interval_label(segment_start, segment_end)}"
    )
    # Only a genuine "lacks" finding on a BOUNDED segment is ever allowlist-
    # eligible. Ambiguous ownership is a registry authoring defect, never a
    # corpus gap; a bounded segment is guaranteed here because an unbounded
    # one with no owner is always caught by the future-year exclusion above.
    allowance_key = (
        (relation.id, relation.source_modelo, source_period, segment_start, segment_end)
        if not owners and segment_end is not None
        else None
    )
    return None, RelationCoverageFailure(message=message, allowance_key=allowance_key)


def _source_upper_bound(candidates: tuple[ModeloRevision, ...]) -> int | None:
    """Return the latest year ANY candidate models, or ``None`` when any is open-ended.

    ``None`` means "no ceiling": an open-ended candidate covers every year
    from its own start onward, so a segment reaching that far would already
    have found an owner and never reach
    :func:`_is_beyond_latest_modelled_source_year`.
    """
    bound: int | None = None
    for revision in candidates:
        for _, end in _selector_year_intervals(revision.period_selector):
            if end is None:
                return None
            bound = end if bound is None else max(bound, end)
    return bound


def _is_beyond_latest_modelled_source_year(start: int, candidates: tuple[ModeloRevision, ...]) -> bool:
    """Whether ``start`` is entirely beyond every candidate's own latest modelled year.

    STRUCTURAL and unconditional (unlike :func:`_is_pre_modelled_history`,
    which stays scoped to ``source_is_observation_history``): a required year
    beyond the SOURCE modelo's own latest published year is not yet
    published by AEAT for ANYONE, which is the expected state of the world
    today rather than a corpus omission, and it resolves itself the moment a
    new source revision ships. Without this, an open-ended CONSUMER reading
    a period-versioned, closed-ended SOURCE (each revision covering exactly
    one year) fails this gate perpetually for every year beyond the
    source's latest authored revision -- a standing, undischargeable
    failure no allowlist entry could ever satisfy.
    """
    bound = _source_upper_bound(candidates)
    return bound is not None and start > bound


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
            _add_coverage_boundary(boundaries, candidate_start, start=start, end=end)
            if candidate_end is not None:
                _add_coverage_boundary(boundaries, candidate_end + 1, start=start, end=end)
    ordered_boundaries = sorted(boundaries)
    return tuple(
        _coverage_segment(
            segment_start,
            next_boundary=ordered_boundaries[index + 1] if index + 1 < len(ordered_boundaries) else None,
            end=end,
            candidates=candidates,
        )
        for index, segment_start in enumerate(ordered_boundaries)
        if end is None or segment_start <= end
    )


def _add_coverage_boundary(boundaries: set[int], boundary: int, *, start: int, end: int | None) -> None:
    """Keep only interior selector boundaries relevant to the requested interval."""
    if boundary > start and (end is None or boundary <= end):
        boundaries.add(boundary)


def _coverage_segment(
    start: int,
    *,
    next_boundary: int | None,
    end: int | None,
    candidates: tuple[ModeloRevision, ...],
) -> tuple[int, int | None, tuple[ModeloRevision, ...]]:
    """Materialise one interval between consecutive ownership boundaries."""
    segment_end = end if next_boundary is None else next_boundary - 1
    owners = tuple(revision for revision in candidates if revision.period_selector.includes_year(start))
    return start, segment_end, owners


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
