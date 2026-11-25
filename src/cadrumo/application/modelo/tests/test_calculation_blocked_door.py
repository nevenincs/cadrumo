"""A calculation the note gate withholds an action from names the door that leads on, in served words.

A stale screen is put right by calculating the declaration again, a blocking
note is read on the declaration's status, and a filing recorded before screens
existed has no action that clears it: the refusal says so as an operator
decision rather than offering nothing.
"""

from __future__ import annotations

import pytest

from ....core.errors.error_codes import resolve_error_message
from ....core.operator_action_enums import (
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.calculation_revision_sources import DISAGREEMENT_REASONS
from ...operations.error_detail import build_operation_error_detail
from ...operations.next_step import OperationCalculateWorkStepV1, OperationOpenWorkStepV1
from ...operator_surface.action_targets import resolve_recorded_precondition_action
from ..calculation_note_gate import ModeloCalculationBlockedError, require_work_unit_calculation_unblocked
from ..calculation_notes import GATE_REFUSED_REASONS
from ..preconditions import build_modelo_precondition_failure_for_scenario
from .test_work_form_gate_agreement import Note, work_form_gate_agreement_revision, work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES = ("en", "es", "ca", "hu")
_ACTIONS = ("verify", "file", "export", "report")
_LEAVES = {
    "verify": "modelo.work.verify",
    "file": "modelo.work.file",
    "export": "modelo.export",
    "report": "modelo.work.report",
}


def _refused(
    operation: PinnedAuthorityOperation, action: str, *notes: Note, stale: bool
) -> ModeloCalculationBlockedError:
    unit = work_unit(operation)
    revision = work_form_gate_agreement_revision(
        operation, unit, *(note.issue() for note in notes), stale=(None,) if stale else None
    )
    with pytest.raises(ModeloCalculationBlockedError) as refused:
        require_work_unit_calculation_unblocked(work_unit=unit, revision=revision, action=action, operation=operation)
    return refused.value


@pytest.mark.parametrize("action", _ACTIONS)
def test_a_stale_screen_names_calculating_the_declaration_again(
    operation: PinnedAuthorityOperation, action: str
) -> None:
    unit = work_unit(operation)
    error = _refused(operation, action, stale=True)

    detail = build_operation_error_detail(error)
    assert detail is not None
    assert detail.refusal_words is not None and "{" not in detail.refusal_words
    assert "REFUSED_MODELO_CALCULATION_BLOCKED" not in detail.refusal_words
    verdict = detail.precondition_verdict()
    assert verdict is not None and verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.calculate"
    assert verdict.no_recovery_outcome is None
    assert verdict.conditionality is ActionConditionality.IMMEDIATE
    (binding,) = verdict.argument_bindings
    assert binding.argument_name == "work_unit_id" and binding.value == unit.work_unit_id
    assert binding.status is ActionArgumentStatus.RESOLVED
    assert error.terminal_precondition_verdict is not None
    assert error.terminal_precondition_verdict.failed_condition_id == f"{_LEAVES[action]}.calculation_notes.clear"

    resolved = resolve_recorded_precondition_action(verdict)
    assert resolved.action is not None and resolved.action.cli_path is not None
    assert resolved.action.cli_path[-3:] == ("modelo", "work", "calculate")
    assert not resolved.missing_argument_names

    assert isinstance(detail.next_step, OperationCalculateWorkStepV1)
    assert detail.next_step.work_unit_id == unit.work_unit_id
    assert detail.next_step.words


@pytest.mark.parametrize("action", _ACTIONS)
def test_a_blocking_note_names_the_declaration_that_holds_it(operation: PinnedAuthorityOperation, action: str) -> None:
    unit = work_unit(operation)
    reason = sorted(GATE_REFUSED_REASONS - DISAGREEMENT_REASONS)[0]
    error = _refused(operation, action, Note(reason), stale=False)

    detail = build_operation_error_detail(error)
    assert detail is not None
    assert detail.context_mapping()["reason"] == reason
    assert detail.refusal_words is not None and "{" not in detail.refusal_words
    assert "REFUSED_MODELO_CALCULATION_BLOCKED" not in detail.refusal_words
    verdict = detail.precondition_verdict()
    assert verdict is not None and verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.work.status"
    (binding,) = verdict.argument_bindings
    assert binding.value == unit.work_unit_id
    assert isinstance(detail.next_step, OperationOpenWorkStepV1)
    assert detail.next_step.work_unit_id == unit.work_unit_id


@pytest.mark.parametrize("action", _ACTIONS)
def test_a_filing_recorded_before_screens_existed_is_an_operator_decision(action: str) -> None:
    leaf = _LEAVES[action]
    scenario = f"{leaf}.calculation_notes.filed_before_grade_cap"
    failure = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=leaf,
        scenario_id=scenario,
        evidence_id=f"{scenario}.observation",
        evidence_values={
            "work_unit_id": "w",
            "gated_step": action,
            "reason": "filed_before_grade_cap",
            "withheld": True,
        },
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
    )
    assert failure.verdict.action is None
    assert failure.verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION


@pytest.mark.parametrize("stale", [True, False], ids=["stale_screen", "blocking_note"])
def test_the_served_words_are_finished_sentences_in_every_language(
    operation: PinnedAuthorityOperation, stale: bool
) -> None:
    reason = sorted(GATE_REFUSED_REASONS - DISAGREEMENT_REASONS)[0]
    error = _refused(operation, "verify", *(() if stale else (Note(reason),)), stale=stale)

    for locale in _LOCALES:
        words = resolve_error_message(error, locale=locale)
        assert words
        assert "%{" not in words and "{" not in words
        assert "errors." not in words and "application.modelo" not in words
