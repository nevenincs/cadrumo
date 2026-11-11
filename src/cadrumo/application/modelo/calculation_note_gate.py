"""Refuse to check, export or record a declaration while its calculation left a figure out of every box.

A calculation persists the notes that mean an amount from the filer's records
reached no box, that the IVA owed on a reverse-charge invoice could not be
derived, that a box the form prints could not be worked out, or that a source
has no route or could not be read yet
(:data:`~.calculation_notes.GATE_REFUSED_REASONS`). While the current
calculation carries one, no entrypoint may produce a complete check, an export
file or a recorded filing from it: a recalculation that clears the note
releases them. The refusal is worded by the same catalogue sentence the
editor's findings list shows.

An unrouted one-stop-shop row is left to the Modelo 369 check, which reads it
with its own evidence, as the other reasons the application refuses on are
left to their own check step or to the export
(:data:`~.calculation_notes.BLOCKING_REASONS`).

See Also:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
        The stored calculation head carrying values, provenance and lifecycle facts;
:class:`RegistrySnapshot`, the pinned registry snapshot.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from ...core.aggregation import BindingSourceKind, BindingValueOutcome
from ...core.casilla_id import CasillaId
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_grade_cap_reach import capped_binding_reach, snapshot_reach_date
from ...domain.calculations.registry.errors import RegistrySnapshotError
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos.calculation_revision_sources import DISAGREEMENT_REASONS, CalculationSourceIssue
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.work_unit import WorkUnit
from .action_errors import ModeloPreconditionErrorMixin
from .calculation_notes import (
    CALCULATION_SCREEN_OUTDATED_REASON,
    DERIVED_GATE_REASONS,
    FILED_BEFORE_GRADE_CAP_REASON,
    GATE_REFUSED_REASONS,
    capped_value_proven_zero,
    what_locale_key,
)
from .calculation_screen import (
    calculation_screen_is_current,
    calculation_screen_outdated_message_key,
    calculation_screen_stamp,
)
from .household_row_fact_gate import household_row_fact_refusal
from .printed_boxes import PrintedBoxes, snapshot_printed_boxes


class ModeloCalculationBlockedError(ModeloPreconditionErrorMixin, ModeloError):
    """The current calculation carries a note that withholds this action until a recalculation clears it."""


_FILED_STATES: frozenset[CalculationRevisionState] = frozenset(
    {CalculationRevisionState.PRESENTADO, CalculationRevisionState.PRESENTADO_SUPERSEDIDO}
)


SOURCE_DISAGREEMENT_FINDING_ID_LENGTH: Final[int] = 16
"""The leading characters of a finding key an operator reads and types back as the finding id."""


@dataclass(frozen=True, slots=True)
class SourceDisagreementResolutions:
    """The source disagreements an active operator resolution covers, by finding key.

    A finding key names one disagreement together with every source's value,
    so a resolution covers only the exact values it was recorded against; any
    changed value is a new finding the resolution does not cover.
    """

    finding_keys: frozenset[str] = frozenset()
    unreadable: bool = False
    """The resolutions could not be read, so none is honoured; an unreadable store never reads as a covering one."""

    def covers(self, finding_key: str | None) -> bool:
        """Whether an active resolution covers the disagreement with ``finding_key``."""
        return not self.unreadable and finding_key is not None and finding_key in self.finding_keys


NO_SOURCE_DISAGREEMENT_RESOLUTIONS: Final[SourceDisagreementResolutions] = SourceDisagreementResolutions()
"""The view where no disagreement is resolved, so every one withholds."""


def gate_refuses(
    reason: str,
    binding_source: BindingSourceKind | None,
    outcome: BindingValueOutcome | None = None,
    *,
    finding_key: str | None = None,
    resolutions: SourceDisagreementResolutions = NO_SOURCE_DISAGREEMENT_RESOLUTIONS,
) -> bool:
    """Whether the gate refuses on a note of ``reason`` from ``binding_source``, wherever the note names.

    It is the one condition the gate, the form's hold on the file and its next
    step all decide with. An unrouted one-stop-shop row is the Modelo 369
    check's to decide. ``outcome`` is what the resolver stated beside a capped
    value: a proven zero withholds nothing, and a capped value without a stated
    outcome withholds like any other. A revision whose screen is outdated, or
    one recorded as filed before screens existed that holds a capped figure, is
    refused before its notes are read, so each derived reason withholds too.
    A disagreement between sources withholds until ``resolutions`` covers its
    ``finding_key``.
    """
    if reason in DERIVED_GATE_REASONS:
        return True
    if reason not in GATE_REFUSED_REASONS:
        return False
    if reason in DISAGREEMENT_REASONS:
        return not resolutions.covers(finding_key)
    if capped_value_proven_zero(reason, outcome):
        return False
    return not (reason == "unrouted_observation" and binding_source is BindingSourceKind.LEDGER_OSS_AGGREGATION)


def _refused_here(
    issue: CalculationSourceIssue, resolutions: SourceDisagreementResolutions = NO_SOURCE_DISAGREEMENT_RESOLUTIONS
) -> bool:
    return gate_refuses(
        issue.reason,
        issue.binding_source,
        issue.value_outcome,
        finding_key=None if issue.disagreement is None else issue.disagreement.finding_key,
        resolutions=resolutions,
    )


def blocking_calculation_issues(
    revision: CalculationRevision, resolutions: SourceDisagreementResolutions = NO_SOURCE_DISAGREEMENT_RESOLUTIONS
) -> tuple[CalculationSourceIssue, ...]:
    """The persisted notes of ``revision`` that withhold checking, exporting and recording it.

    A source disagreement that ``resolutions`` covers withholds nothing; every
    other disagreement still does.

    See Also:
        :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
            The stored calculation head carrying values, provenance and lifecycle facts.
    """
    return tuple(issue for issue in revision.source_issues if _refused_here(issue, resolutions))


def proven_zero_calculation_issues(revision: CalculationRevision) -> tuple[CalculationSourceIssue, ...]:
    """The persisted notes of ``revision`` saying its resolver proved a capped value to be zero.

    They withhold nothing; a reopened declaration shows them so the filer can see the zero was proven.

    See Also:
        :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
            The stored calculation head carrying values, provenance and lifecycle facts.
    """
    return tuple(
        issue for issue in revision.source_issues if capped_value_proven_zero(issue.reason, issue.value_outcome)
    )


def require_no_blocking_calculation_notes(
    revision: CalculationRevision,
    *,
    action: str,
    boxes: PrintedBoxes | None = None,
    resolutions: SourceDisagreementResolutions = NO_SOURCE_DISAGREEMENT_RESOLUTIONS,
) -> None:
    """Refuse ``action`` while ``revision`` carries a persisted blocking note.

    The refusal is worded by the first note's own catalogue sentence and
    carries every note's reason in its context. ``boxes`` are the boxes the
    revision's form prints, used to name the note's box by its printed number.
    A source disagreement is named by its finding id, the id an operator
    resolution answers; ``resolutions_unreadable`` says the resolutions could
    not be read, so none was honoured.

    A household row that omits a fact the official design requires is refused
    with its own typed error, which names the fact and the profile door that
    states it.

    Raises:
        ModeloCalculationBlockedError: The revision carries a blocking note.
        ModeloHouseholdRowFactUnstatedError: The blocking note is a required
            household fact the profile has not stated.

    See Also:
        :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
            The stored calculation head carrying values, provenance and lifecycle facts.
    """
    blocking = blocking_calculation_issues(revision, resolutions)
    if not blocking:
        return
    household_refusal = household_row_fact_refusal(revision, blocking, action=action)
    if household_refusal is not None:
        raise household_refusal
    first = blocking[0]
    raise ModeloCalculationBlockedError(
        translated_message=what_locale_key(first.reason),
        context=_blocked_context(revision, blocking, action=action, boxes=boxes, resolutions=resolutions),
    )


def _blocked_context(
    revision: CalculationRevision,
    blocking: Sequence[CalculationSourceIssue],
    *,
    action: str,
    boxes: PrintedBoxes | None,
    resolutions: SourceDisagreementResolutions,
) -> dict[str, str]:
    first = blocking[0]
    box = None if boxes is None or first.casilla_id is None else boxes.number(first.casilla_id)
    finding_ids = tuple(
        issue.disagreement.finding_key[:SOURCE_DISAGREEMENT_FINDING_ID_LENGTH]
        for issue in blocking
        if issue.disagreement is not None
    )
    context = {
        "action": action,
        "calculation_revision_id": revision.calculation_revision_id,
        "reason": first.reason,
        "reasons": ",".join(sorted({issue.reason for issue in blocking})),
        "blocking_count": str(len(blocking)),
    }
    if box is not None:
        context["box"] = box
    context.update(note_subject_facts(first))
    if finding_ids:
        context["finding_ids"] = ",".join(finding_ids)
        if resolutions.unreadable:
            context["resolutions_unreadable"] = "true"
    return context


_NOTE_SUBJECT_VALUES: Final[frozenset[str]] = frozenset({"row_date", "row_amount"})
"""The fact values that name a note's own record by date and amount, and nothing private about a party."""


