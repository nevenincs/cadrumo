"""The journey follows the declaration's lifecycle, and an assumed value holds it until the filer confirms it.

Placed on the synthetic form: a declaration recorded as filed is done whatever
its form still marks and says when it was recorded; a verified one offers the
file for the AEAT first and recording the filing after; an assumed value keeps
filling in open and withholds recording, even on a verified declaration; and a
step that is done shows as done even after the current one. The stepper marks
the current step as "you are here", a finished one as done and a blocked check
as blocking, and leaves a step not started unmarked.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ......application.modelo.work_form_models import (
    ModeloFormAttention,
    ModeloFormCalculationNote,
    ModeloFormExport,
    ModeloFormFiling,
    ModeloWorkForm,
)
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ......domain.modelos.verification_report import VerificationCompletenessStatus
from ..progress import (
    NextAction,
    StepStatus,
    WorkbenchProgress,
    WorkbenchStep,
    next_action_text,
    stepper_marks,
    stepper_text,
    workbench_progress,
)
from ..vocabulary import DONE_MARK, HERE_MARK
from ..wording import day_text
from .workbench_fixture import synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _statuses(progress: WorkbenchProgress) -> dict[WorkbenchStep, StepStatus]:
    return {state.step: state.status for state in progress.steps}


def _assumed(form: ModeloWorkForm, count: int) -> ModeloWorkForm:
    return form.model_copy(update={"counts": form.counts.model_copy(update={"default_to_confirm": count})})


def test_a_filed_declaration_is_done_whatever_its_form_still_marks_and_says_when() -> None:
    recorded = datetime(2026, 4, 15, 10, 0, tzinfo=UTC)
    form = synthetic_form(needs_input=True).model_copy(update={"filing": ModeloFormFiling(recorded_at=recorded)})

    progress = workbench_progress(form, staged=0, verified=True, filed=True)
    with override_settings(cadrumo_output_language="en"):
        line = next_action_text(progress, OutputLanguage.EN)

    assert set(_statuses(progress).values()) == {StepStatus.DONE}
    assert progress.next_action is NextAction.RECORDED
    assert line == "Recorded as filed on 15/04/2026"


def test_a_verified_declaration_offers_the_file_first_and_recording_after_one_at_a_time() -> None:
    form = synthetic_form(needs_input=True)
    revision = form.calculation_revision_id
    assert revision is not None
    filed_file = ModeloFormExport(
        exported_at=datetime(2026, 4, 2, 9, 0, tzinfo=UTC), calculation_revision_id=revision, current=True
    )
    progress = workbench_progress(form, staged=0, verified=True, filed=False)
    exported = workbench_progress(
        form.model_copy(update={"last_export": filed_file}), staged=0, verified=True, filed=False
    )
    with override_settings(cadrumo_output_language="en"):
        line = next_action_text(progress, OutputLanguage.EN)
        record = next_action_text(exported, OutputLanguage.EN)
        day = day_text(filed_file.exported_at, OutputLanguage.EN)
        expected_record = tr("tui.modelo.workbench.next.record_after_file", date=day)

    statuses = _statuses(progress)
    assert statuses[WorkbenchStep.FILL] is StepStatus.DONE
    assert statuses[WorkbenchStep.REVIEW] is StepStatus.DONE
    assert statuses[WorkbenchStep.FILE] is StepStatus.CURRENT
    assert progress.next_action is NextAction.EXPORT
    assert line == "Create the file to file with AEAT"
    assert exported.next_action is NextAction.RECORD_AFTER_FILE
    assert record == expected_record
    assert day in record


def test_an_assumed_value_keeps_filling_in_open_and_withholds_recording() -> None:
    form = _assumed(synthetic_form(needs_input=False), 3)

    unverified = workbench_progress(form, staged=0, verified=False, filed=False)
    verified = workbench_progress(form, staged=0, verified=True, filed=False)

    for progress in (unverified, verified):
        assert progress.next_action is NextAction.CONFIRM
        assert progress.count == 3
        assert _statuses(progress)[WorkbenchStep.FILL] is StepStatus.CURRENT
        assert _statuses(progress)[WorkbenchStep.FILE] is not StepStatus.DONE
    assert _statuses(verified)[WorkbenchStep.REVIEW] is StepStatus.DONE


def test_without_assumed_values_filling_in_is_done_and_the_declaration_is_checked_next() -> None:
    progress = workbench_progress(_assumed(synthetic_form(needs_input=False), 0), staged=0, verified=False, filed=False)

    assert _statuses(progress)[WorkbenchStep.FILL] is StepStatus.DONE
    assert progress.next_action is NextAction.VERIFY


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


def test_the_stepper_marks_where_the_filer_is_and_leaves_a_step_not_started_unmarked() -> None:
    progress = workbench_progress(
        synthetic_form(calculated=True, needs_input=True), staged=0, verified=False, filed=False
    )
    with override_settings(cadrumo_output_language="en"):
        line = stepper_text(progress)

    assert line.plain == "▸ Fill in ── ✓ Calculate ── Check ── Record filing"
    assert stepper_marks(progress) == (HERE_MARK, DONE_MARK)
    dimmed = [span for span in line.spans if "dim" in str(span.style)]
    assert [line.plain[span.start : span.end] for span in dimmed] == ["Check", "Record filing"]


def _noted(form: ModeloWorkForm, *reasons: str) -> ModeloWorkForm:
    """The form whose latest calculation left blocking notes of ``reasons``."""
    notes = tuple(ModeloFormCalculationNote(reason=reason, attention=ModeloFormAttention.BLOCKS) for reason in reasons)
    return form.model_copy(update={"calculation_notes": notes})


def test_a_note_only_the_check_decides_sends_the_unchecked_declaration_to_the_check() -> None:
    form = _noted(synthetic_form(calculated=True, needs_input=False), "withholding_detail_absent")

    progress = workbench_progress(form, staged=0, verified=False, filed=False)
    with override_settings(cadrumo_output_language="en"):
        line = next_action_text(progress, OutputLanguage.EN)

    assert progress.next_action is NextAction.VERIFY
    assert line == "Check the declaration"
    assert progress.filing_withheld, "it still withholds filing until the check has spoken"
    assert _statuses(progress)[WorkbenchStep.REVIEW] is StepStatus.CURRENT


def test_a_note_the_check_does_not_decide_still_sends_the_filer_to_resolve_it() -> None:
    alone = _noted(synthetic_form(calculated=True, needs_input=False), "unrouted_observation")
    beside = _noted(
        synthetic_form(calculated=True, needs_input=False), "withholding_detail_absent", "unrouted_observation"
    )

    assert workbench_progress(alone, staged=0, verified=False, filed=False).next_action is NextAction.RESOLVE
    mixed = workbench_progress(beside, staged=0, verified=False, filed=False)
    assert mixed.next_action is NextAction.RESOLVE
    assert mixed.count == 2, "the count is the chip's: everything that blocks filing"
    assert _statuses(mixed)[WorkbenchStep.REVIEW] is StepStatus.BLOCKED


def test_once_checked_a_note_the_check_decides_no_longer_sends_the_filer_back_to_it() -> None:
    checked = _noted(synthetic_form(calculated=True, needs_input=False), "withholding_detail_absent").model_copy(
        update={"verification": VerificationCompletenessStatus.BLOCKED}
    )

    assert workbench_progress(checked, staged=0, verified=False, filed=False).next_action is NextAction.RESOLVE
