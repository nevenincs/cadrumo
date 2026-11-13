"""Draws where a declaration stands on the filing journey, and the one thing to do next.

The steps, their order, which are done and which is current, the action offered
next and the count it names are all served with the form (see
:mod:`~cadrumo.application.modelo.work_form_journey`); this module only picks
among the served alternatives the workbench's own session calls for and renders
them. Changes held here and not yet applied come before everything the form
offers, so the served steps for that case and the apply action are shown.

The next-action line always fits one line: it keeps its key and, when the
words run out of room, shortens the words rather than wrapping. A blocked
step's mark is drawn in the error colour, as every blocker mark is.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final

from rich.cells import cell_len
from textual.content import Content

from .....application.modelo.work_form_journey import ModeloFormStep, ModeloFormStepState, ModeloFormStepStatus
from .....application.modelo.work_form_next_step import ModeloFormNextAction
from .....application.modelo.work_form_service import ModeloWorkFormLoadV1
from .....application.modelo.work_form_wording import date_text, day_text
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from ...components.cell_text import ellipsize
from .issue_scale import blocks_marked
from .vocabulary import BLOCKS_MARK, DONE_MARK, HERE_MARK, WorkbenchMark

_STEP_SEPARATOR: Final[str] = " ── "
_STATUS_MARKS: Final[dict[ModeloFormStepStatus, WorkbenchMark | None]] = {
    ModeloFormStepStatus.DONE: DONE_MARK,
    ModeloFormStepStatus.CURRENT: HERE_MARK,
    ModeloFormStepStatus.BLOCKED: BLOCKS_MARK,
    # A step not started carries no mark and is dimmed, so it reads as not
    # done in greyscale without a glyph of its own.
    ModeloFormStepStatus.PENDING: None,
}
_PENDING_STYLE: Final[str] = "dim"
_NEXT_LINE_LOCALE_KEY: Final[str] = "tui.modelo.next_line"
_DATED_ACTIONS: Final[frozenset[ModeloFormNextAction]] = frozenset(
    {ModeloFormNextAction.EXPORT_AGAIN, ModeloFormNextAction.RECORD_AFTER_FILE}
)
"""Next actions that name the day the latest file was created."""


@dataclass(frozen=True, slots=True)
class WorkbenchProgress:
    """The journey's state, the next action it offers, and when the filing was recorded, once it is."""

    steps: tuple[ModeloFormStepState, ...]
    next_action: ModeloFormNextAction
    count: int
    recorded_at: datetime | None = None
    #: When the latest file for the AEAT was created, once one was; the next-action line names that day.
    file_created_at: datetime | None = None
    #: Whether the values still to fill in are named only by findings, such as a table's record values,
    #: so the findings list, not the next box, leads to them.
    findings_lead: bool = False


def workbench_progress(load: ModeloWorkFormLoadV1, *, staged: int) -> WorkbenchProgress:
    """The served journey, with the changes staged here, which come before anything the form offers."""
    journey = load.journey
    step = journey.next_step
    if staged:
        return WorkbenchProgress(
            steps=journey.steps_while_changes_held,
            next_action=ModeloFormNextAction.APPLY,
            count=staged,
            file_created_at=step.file_created_at,
        )
    return WorkbenchProgress(
        steps=journey.steps,
        next_action=step.action,
        count=step.count,
        recorded_at=step.recorded_at if step.action is ModeloFormNextAction.RECORDED else None,
        file_created_at=step.file_created_at,
        findings_lead=step.findings_lead,
    )


def _step_name(step: ModeloFormStep) -> str:
    return tr(f"workspace.modelo.step.{step.value}")


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
            return f"{DONE_MARK.glyph} {_step_name(ModeloFormStep.FILE)}"
        return tr("workspace.modelo.next.recorded", date=date_text(progress.recorded_at.date(), language))
    if action in _DATED_ACTIONS and progress.file_created_at is not None:
        return tr(f"workspace.modelo.next.{action.value}", date=day_text(progress.file_created_at, language))
    return tr(f"workspace.modelo.next.{action.value}", count=progress.count)


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
    "WorkbenchProgress",
    "fit_next_line",
    "next_action_text",
    "stepper_marks",
    "stepper_text",
    "workbench_progress",
]
