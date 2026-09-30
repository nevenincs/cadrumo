"""Where a declaration stands in the filing journey, and the one thing to do next.

Four steps, each decided from facts the form and the lifecycle already carry:
fill (no field still needs the filer and no change is left unapplied),
calculate (a calculation exists and nothing changed since), review (the
current calculation is verified and nothing blocks filing) and file (the
declaration is recorded as filed). The first step not done is the current one,
and the next-action line names it with the key that performs it, so the filer
is never left to guess what comes next.

Nothing here is inferred beyond those facts. In particular a step is never
shown done because its signal is missing: an unverified calculation is simply
not reviewed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from .....application.modelo.work_form_models import ModeloWorkForm
from .....core.i18n.render import tr


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
    CALCULATE = "calculate"
    RESOLVE = "resolve"
    VERIFY = "verify"
    FILE = "file"
    DONE = "done"


_STEP_SEPARATOR: Final[str] = " ── "
_STATUS_MARKS: Final[dict[StepStatus, str]] = {
    StepStatus.DONE: "✓",
    StepStatus.CURRENT: "●",
    StepStatus.BLOCKED: "▲",
    StepStatus.PENDING: "○",
}


@dataclass(frozen=True, slots=True)
class StepState:
    """One step and how far it has got."""

    step: WorkbenchStep
    status: StepStatus


@dataclass(frozen=True, slots=True)
class WorkbenchProgress:
    """The journey's state, the next action it offers and how many defaults remain unconfirmed."""

    steps: tuple[StepState, ...]
    next_action: NextAction
    count: int
    defaults_to_confirm: int = 0


def workbench_progress(form: ModeloWorkForm, *, staged: int, verified: bool, filed: bool) -> WorkbenchProgress:
    """Place a declaration on the filing journey from its form and lifecycle facts.

    The lifecycle facts dominate: a verified declaration has passed its checks
    and a filed one has been filed, whatever its form still marks, so neither is
    sent back to filling. Filling asks only for boxes that need the filer; a
    default the filer has not confirmed is reported beside the next action
    rather than holding the journey back. Every step shows whether it is done,
    wherever it sits; the first step not done is the current one.
    """
    to_fill = form.counts.needs_input
    blocked = form.counts.blocked
    clean = staged == 0
    done = {
        WorkbenchStep.FILL: clean and (filed or verified or to_fill == 0),
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
            is_blocked = step is WorkbenchStep.REVIEW and blocked > 0
            steps.append(StepState(step, StepStatus.BLOCKED if is_blocked else StepStatus.CURRENT))
        else:
            steps.append(StepState(step, StepStatus.PENDING))
    action, count = _next(form, staged=staged, to_fill=to_fill, blocked=blocked, verified=verified, filed=filed)
    advisory = 0 if verified or filed or action is NextAction.APPLY else form.counts.default_to_confirm
    return WorkbenchProgress(steps=tuple(steps), next_action=action, count=count, defaults_to_confirm=advisory)


def _next(
    form: ModeloWorkForm, *, staged: int, to_fill: int, blocked: int, verified: bool, filed: bool
) -> tuple[NextAction, int]:
    if staged:
        return NextAction.APPLY, staged
    if filed:
        return NextAction.DONE, 0
    if verified:
        return NextAction.FILE, 0
    if to_fill:
        return NextAction.FILL, to_fill
    if form.calculation_revision_id is None:
        return NextAction.CALCULATE, 0
    if blocked:
        return NextAction.RESOLVE, blocked
    return NextAction.VERIFY, 0


def _step_name(step: WorkbenchStep) -> str:
    return tr(f"tui.modelo.workbench.step.{step.value}")


def stepper_text(progress: WorkbenchProgress) -> str:
    """Render the steps as one line of marks and names."""
    parts = [f"{_STATUS_MARKS[state.status]} {_step_name(state.step)}" for state in progress.steps]
    return _STEP_SEPARATOR.join(parts)


def next_action_text(progress: WorkbenchProgress) -> str:
    """Render the next-action line in the filer's language."""
    return tr(f"tui.modelo.workbench.next.{progress.next_action.value}", count=progress.count)


def defaults_text(progress: WorkbenchProgress) -> str:
    """Say how many defaults the filer has not confirmed, or nothing when none remain."""
    if not progress.defaults_to_confirm:
        return ""
    return tr("tui.modelo.workbench.defaults_to_confirm", count=progress.defaults_to_confirm)


__all__ = [
    "NextAction",
    "StepState",
    "StepStatus",
    "WorkbenchProgress",
    "WorkbenchStep",
    "defaults_text",
    "next_action_text",
    "stepper_text",
    "workbench_progress",
]
