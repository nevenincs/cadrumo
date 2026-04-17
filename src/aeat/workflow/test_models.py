"""Unit tests for :mod:`aeat.workflow._models`."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest
from pydantic import ValidationError

from . import (
    WorkflowAbortReason,
    WorkflowResult,
    WorkflowStage,
    WorkflowStep,
    compute_run_id,
)


@pytest.mark.unit
class TestWorkflowStageOrdering:
    """The ten-stage enum must stay exact and ordered."""

    def test_exact_ten_stages(self) -> None:
        """Every stage declared in the ADR is present exactly once."""
        expected = (
            "LOADING_PROFILE",
            "SYNCING_CATALOGUES",
            "COMPUTING_DEADLINES",
            "CHECKING_INBOX",
            "BUILDING_DRAFT",
            "VALIDATING_DRAFT",
            "RUNNING_PREFLIGHT",
            "DRY_RUN_SUBMIT",
            "DONE",
            "ABORTED",
        )
        assert tuple(s.value for s in WorkflowStage) == expected


@pytest.mark.unit
class TestWorkflowAbortReasons:
    """The abort reasons must match the issue spec exactly.

    ``SITE_UNAVAILABLE`` was added for #95 to carry the typed
    site-health pause-and-alert contract alongside the original nine
    reasons.
    """

    def test_exact_nine_reasons(self) -> None:
        """Every abort reason declared in the ADR is present exactly once."""
        expected = {
            "NO_PENDING_OBLIGATION",
            "INBOX_BLOCKING_REQUERIMIENTO",
            "DEADLINE_PASSED",
            "ALREADY_FILED",
            "DRAFT_HAS_ERRORS",
            "PREFLIGHT_FAILED",
            "CERT_INVALID",
            "USER_CANCELLED",
            "SITE_UNAVAILABLE",
            "UNHANDLED_EXCEPTION",
        }
        assert {r.value for r in WorkflowAbortReason} == expected


@pytest.mark.unit
class TestComputeRunId:
    """Stable hash for a workflow run."""

    def test_deterministic(self) -> None:
        """Same seed → same 16-char hex id."""
        started = datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC)
        a = compute_run_id(tax_id="X1234567L", modelo="130", period="2026Q1", started_at=started)
        b = compute_run_id(tax_id="X1234567L", modelo="130", period="2026Q1", started_at=started)
        assert a == b
        assert len(a) == 16
        assert all(c in "0123456789abcdef" for c in a)

    def test_differs_by_tax_id(self) -> None:
        """Different tax ids produce different ids."""
        started = datetime(2026, 4, 12, tzinfo=UTC)
        a = compute_run_id(tax_id="A", modelo="130", period="2026Q1", started_at=started)
        b = compute_run_id(tax_id="B", modelo="130", period="2026Q1", started_at=started)
        assert a != b


@pytest.mark.unit
class TestWorkflowStepValidation:
    """Strict pydantic validation on workflow step records."""

    def test_details_dict_str_str_accepted(self) -> None:
        """The single sanctioned ``dict[str, str]`` escape hatch works."""
        now = datetime(2026, 4, 12, tzinfo=UTC)
        step = WorkflowStep(
            stage=WorkflowStage.LOADING_PROFILE,
            started_at=now,
            ended_at=now,
            success=True,
            summary={"en": "ok"},
            details={"key": "value"},
        )
        assert step.details == {"key": "value"}

    def test_details_rejects_non_string_value(self) -> None:
        """Strict validation rejects non-string values in the details dict."""
        now = datetime(2026, 4, 12, tzinfo=UTC)
        with pytest.raises(ValidationError):
            WorkflowStep(
                stage=WorkflowStage.LOADING_PROFILE,
                started_at=now,
                ended_at=now,
                success=True,
                summary={"en": "ok"},
                details=cast(dict[str, str], {"key": 42}),
            )

    def test_ended_at_must_not_precede_started_at(self) -> None:
        """A completed step must have ``ended_at >= started_at``."""
        now = datetime(2026, 4, 12, 12, 0, tzinfo=UTC)
        earlier = datetime(2026, 4, 12, 10, 0, tzinfo=UTC)
        with pytest.raises(ValidationError):
            WorkflowStep(
                stage=WorkflowStage.LOADING_PROFILE,
                started_at=now,
                ended_at=earlier,
                success=True,
                summary={"en": "ok"},
            )


@pytest.mark.unit
class TestWorkflowResultTerminal:
    """Terminal-state invariants on the result envelope."""

    def _step(self) -> WorkflowStep:
        now = datetime(2026, 4, 12, tzinfo=UTC)
        return WorkflowStep(
            stage=WorkflowStage.LOADING_PROFILE,
            started_at=now,
            ended_at=now,
            success=True,
            summary={"en": "ok"},
        )

    def test_done_rejects_reason(self) -> None:
        """A DONE result must not carry an aborted_reason."""
        now = datetime(2026, 4, 12, tzinfo=UTC)
        with pytest.raises(ValidationError):
            WorkflowResult(
                run_id="a" * 16,
                started_at=now,
                ended_at=now,
                final_stage=WorkflowStage.DONE,
                aborted_reason=WorkflowAbortReason.USER_CANCELLED,
                steps=(self._step(),),
                summary={"en": "done"},
            )

    def test_aborted_requires_reason(self) -> None:
        """An ABORTED result must carry an aborted_reason."""
        now = datetime(2026, 4, 12, tzinfo=UTC)
        with pytest.raises(ValidationError):
            WorkflowResult(
                run_id="a" * 16,
                started_at=now,
                ended_at=now,
                final_stage=WorkflowStage.ABORTED,
                aborted_reason=None,
                steps=(self._step(),),
                summary={"en": "?"},
            )

    def test_non_terminal_stage_rejected(self) -> None:
        """final_stage must be DONE or ABORTED."""
        now = datetime(2026, 4, 12, tzinfo=UTC)
        with pytest.raises(ValidationError):
            WorkflowResult(
                run_id="a" * 16,
                started_at=now,
                ended_at=now,
                final_stage=WorkflowStage.BUILDING_DRAFT,
                steps=(self._step(),),
                summary={"en": "?"},
            )

    def test_json_round_trip(self) -> None:
        """Result records survive a full JSON round-trip."""
        now = datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC)
        original = WorkflowResult(
            run_id="0" * 16,
            started_at=now,
            ended_at=now,
            final_stage=WorkflowStage.DONE,
            aborted_reason=None,
            obligation=None,
            draft_id="draft-1",
            submission_id="sub-1",
            steps=(self._step(),),
            summary={"en": "ok"},
        )
        blob = original.model_dump_json()
        reconstructed = WorkflowResult.model_validate_json(blob)
        assert reconstructed == original
