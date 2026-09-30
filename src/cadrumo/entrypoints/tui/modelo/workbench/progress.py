"""Where a declaration stands in the filing journey, and the one thing to do next.

Four steps, each decided from facts the form and the lifecycle already carry:
fill in (no field still needs the filer, no value is still assumed and no
change is left unapplied), calculate (a calculation exists and nothing changed
since), check (the current calculation is verified and nothing blocks filing)
and record filing (the declaration is recorded as filed). The first step not
done is the current one, and the next-action line names it with the key that
performs it, so the filer is never left to guess what comes next.

An assumed value, one the calculation holds that nobody is recorded as having
entered, keeps filling in open and withholds recording the filing until the
filer confirms it or types another: an unentered value in a box the
declaration files is exactly the suspicious zero that must be surfaced before
filing. Recording a filing only records it in Cadrumo, so a verified
declaration is offered the file to take to the AEAT first, and recording once
it has been filed there.

Nothing here is inferred beyond those facts. In particular a step is never
shown done because its signal is missing: an unverified calculation is simply
not checked, and a verification that found something to resolve sends the
filer to what it found rather than back to verifying. What a page that does
not apply this period holds is never to do, so it neither keeps filling in
open nor is counted on the next-action line.

The next-action line always fits one line: it keeps its key and, when the
words run out of room, shortens the words rather than wrapping.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final

from rich.cells import cell_len
from rich.text import Text

from .....application.modelo.work_form_models import ModeloWorkForm
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .....domain.modelos.verification_report import VerificationCompletenessStatus
from .navigator import to_do_counts
from .vocabulary import BLOCKS_MARK, DONE_MARK, HERE_MARK, WorkbenchMark
from .wording import date_text


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


class NextAction(StrEnum):
    """The one action the next-action line offers."""

    APPLY = "apply"
    FILL = "fill"
    CONFIRM = "confirm"
    CALCULATE = "calculate"
    RESOLVE = "resolve"
    VERIFY = "verify"
    EXPORT = "export"
    RECORDED = "recorded"


_UNRESOLVED_VERDICTS: Final[frozenset[VerificationCompletenessStatus]] = frozenset(
    {VerificationCompletenessStatus.INCOMPLETE, VerificationCompletenessStatus.BLOCKED}
)
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
_RECORD_LOCALE_KEY: Final[str] = "tui.modelo.workbench.next.record"
_RECORD_KEY: Final[str] = "F8"
_NEXT_LINE_LOCALE_KEY: Final[str] = "tui.modelo.workbench.next_line"
_ELLIPSIS: Final[str] = "…"


@dataclass(frozen=True, slots=True)
class StepState:
    """One step and how far it has got."""

    step: WorkbenchStep
    status: StepStatus


@dataclass(frozen=True, slots=True)
class WorkbenchProgress:
    """The journey's state, the next action it offers, and when the filing was recorded, once it is."""

    steps: tuple[StepState, ...]
    next_action: NextAction
    count: int
    recorded_at: datetime | None = None


def workbench_progress(form: ModeloWorkForm, *, staged: int, verified: bool, filed: bool) -> WorkbenchProgress:
    """Place a declaration on the filing journey from its form and lifecycle facts.

    A declaration recorded as filed is done whatever its form still marks. A
    verified one is not sent back to filing in the boxes verification already
    accepted, but an assumed value still keeps filling in open: only the filer
    can say it is right. Every step shows whether it is done, wherever it sits;
    the first step not done is the current one.
    """
    counts = to_do_counts(form)
    to_fill = counts.needs_input
    assumed = counts.default_to_confirm
    blocked = counts.blocked
    clean = staged == 0
    filled = filed or ((verified or to_fill == 0) and assumed == 0)
    done = {
        WorkbenchStep.FILL: clean and filled,
        WorkbenchStep.CALCULATE: clean and form.calculation_revision_id is not None,
        WorkbenchStep.REVIEW: clean and verified and blocked == 0,
        WorkbenchStep.FILE: clean and filed,
    }
    steps: list[StepState] = []
    current_found = False
    for step in WorkbenchStep:
        if done[step]:
            steps.append(StepState(step, StepStatus.DONE))
        elif not current_found:
            current_found = True
            is_blocked = step is WorkbenchStep.REVIEW and (
                blocked > 0 or form.verification is VerificationCompletenessStatus.BLOCKED
            )
            steps.append(StepState(step, StepStatus.BLOCKED if is_blocked else StepStatus.CURRENT))
        else:
            steps.append(StepState(step, StepStatus.PENDING))
    action, count = _next(
        form, staged=staged, to_fill=to_fill, assumed=assumed, blocked=blocked, verified=verified, filed=filed
    )
    recorded_at = form.filing.recorded_at if action is NextAction.RECORDED and form.filing is not None else None
    return WorkbenchProgress(steps=tuple(steps), next_action=action, count=count, recorded_at=recorded_at)


