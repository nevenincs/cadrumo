"""Where a declaration stands in the filing journey, and the one thing to do next.

Four steps, each decided from facts the form and the lifecycle already carry:
fill in (no field still needs the filer, no value is still assumed and no
change is left unapplied), calculate (a calculation exists and nothing changed
since, neither a staged change nor the filer's records), check (the current
calculation is verified and nothing blocks filing) and record filing (the
declaration is recorded as filed). The first step not
done is the current one, and the next-action line names it with the key that
performs it, so the filer is never left to guess what comes next.

An assumed value, one the calculation holds that nobody is recorded as having
entered, keeps filling in open and withholds both the file for the AEAT and
recording the filing until the filer confirms it or types another: an
unentered value in a box the declaration files is exactly the suspicious zero
that must be surfaced before filing, and the file is what reaches the AEAT.
Anything that blocks filing, whether the check or the calculation found it,
withholds both in the same way. A calculation note the check decides on its own
evidence (an empty withholdings detail the filer may attest, say) waits for the
check: while it is all that blocks and the current calculation is unchecked,
the next action is the check, never "resolve", since only the check can say
whether it stands; the check also judges any value still missing. Recording a filing only records it in Cadrumo,
so a verified declaration is offered the file to take to the AEAT first, and
recording the filing once a file made from the current calculation exists: the
next-action line carries one action at a time. A file made from an earlier
calculation no longer matches the declaration, so it is to be created again,
never recorded.

Nothing here is inferred beyond those facts. In particular a step is never
shown done because its signal is missing: an unverified calculation is simply
not checked, and a verification that found something to resolve sends the
filer to what it found rather than back to verifying. The count beside a step
counts what that step resolves, as the header's chips count it: filling in
counts the values still missing, boxes and findings alike, and resolving
counts what blocks filing and any missing value only a finding names. What a
page that does not apply this period holds is never to do, so it neither
keeps filling in open nor is counted on the next-action line. A blocked
step's mark is drawn in the error colour, as every blocker mark is.

The next-action line always fits one line: it keeps its key and, when the
words run out of room, shortens the words rather than wrapping.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final

from rich.cells import cell_len
from textual.content import Content

from .....application.modelo.work_form_models import ModeloWorkForm
from .....application.modelo.work_form_next_step import (
    ModeloFormNextAction,
    awaiting_the_check,
    blocking_count,
    form_next_step,
    to_do_counts,
)
from .....application.modelo.work_form_wording import date_text, day_text
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .....domain.modelos.verification_report import VerificationCompletenessStatus
from ...components.cell_text import ellipsize
from .issue_scale import blocks_marked
from .vocabulary import BLOCKS_MARK, DONE_MARK, HERE_MARK, WorkbenchMark


class WorkbenchStep(StrEnum):
    """The steps of filing one declaration, in order."""

    FILL = "fill"
    CALCULATE = "calculate"
    REVIEW = "review"
    FILE = "file"


class StepStatus(StrEnum):
    """How far one step has got."""

    DONE = "done"
    CURRENT = "current"
    BLOCKED = "blocked"
    PENDING = "pending"


_STEP_SEPARATOR: Final[str] = " ── "
_STATUS_MARKS: Final[dict[StepStatus, WorkbenchMark | None]] = {
    StepStatus.DONE: DONE_MARK,
    StepStatus.CURRENT: HERE_MARK,
    StepStatus.BLOCKED: BLOCKS_MARK,
    # A step not started carries no mark and is dimmed, so it reads as not
    # done in greyscale without a glyph of its own.
    StepStatus.PENDING: None,
}
_PENDING_STYLE: Final[str] = "dim"
_NEXT_LINE_LOCALE_KEY: Final[str] = "tui.modelo.workbench.next_line"
_DATED_ACTIONS: Final[frozenset[ModeloFormNextAction]] = frozenset(
    {ModeloFormNextAction.EXPORT_AGAIN, ModeloFormNextAction.RECORD_AFTER_FILE}
)
"""Next actions that name the day the latest file was created."""


@dataclass(frozen=True, slots=True)
class StepState:
    """One step and how far it has got."""

    step: WorkbenchStep
    status: StepStatus


@dataclass(frozen=True, slots=True)
class WorkbenchProgress:
    """The journey's state, the next action it offers, and when the filing was recorded, once it is.

    ``assumed`` counts the assumed values on pages that apply this period and
    ``blocking`` what blocks filing, as the header's chip counts it; while
    either is not zero, neither the file for the AEAT nor recording the filing
    is offered.
    """

    steps: tuple[StepState, ...]
    next_action: ModeloFormNextAction
    count: int
    recorded_at: datetime | None = None
    assumed: int = 0
    blocking: int = 0
    #: When the latest file for the AEAT was created, once one was; the next-action line names that day.
    file_created_at: datetime | None = None
    #: Whether the values still to fill in are named only by findings, such as a table's record values,
    #: so the findings list, not the next box, leads to them.
    findings_lead: bool = False

    @property
    def filing_withheld(self) -> bool:
        """Whether an assumed value or something that blocks filing withholds the file and the recording."""
        return self.assumed > 0 or self.blocking > 0


def workbench_progress(form: ModeloWorkForm, *, staged: int, verified: bool, filed: bool) -> WorkbenchProgress:
    """Place a declaration on the filing journey from its form and lifecycle facts.

    Once nothing withholds it, a verified declaration is offered the file for
    the AEAT, then recording the filing once a file made from the current
    calculation exists, and the file again when the only one is from an
    earlier calculation.

    A declaration recorded as filed is done whatever its form still marks. A
    verified one is not sent back to filing in the boxes verification already
    accepted, but an assumed value still keeps filling in open: only the filer
    can say it is right. Every step shows whether it is done, wherever it sits;
    the first step not done is the current one.

    When nothing blocks and only values are missing, the next action is
    filling them in, never resolving what blocks; where findings alone name
    those values, the findings list leads to them (``findings_lead``).
    """
    counts = to_do_counts(form)
    assumed = counts.default_to_confirm
    blocked = counts.blocked
    blocking = blocking_count(form)
    clean = staged == 0
    done = {
        WorkbenchStep.FILL: clean and _filling_is_done(filed, verified, counts.needs_input, assumed),
        WorkbenchStep.CALCULATE: clean and _calculation_is_done(form, filed),
        WorkbenchStep.REVIEW: clean and _review_is_done(filed, verified, blocked, blocking),
        WorkbenchStep.FILE: clean and filed,
    }
    steps = _step_states(done, blocked=blocked, blocking=blocking, awaiting=awaiting_the_check(form), form=form)
    step = form_next_step(form, verified=verified, filed=filed)
    if staged:
        # Changes held here come before anything the form offers.
        step = step.model_copy(update={"action": ModeloFormNextAction.APPLY, "count": staged, "findings_lead": False})
    return WorkbenchProgress(
        steps=steps,
        next_action=step.action,
        count=step.count,
        recorded_at=step.recorded_at if step.action is ModeloFormNextAction.RECORDED else None,
        assumed=0 if filed else assumed,
        blocking=0 if filed else blocking,
        file_created_at=step.file_created_at,
        findings_lead=step.findings_lead,
    )


def _filling_is_done(filed: bool, verified: bool, to_fill: int, assumed: int) -> bool:
    return filed or ((verified or to_fill == 0) and assumed == 0)


def _calculation_is_done(form: ModeloWorkForm, filed: bool) -> bool:
    return form.calculation_revision_id is not None and (filed or not form.calculation_out_of_date)


def _review_is_done(filed: bool, verified: bool, blocked: int, blocking: int) -> bool:
    return filed or (verified and blocked == 0 and blocking == 0)


def _step_states(
    done: Mapping[WorkbenchStep, bool],
    *,
    blocked: int,
    blocking: int,
    awaiting: int,
    form: ModeloWorkForm,
) -> tuple[StepState, ...]:
    steps: list[StepState] = []
    current_found = False
    for step in WorkbenchStep:
        if done[step]:
            steps.append(StepState(step, StepStatus.DONE))
        elif not current_found:
            current_found = True
            is_blocked = step is WorkbenchStep.REVIEW and (
                blocked > 0 or blocking > awaiting or form.verification is VerificationCompletenessStatus.BLOCKED
            )
            steps.append(StepState(step, StepStatus.BLOCKED if is_blocked else StepStatus.CURRENT))
        else:
            steps.append(StepState(step, StepStatus.PENDING))
    return tuple(steps)


def _step_name(step: WorkbenchStep) -> str:
    return tr(f"tui.modelo.workbench.step.{step.value}")


def stepper_text(progress: WorkbenchProgress) -> Content:
    """Render the steps as one line: a mark and a name each.

    A step not started is dimmed and unmarked, and a blocked step's mark is
    drawn in the error colour.
    """
    parts: list[Content] = []
    for state in progress.steps:
        mark = _STATUS_MARKS[state.status]
        if mark is None:
            parts.append(Content.styled(_step_name(state.step), _PENDING_STYLE))
        else:
            parts.append(blocks_marked(f"{mark.glyph} {_step_name(state.step)}"))
    return Content(_STEP_SEPARATOR).join(parts)


def stepper_marks(progress: WorkbenchProgress) -> tuple[WorkbenchMark, ...]:
    """The marks the stepper draws, one per step that carries one."""
    return tuple(mark for state in progress.steps if (mark := _STATUS_MARKS[state.status]) is not None)


def next_action_text(progress: WorkbenchProgress, language: OutputLanguage) -> str:
    """Render the next action in the filer's language, without its key."""
    action = progress.next_action
    if action is ModeloFormNextAction.RECORDED:
        if progress.recorded_at is None:
            return f"{DONE_MARK.glyph} {_step_name(WorkbenchStep.FILE)}"
        return tr("tui.modelo.workbench.next.recorded", date=date_text(progress.recorded_at.date(), language))
    if action in _DATED_ACTIONS and progress.file_created_at is not None:
        return tr(f"tui.modelo.workbench.next.{action.value}", date=day_text(progress.file_created_at, language))
    return tr(f"tui.modelo.workbench.next.{action.value}", count=progress.count)


def fit_next_line(action: str, key: str, width: int) -> str:
    """The next-action line in at most ``width`` cells: the one action and its key.

    The key is never dropped; the action's words are shortened, ending in an
    ellipsis, before the line is allowed to wrap.
    """
    if not key:
        return action if cell_len(action) <= width else ellipsize(action, width)
    line = tr(_NEXT_LINE_LOCALE_KEY, action=action, key=key)
    if cell_len(line) <= width:
        return line
    frame = cell_len(tr(_NEXT_LINE_LOCALE_KEY, action="", key=key))
    return tr(_NEXT_LINE_LOCALE_KEY, action=ellipsize(action, max(width - frame, 1)), key=key)


__all__ = [
    "StepState",
    "StepStatus",
    "WorkbenchProgress",
    "WorkbenchStep",
    "fit_next_line",
    "next_action_text",
    "stepper_marks",
    "stepper_text",
    "workbench_progress",
]
