"""Error-boundary regression tests for :class:`ModeloWorkflowGateError`.

A workflow-gate refusal carries a :class:`WorkflowResult` describing the
aborted run. The result is a deeply nested record — ``datetime`` fields,
:class:`WorkflowStage` enums, a tuple of :class:`WorkflowStep` records.
If that live object reaches the CLI error boundary as a public exception
attribute, :func:`render_error_text` folds it into the operator-facing
context via its ``vars(error)`` merge and stringifies it to a raw Python
repr — ``datetime.datetime(...)`` constructors, ``<WorkflowStage.X>``
enum reprs, nested ``WorkflowStep(...)`` tuples — straight at a
non-technical taxpayer.

These tests pin the boundary: the error carries the engine-owned locale identity
and stable primitive machine codes only — never a raw object dump or locally
authored command guidance.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core import (
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from ....core.config import override_settings
from ....core.errors import render_error_json, render_error_text
from ...operator_actions import (
    ConditionEvidence,
    PreconditionVerdict,
)
from cadrumo.application.workflow.abort import WorkflowAbortReason
from cadrumo.application.workflow.run_models import WorkflowResult, WorkflowStage, WorkflowStep
from .. import ModeloWorkflowGateError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _aborted_result(
    *,
    summary_locale_key: str = "application.workflow.steps.deadline_missing",
    reason: WorkflowAbortReason = WorkflowAbortReason.NO_PENDING_OBLIGATION,
) -> WorkflowResult:
    """Build a realistic ABORTED workflow result with nested steps."""

    started = datetime(2026, 5, 21, 6, 49, 48, 69357, tzinfo=UTC)
    ended = datetime(2026, 5, 21, 6, 49, 48, 240000, tzinfo=UTC)
    return WorkflowResult(
        run_id="1de72c8978487300",
        started_at=started,
        ended_at=ended,
        final_stage=WorkflowStage.ABORTED,
        aborted_reason=reason,
        obligation=None,
        draft_id=None,
        submission_id=None,
        steps=(
            WorkflowStep(
                stage=WorkflowStage.LOADING_PROFILE,
                started_at=started,
                ended_at=ended,
                success=True,
                summary_locale_key="application.workflow.steps.profile_loaded",
            ),
            WorkflowStep(
                stage=WorkflowStage.COMPUTING_DEADLINES,
                started_at=started,
                ended_at=ended,
                success=False,
                summary_locale_key=summary_locale_key,
                precondition_verdict=PreconditionVerdict(
                    failed_condition_id="workflow.deadline.filing_window_open",
                    evidence=(
                        ConditionEvidence(
                            condition_id="workflow.deadline.filing_window_open",
                            evidence_id="workflow.deadline.window",
                            provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
                            values={"filing_window_open": False},
                        ),
                    ),
                    conditionality=ActionConditionality.NOT_APPLICABLE,
                    no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
                ),
            ),
        ),
        summary_locale_key=summary_locale_key,
    )


def test_gate_error_text_carries_no_raw_python_repr() -> None:
    """The operator-facing text must not leak a WorkflowResult repr.

    Reproduces persona bug B2: ``work verify`` against a profile with
    no pending obligation dumped a ``result: run_id=... started_at=
    datetime.datetime(...) ... steps=(WorkflowStep(...))`` line straight
    at the operator.
    """

    with override_settings(cadrumo_output_language="en"):
        error = ModeloWorkflowGateError(_aborted_result())
        rendered = render_error_text(error)

    assert error.translated_message == "application.workflow.steps.deadline_missing"
    assert "aeat app modelo export" not in rendered

    # No raw Python object repr of any shape reaches the operator.
    for leak in (
        "datetime.datetime(",
        "WorkflowStep(",
        "WorkflowResult(",
        "<WorkflowStage.",
        "<WorkflowAbortReason.",
        "tzinfo=",
        "result: run_id=",
    ):
        assert leak not in rendered, f"raw repr fragment leaked into operator output: {leak!r}\n{rendered}"


def test_gate_error_context_exposes_stable_primitive_machine_codes() -> None:
    """The context carries stringified machine codes, not the live object."""

    error = ModeloWorkflowGateError(_aborted_result())
    rendered = render_error_text(error)

    assert "abort_code: NO_PENDING_OBLIGATION" in rendered
    assert "stage: ABORTED" in rendered


def test_gate_error_keeps_the_persisted_summary_as_a_locale_identity() -> None:
    """Application code forwards the engine-owned locale key without rendering it."""

    error = ModeloWorkflowGateError(_aborted_result())

    assert error.translated_message == "application.workflow.steps.deadline_missing"
    assert error.context == {"abort_code": "NO_PENDING_OBLIGATION", "stage": "ABORTED"}


def test_other_gate_abort_reasons_keep_their_workflow_locale_identity() -> None:
    """The error boundary does not substitute a prose fallback for another abort."""

    error = ModeloWorkflowGateError(
        _aborted_result(
            summary_locale_key="application.workflow.steps.deadline_closed",
            reason=WorkflowAbortReason.DEADLINE_PASSED,
        )
    )
    rendered = render_error_text(error)

    assert error.translated_message == "application.workflow.steps.deadline_closed"
    assert "abort_code: DEADLINE_PASSED" in rendered
    assert "stage: ABORTED" in rendered


def test_gate_error_json_envelope_context_is_all_strings() -> None:
    """The JSON envelope context must be a flat ``str -> str`` mapping.

    A non-primitive object in ``context`` would either crash strict
    envelope validation or serialize a Python repr into the machine
    contract. Every value must be a plain string.
    """

    error = ModeloWorkflowGateError(_aborted_result())
    payload = render_error_json(error)

    assert '"abort_code":"NO_PENDING_OBLIGATION"' in payload
    assert '"stage":"ABORTED"' in payload
    assert "datetime.datetime(" not in payload
    assert "WorkflowStep(" not in payload


def test_gate_error_retains_result_for_internal_telemetry() -> None:
    """The live result stays reachable for telemetry — just not via context.

    The fix moves ``result`` from a public instance attribute to a
    property so the ``vars(error)`` context merge skips it. Internal
    callers (run persistence, telemetry) must still reach the object.
    """

    result = _aborted_result()
    error = ModeloWorkflowGateError(result)

    assert error.result is result
    assert error.result.final_stage is WorkflowStage.ABORTED
    assert error.terminal_precondition_verdict is result.steps[-1].precondition_verdict
    # ``result`` is a property, not an instance attribute, so it never
    # appears in ``vars`` — the merge surface the error boundary walks.
    assert "result" not in vars(error)
