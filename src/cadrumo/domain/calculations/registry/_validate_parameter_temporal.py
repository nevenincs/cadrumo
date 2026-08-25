"""Temporal validation for parameter values and bracket tables.

The helpers here accumulate diagnostics for a revision's parameter temporal
surfaces. The established revision-rules module re-exports them to retain the
validator's existing call sites and diagnostic composition.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta

from ._schema import DatedValue, ModeloRevision, ParameterDefinition

_FAR_FUTURE = date(9999, 12, 31)


def validate_dated_values(scope: str, parameter_id: str, values: Iterable[DatedValue]) -> list[str]:
    """Return overlap diagnostics for one parameter's dated values."""
    failures: list[str] = []
    by_axis: dict[str, list[DatedValue]] = {}
    for value in values:
        axis = value.date_axis
        by_axis.setdefault(axis, []).append(value)
    for axis, axis_values in by_axis.items():
        ordered = sorted(axis_values, key=lambda item: item.valid_from)
        for index, current in enumerate(ordered[1:], start=1):
            previous = ordered[index - 1]
            previous_to = previous.valid_to
            if previous_to is None or previous_to >= current.valid_from:
                failures.append(f"{scope}: parameter {parameter_id!r} has overlapping {axis} values")
    return failures


def _bracket_windows_for_parameter(parameter: ParameterDefinition) -> list[tuple[date, date]]:
    """Return the sorted list of ``(effective_from, effective_to)`` windows.

    Each distinct ``valid_from`` date across all brackets defines one window.
    The window ends at the latest ``valid_to`` among the brackets that share
    that ``valid_from``; an open-ended bracket (``valid_to = None``) makes the
    entire window open-ended, represented here as ``_FAR_FUTURE``.
    """
    window_to: dict[date, date] = {}
    for bracket in parameter.brackets:
        wf = bracket.valid_from
        effective_wt = bracket.valid_to if bracket.valid_to is not None else _FAR_FUTURE
        window_to[wf] = max(window_to.get(wf, date.min), effective_wt)
    return sorted(window_to.items())


def _clamp_bracket_window(
    window: tuple[date, date],
    *,
    revision_from: date,
    effective_revision_to: date,
) -> tuple[date, date] | None:
    window_from, window_to = window
    clamp_from = max(window_from, revision_from)
    clamp_to = min(window_to, effective_revision_to)
    if clamp_from > effective_revision_to or clamp_to < revision_from:
        return None
    return clamp_from, clamp_to


def _advance_bracket_coverage(
    gaps: list[tuple[date, date]],
    frontier: date,
    clamped: tuple[date, date],
) -> tuple[date, bool]:
    clamp_from, clamp_to = clamped
    if frontier < clamp_from:
        gaps.append((frontier, clamp_from - timedelta(days=1)))
    if clamp_to < frontier:
        return frontier, False
    if clamp_to == _FAR_FUTURE:
        return frontier, True
    return clamp_to + timedelta(days=1), False


def _bracket_coverage_gaps(
    parameter: ParameterDefinition,
    revision_from: date,
    revision_to: date | None,
) -> list[tuple[date, date]]:
    """Return date gaps in ``parameter``'s bracket windows relative to the revision range.

    Only ``bracket_table`` parameters with ``bracket_axis = "filing_period"`` are
    examined; all others return an empty list immediately.

    A gap is a contiguous date interval within ``[revision_from, effective_revision_to]``
    not covered by any bracket window (where ``effective_revision_to = _FAR_FUTURE``
    when ``revision_to`` is ``None``). Open-ended revisions are not validated for
    completeness beyond their last bracket window - gaps are only reported when
    ``revision_to`` is set or when there are windows with explicit ``valid_to``
    dates that leave holes before another window begins.
    """
    if parameter.data_type != "bracket_table" or parameter.bracket_axis != "filing_period":
        return []

    windows = _bracket_windows_for_parameter(parameter)
    if not windows:
        return []

    effective_revision_to = revision_to if revision_to is not None else _FAR_FUTURE
    gaps: list[tuple[date, date]] = []

    # Walk from revision_from through the sorted windows, tracking coverage frontier.
    frontier = revision_from

    for window in windows:
        clamped = _clamp_bracket_window(
            window,
            revision_from=revision_from,
            effective_revision_to=effective_revision_to,
        )
        if clamped is None:
            continue  # window entirely outside revision range
        frontier, covered_to_end = _advance_bracket_coverage(gaps, frontier, clamped)
        if covered_to_end:
            return gaps

    # Tail gap: after all windows but before revision_to (only when bounded).
    if revision_to is not None and frontier <= effective_revision_to:
        gaps.append((frontier, effective_revision_to))

    return gaps


def validate_bracket_table_temporal_coverage(scope: str, revision: ModeloRevision) -> list[str]:
    """Surface bracket_table parameters whose windows gap the revision date range.

    Every ``bracket_table`` parameter with ``bracket_axis = "filing_period"``
    must have at least one bracket window covering every date in the revision's
    ``[valid_from, valid_to]`` range (or from ``valid_from`` to the first
    bracket window's ``valid_to`` when the revision is open-ended).

    A gap detected here would otherwise surface at runtime as a
    ``bracket_no_window`` error when an operator files for a period in the
    uncovered range - this validator promotes that to a registry-load failure.

    Args:
        scope: Diagnostic scope string prefixed to each failure message.
        revision: The :class:`ModeloRevision` whose bracket_table parameters
            are checked for temporal coverage gaps.
    """
    failures: list[str] = []
    for parameter in revision.parameters:
        if parameter.data_type != "bracket_table" or parameter.bracket_axis != "filing_period":
            continue
        gaps = _bracket_coverage_gaps(parameter, revision.valid_from, revision.valid_to)
        for gap_start, gap_end in gaps:
            failures.append(
                f"{scope}: bracket_table parameter {parameter.id!r} has no bracket "
                f"covering [{gap_start.isoformat()}, {gap_end.isoformat()}] "
                f"within revision date range starting {revision.valid_from.isoformat()}",
            )
    return failures
