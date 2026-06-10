"""Revision-level invariant validation helpers.

Validates temporal window overlap, informative-class invariants, bracket-table
coverage, reconciliation-total closure, and the D3 ``orden_aplicabilidad``
ratchet gate for a :class:`ModeloRevision` within its :class:`ModeloDefinition`.

D3 / Ruling 4 (period-revision-resolution ADR)
-----------------------------------------------
Every revision's ``orden_aplicabilidad`` field declares the legal-catalogue
:class:`~aeat.domain.calculations.registry._schema.LegalReference` id(s) of
the ordenes ministeriales that approve or amend the modelo form for this
revision's applicability window.  The gate is a **ratchet**:

- A *new* revision (``valid_from`` on or after the ratchet date ``2026-06-10``)
  MUST declare at least one entry — missing entries are a hard failure.
- An *existing* revision (``valid_from`` before the ratchet date) MAY omit
  the field — missing entries produce a tracked follow-up failure that callers
  can surface as an advisory rather than a hard error.
- Every declared entry MUST resolve in the legal catalogue with a ``corpus_ref``
  (per ``registry-calculation-legal-grounding``).
- Every declared entry MUST also appear in (or be merged into) ``legal_refs``
  so existing snapshot ref-collection carries it.

S24 / Ruling 5 boundary (R3):
    For ``*-y-siguientes`` (open-ended) revisions the ``orden_aplicabilidad``
    MUST cite the orden establishing the open-ended applicability — the
    connective gate ensuring even the "y siguientes" claim is BOE-anchored.
    Per-year norm values *inside* the open-ended revision (rate brackets,
    thresholds) are the parameter-bracket layer's responsibility gated by
    :func:`validate_bracket_table_temporal_coverage`; a wrong-but-present
    bracket value is a legal-grounding defect, NOT a resolution defect.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta

from ._schema import DatedValue, InputKind, LegalReference, ModeloDefinition, ModeloRevision, ParameterDefinition
from ._validate_relation_sources import period_selectors_overlap

# Ratchet date: revisions whose valid_from is on or after this date MUST
# declare orden_aplicabilidad.  Revisions before this date are accepted
# without it but tracked as follow-up items.
_ORDEN_APLICABILIDAD_RATCHET_DATE = date(2026, 6, 10)

_FAR_FUTURE = date(9999, 12, 31)


def validate_revision_windows(modelo: ModeloDefinition) -> list[str]:
    failures: list[str] = []
    revisions = sorted(modelo.revisions.values(), key=lambda item: item.valid_from)
    for index, current in enumerate(revisions[1:], start=1):
        previous = revisions[index - 1]
        previous_to = previous.valid_to
        if (previous_to is None or previous_to >= current.valid_from) and period_selectors_overlap(
            previous.period_selector, current.period_selector
        ):
            failures.append(
                f"modelo {modelo.id}: revisions {previous.id!r} and {current.id!r} overlap on period selector"
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
                f"{prefix}: informative modelo must not declare calculation formulas (got {len(revision.formulas)})"
            )
        if revision.relations:
            failures.append(
                f"{prefix}: informative modelo must not declare cross-model relations (got {len(revision.relations)})"
            )
        for casilla in revision.casillas:
            if casilla.input_kind not in {InputKind.INFORMATIONAL, InputKind.MANUAL}:
                failures.append(
                    f"{prefix}: informative modelo casilla {casilla.id!r} "
                    f"has input_kind={casilla.input_kind!r}; "
                    "only 'informational' and 'manual' are permitted"
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

    for wf, wt in windows:
        # Clamp window to revision range.
        clamp_wf = max(wf, revision_from)
        clamp_wt = min(wt, effective_revision_to)
        if clamp_wf > effective_revision_to or clamp_wt < revision_from:
            continue  # window entirely outside revision range
        if frontier < clamp_wf:
            # Gap between frontier and this window's start.
            gaps.append((frontier, clamp_wf - timedelta(days=1)))
        if clamp_wt >= frontier:
            if clamp_wt == _FAR_FUTURE:
                # Open-ended window covers everything forward; no further gaps.
                return gaps
            frontier = clamp_wt + timedelta(days=1)

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
                f"within revision date range starting {revision.valid_from.isoformat()}"
            )
    return failures


def validate_reconciliation_total_closure(scope: str, revision: ModeloRevision) -> list[str]:
    failures: list[str] = []
    declared: dict[str, str] = {}
    for expectation in revision.verification_expectations:
        for total_kind, casilla_id in expectation.reconciliation_totals.items():
            previous = declared.get(total_kind)
            if previous is not None and previous != casilla_id:
                failures.append(
                    f"{scope}: reconciliation total {total_kind!r} is declared by multiple casillas "
                    f"{previous!r} and {casilla_id!r}"
                )
            declared[total_kind] = casilla_id
    return failures


def validate_orden_aplicabilidad(
    scope: str,
    modelo_id: str,
    revision: ModeloRevision,
    legal_catalogue: Mapping[str, LegalReference],
) -> tuple[list[str], list[str]]:
    """Validate the ``orden_aplicabilidad`` ratchet gate for one revision.

    Returns ``(hard_failures, follow_up_items)`` where:

    - ``hard_failures`` are errors that MUST block registry load (new revision
      missing the field, or a declared entry that fails catalogue / corpus_ref /
      legal_refs cross-checks).
    - ``follow_up_items`` are tracked deficits on existing revisions that are
      accepted but must shrink monotonically (unstamped pre-ratchet revisions).

    S24 connective gate (Ruling 5 boundary):
        For open-ended ``*-y-siguientes`` revisions (``valid_to is None`` and
        ``period_selector.year_from`` is set) the ``orden_aplicabilidad`` MUST
        be non-empty — the open-ended applicability claim MUST be BOE-anchored.
        A pre-ratchet open-ended revision without ``orden_aplicabilidad`` is a
        follow-up item, not a hard failure, to avoid breaking the existing
        corpus; a post-ratchet one is a hard failure.

    Args:
        scope: Diagnostic scope string prefixed to each message.
        modelo_id: The modelo identifier, used in advisory messages.
        revision: The :class:`ModeloRevision` to validate.
        legal_catalogue: The loaded legal-reference catalogue mapping.

    Returns:
        A ``(hard_failures, follow_up_items)`` tuple; both lists may be empty.
    """
    hard: list[str] = []
    follow_up: list[str] = []

    is_new_revision = revision.valid_from >= _ORDEN_APLICABILIDAD_RATCHET_DATE
    is_open_ended = revision.valid_to is None and revision.period_selector.year_from is not None

    if not revision.orden_aplicabilidad:
        # Missing field: hard failure for new revisions; follow-up for existing.
        if is_new_revision or is_open_ended:
            # Post-ratchet or open-ended: MUST declare.
            if is_new_revision:
                hard.append(
                    f"{scope}: revision {revision.id!r} (valid_from {revision.valid_from.isoformat()}) "
                    f"is a new revision (on or after ratchet date "
                    f"{_ORDEN_APLICABILIDAD_RATCHET_DATE.isoformat()}) and MUST declare "
                    f"orden_aplicabilidad citing the orden ministerial that approves this form; "
                    f"see registry-calculation-legal-grounding rule and D3 of the "
                    f"period-revision-resolution ADR"
                )
            else:
                # Pre-ratchet open-ended: follow-up so it burns down.
                follow_up.append(
                    f"{scope}: open-ended revision {revision.id!r} (valid_from "
                    f"{revision.valid_from.isoformat()}, valid_to open) has no "
                    f"orden_aplicabilidad — the open-ended applicability claim is not "
                    f"BOE-anchored; add the orden that establishes 'y siguientes' "
                    f"applicability (S24 connective gate, Ruling 5 boundary, "
                    f"period-revision-resolution ADR)"
                )
        else:
            # Pre-ratchet bounded: simple follow-up.
            follow_up.append(
                f"{scope}: revision {revision.id!r} (valid_from {revision.valid_from.isoformat()}) "
                f"has no orden_aplicabilidad — follow-up backfill required; cite the orden "
                f"ministerial that approves this form revision in the legal catalogue with a "
                f"corpus_ref (D3 backfill, period-revision-resolution ADR)"
            )
        # No entries to validate further.
        return hard, follow_up

    # Validate each declared entry.
    legal_refs_set = set(revision.legal_refs)
    for ref_id in revision.orden_aplicabilidad:
        # (i) Must resolve in the legal catalogue.
        if ref_id not in legal_catalogue:
            hard.append(
                f"{scope}: revision {revision.id!r} orden_aplicabilidad entry {ref_id!r} "
                f"does not resolve in the legal catalogue; add the full LegalReference "
                f"entry to a legal/*.toml file (registry-calculation-legal-grounding rule)"
            )
            continue  # Cannot check corpus_ref on an absent entry.

        # (ii) Must carry a corpus_ref (already validated by LegalReference schema,
        # but we surface a more helpful revision-level message if it's missing).
        ref = legal_catalogue[ref_id]
        if not ref.corpus_ref:
            hard.append(
                f"{scope}: revision {revision.id!r} orden_aplicabilidad entry {ref_id!r} "
                f"exists in the catalogue but has no corpus_ref; add a corpus_ref pointing "
                f"to real BOE/AEAT text (registry-calculation-legal-grounding rule)"
            )

        # (iii) Must also appear in legal_refs so snapshot ref-collection carries it.
        if ref_id not in legal_refs_set:
            hard.append(
                f"{scope}: revision {revision.id!r} orden_aplicabilidad entry {ref_id!r} "
                f"is not present in the revision's legal_refs; add it to legal_refs so "
                f"snapshot ref-collection carries the orden (D3, period-revision-resolution ADR)"
            )

    return hard, follow_up
