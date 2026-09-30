"""The journey follows the declaration's lifecycle and asks only for what needs the filer.

Placed on the synthetic form: a filed declaration is done whatever its form
still marks, a verified one offers filing, a default the filer has not
confirmed is reported beside the next action instead of holding the journey
back, and a step that is done shows as done even after the current one.
"""

from __future__ import annotations

import pytest

from ..progress import NextAction, StepStatus, WorkbenchProgress, WorkbenchStep, workbench_progress
from .workbench_fixture import synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _statuses(progress: WorkbenchProgress) -> dict[WorkbenchStep, StepStatus]:
    return {state.step: state.status for state in progress.steps}


def test_a_filed_declaration_is_done_whatever_its_form_still_marks() -> None:
    progress = workbench_progress(synthetic_form(needs_input=True), staged=0, verified=True, filed=True)

    assert set(_statuses(progress).values()) == {StepStatus.DONE}
    assert progress.next_action is NextAction.DONE
    assert progress.defaults_to_confirm == 0


def test_a_verified_declaration_offers_filing_rather_than_filling() -> None:
    progress = workbench_progress(synthetic_form(needs_input=True), staged=0, verified=True, filed=False)

    statuses = _statuses(progress)
    assert statuses[WorkbenchStep.FILL] is StepStatus.DONE
    assert statuses[WorkbenchStep.REVIEW] is StepStatus.DONE
    assert statuses[WorkbenchStep.FILE] is StepStatus.CURRENT
    assert progress.next_action is NextAction.FILE


def test_unconfirmed_defaults_are_reported_without_holding_the_journey_back() -> None:
    form = synthetic_form(needs_input=False)
    form = form.model_copy(update={"counts": form.counts.model_copy(update={"default_to_confirm": 3})})

    progress = workbench_progress(form, staged=0, verified=False, filed=False)

    assert progress.next_action is NextAction.VERIFY
    assert progress.defaults_to_confirm == 3
    assert _statuses(progress)[WorkbenchStep.FILL] is StepStatus.DONE


def test_a_done_step_shows_as_done_even_after_the_current_one() -> None:
    progress = workbench_progress(
        synthetic_form(calculated=True, needs_input=True), staged=0, verified=False, filed=False
    )

    statuses = _statuses(progress)
    assert statuses[WorkbenchStep.FILL] is StepStatus.CURRENT
    assert statuses[WorkbenchStep.CALCULATE] is StepStatus.DONE
    assert progress.next_action is NextAction.FILL


def test_staged_changes_come_first_and_undo_every_step_they_touch() -> None:
    progress = workbench_progress(synthetic_form(needs_input=False), staged=2, verified=True, filed=True)

    assert progress.next_action is NextAction.APPLY
    assert progress.count == 2
    assert StepStatus.DONE not in _statuses(progress).values()
