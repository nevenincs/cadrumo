"""A filing window that has not opened refuses local filing and names the export door.

Local filing waits for the window, but the verified revision can be exported
now. The refusal therefore carries the export action addressed to the same
modelo, year and period, and the date the window opens. A closed window keeps
its terminal refusal, because no door exists there.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from ....application.operator_surface.action_targets import resolve_recorded_precondition_action
from ....core.operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    NoRecoveryOutcome,
)
from ....core.period import Period
from ....core.time.clock import now
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.deadlines.festivos import DeadlineHolidayCoverage
from ....domain.deadlines.models import ModeloDeadline, ObligationStatus
from ..abort import WorkflowAbortReason
from ..deadline_decisions import decide_filing_deadline
from ..errors import WorkflowAbortSignalError
from ..run_models import WorkflowPurpose, WorkflowStep

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _second_quarter_obligation(status: ObligationStatus) -> ModeloDeadline:
    year = filing_year_envelope().horizon
    closes_on = date(year, 7, 20)
    return ModeloDeadline(
        modelo="303",
        period=Period.from_year_and_code(year, "2T"),
        opens_on=date(year, 4, 1),
        closes_on=closes_on,
        adjusted_closes_on=closes_on,
        holiday_coverage=DeadlineHolidayCoverage.NOT_SHIFTED,
        shift_reason="none",
        status=status,
    )


def _abort(
    obligation: ModeloDeadline, *, today: date, operation: PinnedAuthorityOperation
) -> tuple[WorkflowAbortReason, WorkflowStep]:
    steps: list[WorkflowStep] = []
    with pytest.raises(WorkflowAbortSignalError) as aborted:
        decide_filing_deadline(
            obligation=obligation,
            target_modelo=None,
            target_period=None,
            today=today,
            started=now(),
            steps=steps,
            purpose=WorkflowPurpose.FILE,
            authority_operation=operation,
        )
    return aborted.value.reason, steps[-1]


def test_an_unopened_window_names_the_export_door_with_its_arguments(operation: PinnedAuthorityOperation) -> None:
    """The refusal addresses the export of the same modelo, year and period and states the opening date."""
    obligation = _second_quarter_obligation(ObligationStatus.UPCOMING)

    reason, step = _abort(obligation, today=obligation.opens_on - timedelta(days=1), operation=operation)

    assert reason is WorkflowAbortReason.NO_PENDING_OBLIGATION
    verdict = step.precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "workflow.deadline.filing_window_open"
    assert verdict.no_recovery_outcome is None
    assert verdict.conditionality is ActionConditionality.REQUIRES_ARGUMENTS
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.modelo.export"
    bindings = {item.argument_name: item for item in verdict.argument_bindings}
    assert {name: item.value for name, item in bindings.items() if item.status is ActionArgumentStatus.RESOLVED} == {
        "modelo": "303",
        "year": obligation.period.filing_year,
        "period": obligation.period.registry_token,
    }
    assert bindings["output"].status is ActionArgumentStatus.MISSING
    assert verdict.missing_argument_names == ("output",)
    assert {item.source for item in bindings.values() if item.source is not None} == {
        ActionArgumentSource.CONDITION_EVIDENCE
    }
    (evidence,) = verdict.evidence
    assert evidence.values["opens_on"] == obligation.opens_on.isoformat()


def test_the_export_door_resolves_to_the_live_export_command(operation: PinnedAuthorityOperation) -> None:
    """The recorded action target carries the verdict's arguments to the export command."""
    obligation = _second_quarter_obligation(ObligationStatus.UPCOMING)
    _, step = _abort(obligation, today=obligation.opens_on - timedelta(days=1), operation=operation)
    assert step.precondition_verdict is not None

    resolved = resolve_recorded_precondition_action(step.precondition_verdict)

    assert resolved.action is not None
    assert resolved.action.action_id == "operator.modelo.export"
    assert resolved.action.cli_path is not None
    assert resolved.action.cli_path[-3:] == ("app", "modelo", "export")
    assert resolved.missing_argument_names == ("output",)


def test_a_closed_window_keeps_its_terminal_refusal(operation: PinnedAuthorityOperation) -> None:
    """A window that has closed offers no export door: the refusal stays terminal."""
    obligation = _second_quarter_obligation(ObligationStatus.OVERDUE)

    reason, step = _abort(obligation, today=obligation.adjusted_closes_on + timedelta(days=30), operation=operation)

    assert reason is WorkflowAbortReason.DEADLINE_PASSED
    verdict = step.precondition_verdict
    assert verdict is not None
    assert verdict.action is None
    assert verdict.argument_bindings == ()
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL
