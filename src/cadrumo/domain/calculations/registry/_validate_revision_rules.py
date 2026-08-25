"""Revision-level invariant validation helpers.

Validates temporal window overlap, informative-class invariants, bracket-table
coverage, and reconciliation-total closure for a :class:`ModeloRevision` within
its :class:`ModeloDefinition`.

The D3 ``orden_aplicabilidad`` gate lives in its sibling module
:mod:`cadrumo.domain.calculations.registry._validate_orden_aplicabilidad`.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from datetime import date, timedelta

from ....core import M210_TIPO_RENTA_CODE_PROJECTION
from ._deadline_coordinate import DeadlineSemanticCoordinate, deadline_window_semantic_coordinates
from ._errors import RegistrySnapshotError
from ._schema import (
    DatedValue,
    InputKind,
    ModeloDefinition,
    ModeloRevision,
    ParameterDefinition,
    filing_schedule_period_kind_mismatches,
)
from ._temporal import select_revision
from ._validate_relation_sources import period_selectors_overlap

_FAR_FUTURE = date(9999, 12, 31)

_M210_TIPO_RENTA_CODE_PARAMETER_PREFIX = "m210-tipo-renta-code-"


def validate_revision_windows(modelo: ModeloDefinition) -> list[str]:
    failures: list[str] = []
    revisions = sorted(modelo.revisions.values(), key=lambda item: item.valid_from)
    for index, earlier in enumerate(revisions):
        for later in revisions[index + 1 :]:
            if earlier.valid_to is not None and earlier.valid_to < later.valid_from:
                # Later revisions are ordered by valid_from, so no subsequent
                # revision can overlap this bounded earlier window either.
                break
            if period_selectors_overlap(earlier.period_selector, later.period_selector):
                failures.append(
                    f"modelo {modelo.id}: revisions {earlier.id!r} and {later.id!r} overlap on period selector",
                )
    return failures


def validate_deadline_window_uniqueness(modelo: ModeloDefinition) -> list[str]:
    """Reject deadline identities repeated anywhere in one modelo's revisions.

    Deadline rows are revision-owned law facts, so neither an authored id nor
    an atomic request coordinate may have more than one owner.  The plural
    coordinate projection deliberately expands qualifier bundles and wildcard
    scopes before this pass compares them; this makes overlaps visible without
    teaching the validator a second set of deadline matching rules.
    """
    failures: list[str] = []
    id_owner: dict[str, str] = {}
    coordinate_owner: dict[DeadlineSemanticCoordinate, tuple[str, str]] = {}
    duplicate_ids: set[str] = set()
    duplicate_coordinates: set[DeadlineSemanticCoordinate] = set()

    for revision in modelo.revisions.values():
        for window in revision.deadline_windows:
            previous_revision = id_owner.get(window.id)
            if previous_revision is None:
                id_owner[window.id] = revision.id
            elif window.id not in duplicate_ids:
                failures.append(
                    f"modelo {modelo.id}: deadline window id {window.id!r} is declared more than once "
                    f"across revisions {previous_revision!r} and {revision.id!r}",
                )
                duplicate_ids.add(window.id)

            for coordinate in deadline_window_semantic_coordinates(modelo.id, window):
                previous_owner = coordinate_owner.get(coordinate)
                if previous_owner is None:
                    coordinate_owner[coordinate] = (revision.id, window.id)
                    continue
                if coordinate in duplicate_coordinates:
                    continue
                failures.append(
                    f"modelo {modelo.id}: deadline semantic coordinate {coordinate!r} is declared more than once "
                    f"by revision/window {previous_owner!r} and {(revision.id, window.id)!r}",
                )
                duplicate_coordinates.add(coordinate)

    return failures


def validate_deadline_window_ownership(modelo: ModeloDefinition) -> list[str]:
    """Require every deadline row to live beneath its law-selected revision.

    The deadline's canonical filing coordinate drives the existing temporal
    resolver.  The containing revision is only asserted against that result;
    it never participates in selection.  This keeps period-sensitive cutovers
    governed by exactly the same resolver as snapshots and other registry
    projections.
    """
    failures: list[str] = []
    for containing_revision in modelo.revisions.values():
        for window in containing_revision.deadline_windows:
            filing_year = window.period.filing_year
            period = window.period.registry_token
            try:
                selected_revision = select_revision(
                    modelo,
                    filing_year=filing_year,
                    period=period,
                )
            except RegistrySnapshotError as exc:
                failures.append(
                    f"modelo {modelo.id} revision {containing_revision.id}: deadline window "
                    f"{window.id!r} has no unique canonical owner for filing coordinate "
                    f"({filing_year}, {period!r}): {exc}",
                )
                continue
            if selected_revision.id != containing_revision.id:
                failures.append(
                    f"modelo {modelo.id} revision {containing_revision.id}: deadline window "
                    f"{window.id!r} belongs to canonically selected revision "
                    f"{selected_revision.id!r} for filing coordinate ({filing_year}, {period!r})",
                )
    return failures


def validate_deadline_window_cadence(modelo: ModeloDefinition) -> list[str]:
    """Reject deadline cadence labels that contradict their canonical period.

    Reuse the filing-schedule compatibility table so deadline rows and
    schedules interpret monthly, quarterly, instalment, and extended tokens
    through one vocabulary owner.
    """
    failures: list[str] = []
    for revision in modelo.revisions.values():
        for window in revision.deadline_windows:
            period = window.period.registry_token
            if filing_schedule_period_kind_mismatches(window.period_kind, (period,)):
                failures.append(
                    f"modelo {modelo.id} revision {revision.id}: deadline window {window.id!r} "
                    f"period_kind {window.period_kind!r} contradicts period {period!r}",
                )
    return failures


def validate_periodic_deadline_completeness(
    modelo: ModeloDefinition,
    *,
    supported_filing_years: Collection[int],
) -> list[str]:
    """Require every selected periodic schedule coordinate to own a window.

    The supported-year horizon is supplied by the registry-wide catalogue.
    Candidate tokens come only from authored filing schedules, and
    :func:`select_revision` decides which revision governs each coordinate.
    The shared filing-schedule cadence compatibility gate validates the period
    vocabulary; it is not replaced by a deadline-specific parser or table.
    """
    candidate_periods = sorted(
        {
            period
            for revision in modelo.revisions.values()
            for schedule in revision.filing_schedules
            if schedule.is_periodic
            for period in schedule.periods
        },
    )
    failures: list[str] = []
    for filing_year in supported_filing_years:
        for period in candidate_periods:
            try:
                selected = select_revision(modelo, filing_year=filing_year, period=period)
            except RegistrySnapshotError:
                continue
            selected_schedules = tuple(
                schedule
                for schedule in selected.filing_schedules
                if schedule.is_periodic and period in schedule.periods
            )
            if not selected_schedules:
                continue
            if any(
                window.filing_year == filing_year
                and window.period.registry_token == period
                and not filing_schedule_period_kind_mismatches(window.period_kind, (period,))
                for window in selected.deadline_windows
            ):
                continue
            failures.append(
                f"modelo {modelo.id} revision {selected.id}: periodic filing schedule coordinate "
                f"({filing_year}, {period!r}) has no deadline window",
            )
    return failures


def validate_informative_class_invariant(modelo: ModeloDefinition) -> list[str]:
    """Enforce that informative modelos carry no filing-grade computation artefacts.

    Args:
        modelo: The :class:`ModeloDefinition` to validate against the informative-class invariant.
    """
    if modelo.calculation_class != "informative":
        return []
    failures: list[str] = []
    for revision in modelo.revisions.values():
        prefix = f"modelo {modelo.id} revision {revision.id}"
        if revision.formulas:
            failures.append(
                f"{prefix}: informative modelo must not declare calculation formulas (got {len(revision.formulas)})",
            )
        if revision.relations:
            failures.append(
                f"{prefix}: informative modelo must not declare cross-model relations (got {len(revision.relations)})",
            )
        for casilla in revision.casillas:
            if casilla.input_kind not in {InputKind.INFORMATIONAL, InputKind.MANUAL}:
                failures.append(
                    f"{prefix}: informative modelo casilla {casilla.id!r} "
                    f"has input_kind={casilla.input_kind!r}; "
                    "only 'informational' and 'manual' are permitted",
                )
    return failures


def validate_m210_tipo_renta_code_projection_parity(
    modelo: ModeloDefinition,
    *,
    projected_codes: Collection[str] | None = None,
) -> list[str]:
    """Enforce bidirectional parity between the registry code set and the core projection.

    The official Modelo 210 tipo-de-renta code axis is declared in two places
    that MUST agree: the registry parameter ``m210-tipo-renta-code-<year>``
    (which codes the revision accepts, carrying the registry legal-grounding)
    and the core :data:`~cadrumo.core.M210_TIPO_RENTA_CODE_PROJECTION` (each code's
    :class:`~cadrumo.core.TipoRentaIrnr` rate concept). This gate fails the
    registry build in BOTH directions: a code declared in the registry with no
    core projection, and a code the core projects that the registry does not
    declare. It keeps the two axes from drifting so no declared code resolves to
    a fabricated rate and no projected code silently lacks a grounded home.

    Args:
        modelo: The :class:`ModeloDefinition` to check. Only revisions carrying
            an ``m210-tipo-renta-code-`` parameter are inspected; every other
            modelo is a no-op.
        projected_codes: Optional code set used for the comparison. When omitted,
            the shipped core projection is used.
    """
    failures: list[str] = []
    projected = set(M210_TIPO_RENTA_CODE_PROJECTION if projected_codes is None else projected_codes)
    for revision in modelo.revisions.values():
        for parameter in revision.parameters:
            if not parameter.id.startswith(_M210_TIPO_RENTA_CODE_PARAMETER_PREFIX):
                continue
            declared = {row.key for row in parameter.keyed_brackets}
            prefix = f"modelo {modelo.id} revision {revision.id} parameter {parameter.id!r}"
            for code in sorted(declared - projected):
                failures.append(
                    f"{prefix}: declared tipo-de-renta code {code!r} has no core "
                    "TipoRentaIrnr projection (add it to OFFICIAL_M210_TIPO_RENTA_CODES "
                    "or remove the declaration)",
                )
            for code in sorted(projected - declared):
                failures.append(
                    f"{prefix}: core-projected tipo-de-renta code {code!r} is not "
                    "declared in the registry code set (declare it here or remove it "
                    "from OFFICIAL_M210_TIPO_RENTA_CODES)",
                )
    return failures


def validate_dated_values(scope: str, parameter_id: str, values: Iterable[DatedValue]) -> list[str]:
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
    when ``revision_to`` is ``None``).  Open-ended revisions are not validated for
    completeness beyond their last bracket window — gaps are only reported when
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
    uncovered range — this validator promotes that to a registry-load failure.

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


def validate_reconciliation_total_closure(scope: str, revision: ModeloRevision) -> list[str]:
    failures: list[str] = []
    declared: dict[str, str] = {}
    for expectation in revision.verification_expectations:
        for total_kind, casilla_id in expectation.reconciliation_total_casilla_ids.items():
            previous = declared.get(total_kind)
            if previous is not None and previous != casilla_id:
                failures.append(
                    f"{scope}: reconciliation total {total_kind!r} is declared by multiple casillas "
                    f"{previous!r} and {casilla_id!r}",
                )
            declared[total_kind] = casilla_id
    return failures
