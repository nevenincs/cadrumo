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

These tests pin the boundary: the rendered text must carry the clean
refusal summary, the next-step hint, and stable primitive machine codes
only — never a raw object dump.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core.errors import render_error_json, render_error_text
from ...workflow import (
    WorkflowAbortReason,
    WorkflowResult,
    WorkflowStage,
    WorkflowStep,
)
from .._actions import ModeloWorkflowGateError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _aborted_result(*, summary: str = "No pending filing obligation for this profile") -> WorkflowResult:
    """Build a realistic ABORTED workflow result with nested steps."""

    started = datetime(2026, 5, 21, 6, 49, 48, 69357, tzinfo=UTC)
    ended = datetime(2026, 5, 21, 6, 49, 48, 240000, tzinfo=UTC)
    return WorkflowResult(
        run_id="1de72c8978487300",
        started_at=started,
        ended_at=ended,
        final_stage=WorkflowStage.ABORTED,
        aborted_reason=WorkflowAbortReason.NO_PENDING_OBLIGATION,
        obligation=None,
        draft_id=None,
        submission_id=None,
        steps=(
            WorkflowStep(
                stage=WorkflowStage.LOADING_PROFILE,
                started_at=started,
                ended_at=ended,
                success=True,
                summary="Loaded profile tax_id=00000000T",
            ),
            WorkflowStep(
                stage=WorkflowStage.COMPUTING_DEADLINES,
                started_at=started,
                ended_at=ended,
                success=True,
                summary="No pending filing obligation for this profile",
            ),
        ),
        summary=summary,
    )


def test_gate_error_text_carries_no_raw_python_repr() -> None:
    """The operator-facing text must not leak a WorkflowResult repr.

    Reproduces persona bug B2: ``work verify`` against a profile with
    no pending obligation dumped a ``result: run_id=... started_at=
    datetime.datetime(...) ... steps=(WorkflowStep(...))`` line straight
    at the operator.
    """

    error = ModeloWorkflowGateError(_aborted_result())
    rendered = render_error_text(error)

    # The clean operator refusal and next-step hint survive. For a
    # NO_PENDING_OBLIGATION abort the next-step hint signposts the local
    # finish line — the real verb `aeat app modelo export` (a sibling of `work`,
    # NOT a `work` subcommand) rather than the generic `work list` — so a
    # newcomer who cannot file a verified-complete revision is told how to
    # finish locally instead of dead-ending on a non-existent command.
    assert "Refused. No pending filing obligation for this profile" in rendered
    assert "aeat app modelo export" in rendered
    assert "aeat app modelo work export" not in rendered

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
    # ``result`` is a property, not an instance attribute, so it never
    # appears in ``vars`` — the merge surface the error boundary walks.
    assert "result" not in vars(error)