def _next(
    form: ModeloWorkForm, *, staged: int, to_fill: int, assumed: int, blocked: int, verified: bool, filed: bool
) -> tuple[NextAction, int]:
    if staged:
        return NextAction.APPLY, staged
    if filed:
        return NextAction.RECORDED, 0
    if to_fill and not verified:
        return NextAction.FILL, to_fill
    if assumed:
        return NextAction.CONFIRM, assumed
    if verified:
        return NextAction.EXPORT, 0
    if form.calculation_revision_id is None:
        return NextAction.CALCULATE, 0
    if blocked or form.verification in _UNRESOLVED_VERDICTS:
        return NextAction.RESOLVE, max(blocked, len(form.issues))
    return NextAction.VERIFY, 0


def _step_name(step: WorkbenchStep) -> str:
    return tr(f"tui.modelo.workbench.step.{step.value}")


def stepper_text(progress: WorkbenchProgress) -> Text:
    """Render the steps as one line: a mark and a name each, a step not started dimmed and unmarked."""
    line = Text()
    for index, state in enumerate(progress.steps):
        if index:
            line.append(_STEP_SEPARATOR)
        mark = _STATUS_MARKS[state.status]
        if mark is None:
            line.append(_step_name(state.step), style=_PENDING_STYLE)
        else:
            line.append(f"{mark.glyph} {_step_name(state.step)}")
    return line


def stepper_marks(progress: WorkbenchProgress) -> tuple[WorkbenchMark, ...]:
    """The marks the stepper draws, one per step that carries one."""
    return tuple(mark for state in progress.steps if (mark := _STATUS_MARKS[state.status]) is not None)


def next_action_text(progress: WorkbenchProgress, language: OutputLanguage) -> str:
    """Render the next action in the filer's language, without its key."""
    action = progress.next_action
    if action is NextAction.RECORDED:
        if progress.recorded_at is None:
            return f"{DONE_MARK.glyph} {_step_name(WorkbenchStep.FILE)}"
        return tr("tui.modelo.workbench.next.recorded", date=date_text(progress.recorded_at.date(), language))
    return tr(f"tui.modelo.workbench.next.{action.value}", count=progress.count)


def record_filing_text() -> str:
    """The second half of a verified declaration's next line: record the filing once it is filed with the AEAT."""
    return f"{tr(_RECORD_LOCALE_KEY)} [{_RECORD_KEY}]"


def _shortened(text: str, room: int) -> str:
    if cell_len(text) <= room:
        return text
    kept = ""
    for character in text:
        if cell_len(kept + character + _ELLIPSIS) > room:
            break
        kept += character
    return kept.rstrip() + _ELLIPSIS


def fit_next_line(action: str, key: str, width: int, *, then: str | None = None) -> str:
    """The next-action line in at most ``width`` cells: the action, its key, and ``then`` when it fits.

    ``then`` is the step after this one, dropped first. The key is never
    dropped; the action's words are shortened, ending in an ellipsis, before
    the line is allowed to wrap.
    """
    if not key:
        full = action if then is None else f"{action} · {then}"
        return full if cell_len(full) <= width else _shortened(action, width)
    line = tr(_NEXT_LINE_LOCALE_KEY, action=action, key=key)
    if then is not None and cell_len(f"{line} · {then}") <= width:
        return f"{line} · {then}"
    if cell_len(line) <= width:
        return line
    frame = cell_len(tr(_NEXT_LINE_LOCALE_KEY, action="", key=key))
    return tr(_NEXT_LINE_LOCALE_KEY, action=_shortened(action, max(width - frame, 1)), key=key)


__all__ = [
    "NextAction",
    "StepState",
    "StepStatus",
    "WorkbenchProgress",
    "WorkbenchStep",
    "fit_next_line",
    "next_action_text",
    "record_filing_text",
    "stepper_marks",
    "stepper_text",
    "workbench_progress",
]