def note_subject_facts(issue: CalculationSourceIssue) -> dict[str, str]:
    """The record a note is about and the amount it leaves out, as stable tokens.

    A refusal or a review that names only the reason leaves the filer nothing to
    act on, so each also names the record the note was raised on and, where the
    note's fact states them, that record's date and the amount it leaves out.
    """
    subject: dict[str, str] = {}
    if issue.source_ref is not None:
        subject["source_ref"] = issue.source_ref
    if issue.fact is not None:
        subject.update((name, value) for name, value in issue.fact.values if name in _NOTE_SUBJECT_VALUES and value)
    return subject


def _screened_snapshot(
    operation: PinnedAuthorityOperation, *, modelo: str, filing_year: int, period: Period
) -> RegistrySnapshot:
    """The filing-grade snapshot an action on the revision is screened against.

    A year the selected revision does not author has none, so checking,
    exporting and recording its revision refuse here as the registry refuses it.
    """
    return operation.snapshot(modelo, filing_year=filing_year, period=period.registry_token)


def _read_screened_snapshot(
    operation: PinnedAuthorityOperation, *, modelo: str, filing_year: int, period: Period
) -> RegistrySnapshot:
    """The snapshot a form or review reads a revision's screen from, which a projected year carries too."""
    return operation.reading_snapshot(modelo, filing_year=filing_year, period=period.registry_token)


