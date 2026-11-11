"""Strict round-trip coverage for the application workflow step envelope."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ..run_models import (
    WorkflowAuthCheckDetails,
    WorkflowDiagnosticSkipReason,
    WorkflowStage,
    WorkflowStep,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_WORKFLOW_STEP_STARTED_AT = datetime(2026, 5, 28, 10, 5, 0, tzinfo=UTC)


def test_workflow_step_details_typed_envelope_roundtrip() -> None:
    """``WorkflowStep.details`` preserves the concrete closed-union detail type.

    A skipped auth-provider check carries typed facts rather than a free-form
    mapping, and the canonical preflight summary key remains valid across the
    JSON boundary.
    """

    original = WorkflowStep(
        stage=WorkflowStage.RUNNING_PREFLIGHT,
        started_at=_WORKFLOW_STEP_STARTED_AT,
        ended_at=_WORKFLOW_STEP_STARTED_AT + timedelta(seconds=2),
        success=True,
        summary_locale_key="application.workflow.steps.preflight_completed",
        details=WorkflowAuthCheckDetails(
            kind="auth_check",
            provider_check_skipped=True,
            skip_reason=WorkflowDiagnosticSkipReason.NOT_WIRED,
        ),
    )

    assert isinstance(original.details, WorkflowAuthCheckDetails)
    assert original.details.kind == "auth_check"
    assert original.details.provider_check_skipped is True
    assert original.details.skip_reason is WorkflowDiagnosticSkipReason.NOT_WIRED

    roundtripped = WorkflowStep.model_validate_json(original.model_dump_json())
    assert isinstance(roundtripped.details, WorkflowAuthCheckDetails)
    assert roundtripped == original
    assert roundtripped.details.kind == "auth_check"
    assert roundtripped.details.provider_check_skipped is True
    assert roundtripped.details.skip_reason is WorkflowDiagnosticSkipReason.NOT_WIRED