def _screen_outdated(
    revision: CalculationRevision, snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation
) -> bool:
    if revision.state in _FILED_STATES:
        return False
    return not calculation_screen_is_current(revision, calculation_screen_stamp(snapshot, operation=operation))


def calculation_screen_outdated(
    revision: CalculationRevision,
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Whether the gate refuses ``revision`` as stale before reading its notes, as checking, exporting and recording do.

    A revision is stale when its screen stamp is absent or differs from the one
    a calculation under ``operation``'s pinned authority would carry. A revision
    already recorded as filed keeps its history and is never stale. The form
    asks this to offer a recalculation exactly where the gate refuses.

    See Also:
        :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
            The stored calculation head carrying values, provenance and lifecycle facts.
    """
    snapshot = _read_screened_snapshot(operation, modelo=modelo, filing_year=filing_year, period=period)
    return _screen_outdated(revision, snapshot, operation)


def saved_calculation_screen_outdated(
    revision: CalculationRevision,
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Whether a saved ``revision`` is shown as stale, read exactly as the gate reads it.

    Review and export screen the revision against the same snapshot, the one
    ``operation`` selects for the law in force, so they never disagree about a
    revision. A revision not yet recorded as filed whose snapshot cannot be
    selected is reported stale: nothing shows it current. A filed revision is
    never stale.

    ``revision`` is the :class:`CalculationRevision`, the saved calculation revision.
    """
    try:
        return calculation_screen_outdated(
            revision, modelo=modelo, filing_year=filing_year, period=period, operation=operation
        )
    except RegistrySnapshotError:
        return revision.state not in _FILED_STATES


def filed_before_grade_cap(
    revision: CalculationRevision, snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation
) -> CasillaId | None:
    """The first box a capped binding reaches that a filed, unstamped ``revision`` holds a figure in, or ``None``.

    A revision recorded as filed before screen stamps existed was never screened
    for grade caps, so a box a capped binding reaches may hold a figure the cap
    would withhold. A proven zero is the one value that cannot be such a figure;
    a box with no value at all is unresolved, so it refuses too.

    ``revision`` is a :class:`CalculationRevision`; ``snapshot`` is a :class:`RegistrySnapshot`.
    """
    if revision.state not in _FILED_STATES or revision.screen_stamp is not None:
        return None
    reach = capped_binding_reach(snapshot.revision, authority=operation, effective_date=snapshot_reach_date(snapshot))
    for capped in reach.values():
        for casilla_id in capped.casilla_ids:
            value = revision.casilla_values.get(casilla_id)
            if value is None or Decimal(value) != 0:
                return casilla_id
    return None


def calculation_filed_before_grade_cap(
    revision: CalculationRevision,
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    operation: PinnedAuthorityOperation,
) -> CasillaId | None:
    """The box whose figure keeps a revision filed before screens existed from being exported, or ``None``.

    It is the condition the export gate refuses with
    ``filed_before_grade_cap``. The form and the declarations list ask it to
    offer a recalculation exactly where the export refuses. A revision filed
    with a stamp, or with no figure in a capped box, is never refused this way.

    See Also:
        :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
            The stored calculation head carrying values, provenance and lifecycle facts.
    """
    if revision.state not in _FILED_STATES or revision.screen_stamp is not None:
        return None
    snapshot = _read_screened_snapshot(operation, modelo=modelo, filing_year=filing_year, period=period)
    return filed_before_grade_cap(revision, snapshot, operation)


def saved_calculation_filed_before_grade_cap(
    revision: CalculationRevision,
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Whether a saved ``revision`` is shown as filed before screens existed with a figure in a capped box.

    It is the condition :func:`calculation_filed_before_grade_cap` finds, read
    for review. A filed revision without a screen stamp whose snapshot cannot be
    selected is reported so: nothing shows its figures were screened.

    ``revision`` is the :class:`CalculationRevision`, the saved calculation revision.
    """
    if revision.state not in _FILED_STATES or revision.screen_stamp is not None:
        return False
    try:
        return (
            calculation_filed_before_grade_cap(
                revision, modelo=modelo, filing_year=filing_year, period=period, operation=operation
            )
            is not None
        )
    except RegistrySnapshotError:
        return True


def _refuse_outdated_screen(revision: CalculationRevision, *, action: str) -> ModeloCalculationBlockedError:
    return ModeloCalculationBlockedError(
        translated_message=calculation_screen_outdated_message_key(),
        context={
            "action": action,
            "calculation_revision_id": revision.calculation_revision_id,
            "reason": CALCULATION_SCREEN_OUTDATED_REASON,
            "reasons": CALCULATION_SCREEN_OUTDATED_REASON,
        },
    )


def _refuse_filed_before_grade_cap(
    revision: CalculationRevision,
    *,
    action: str,
    snapshot: RegistrySnapshot,
    operation: PinnedAuthorityOperation,
    capped_box: CasillaId,
) -> ModeloCalculationBlockedError:
    box = snapshot_printed_boxes(operation, snapshot).number(capped_box)
    return ModeloCalculationBlockedError(
        translated_message=what_locale_key(FILED_BEFORE_GRADE_CAP_REASON),
        context={
            "action": action,
            "calculation_revision_id": revision.calculation_revision_id,
            "reason": FILED_BEFORE_GRADE_CAP_REASON,
            "reasons": FILED_BEFORE_GRADE_CAP_REASON,
            **({} if box is None else {"box": box}),
        },
    )


def require_work_unit_calculation_screen_current(
    *, work_unit: WorkUnit, revision: CalculationRevision, action: str, operation: PinnedAuthorityOperation
) -> None:
    """Refuse ``action`` on ``work_unit`` while ``revision`` is stale or filed with a capped figure, notes unread.

    The staleness is the one :func:`calculation_screen_outdated` answers: an
    absent or differing screen stamp refuses, and a revision already recorded
    as filed is never stale. A revision filed before screen stamps existed
    still refuses when a box a capped binding reaches holds a figure
    (:func:`calculation_filed_before_grade_cap`), as the gate refuses it.

    Raises:
        ModeloCalculationBlockedError: The revision is stale, or was filed
            before screens with a capped figure.

    See Also:
        :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
            The stored calculation head carrying values, provenance and lifecycle facts.
    """
    if revision.state in _FILED_STATES and revision.screen_stamp is not None:
        return
    snapshot = _screened_snapshot(
        operation, modelo=str(work_unit.modelo), filing_year=work_unit.filing_year, period=work_unit.period
    )
    if _screen_outdated(revision, snapshot, operation):
        raise _refuse_outdated_screen(revision, action=action)
    capped_box = filed_before_grade_cap(revision, snapshot, operation)
    if capped_box is not None:
        raise _refuse_filed_before_grade_cap(
            revision, action=action, snapshot=snapshot, operation=operation, capped_box=capped_box
        )


def require_work_unit_calculation_unblocked(
    *,
    work_unit: WorkUnit,
    revision: CalculationRevision,
    action: str,
    operation: PinnedAuthorityOperation,
    resolutions: SourceDisagreementResolutions = NO_SOURCE_DISAGREEMENT_RESOLUTIONS,
) -> None:
    """Refuse ``action`` on ``work_unit`` while its ``revision`` is stale or carries a persisted blocking note.

    A revision is stale when its screen stamp is absent or differs from the one
    a calculation under ``operation``'s pinned authority would carry: its notes
    were screened against other declarations, so it is refused before its notes
    are read. A revision already recorded as filed keeps its history and is not
    screened again, but a blocking note it carries still refuses, and so does a
    figure in a capped box of a revision filed before screen stamps existed
    (:func:`calculation_filed_before_grade_cap`). A source disagreement that
    ``resolutions`` covers is not a blocking note.

    Raises:
        ModeloCalculationBlockedError: The revision is stale, was filed before screens with a capped figure,
            or carries a blocking note.

    See Also:
        :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
            The stored calculation head carrying values, provenance and lifecycle facts.
    """
    filed = revision.state in _FILED_STATES
    snapshot = (
        None
        if filed and revision.screen_stamp is not None
        else _screened_snapshot(
            operation, modelo=str(work_unit.modelo), filing_year=work_unit.filing_year, period=work_unit.period
        )
    )
    if snapshot is not None and _screen_outdated(revision, snapshot, operation):
        raise _refuse_outdated_screen(revision, action=action)
    capped_box = None if snapshot is None else filed_before_grade_cap(revision, snapshot, operation)
    if snapshot is not None and capped_box is not None:
        raise _refuse_filed_before_grade_cap(
            revision, action=action, snapshot=snapshot, operation=operation, capped_box=capped_box
        )
    if not blocking_calculation_issues(revision, resolutions):
        return
    if snapshot is None:
        snapshot = _screened_snapshot(
            operation, modelo=str(work_unit.modelo), filing_year=work_unit.filing_year, period=work_unit.period
        )
    require_no_blocking_calculation_notes(
        revision, action=action, boxes=snapshot_printed_boxes(operation, snapshot), resolutions=resolutions
    )


__all__ = [
    "NO_SOURCE_DISAGREEMENT_RESOLUTIONS",
    "SOURCE_DISAGREEMENT_FINDING_ID_LENGTH",
    "ModeloCalculationBlockedError",
    "SourceDisagreementResolutions",
    "blocking_calculation_issues",
    "calculation_filed_before_grade_cap",
    "calculation_screen_outdated",
    "gate_refuses",
    "note_subject_facts",
    "proven_zero_calculation_issues",
    "require_no_blocking_calculation_notes",
    "require_work_unit_calculation_screen_current",
    "require_work_unit_calculation_unblocked",
    "saved_calculation_filed_before_grade_cap",
    "saved_calculation_screen_outdated",
]
