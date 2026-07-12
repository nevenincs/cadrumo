"""Verify-purpose workflow engine coverage."""

from __future__ import annotations

from datetime import date

import pytest

from ....core.errors import BaseSeverity
from ....domain.submission import ModeloFinding
from .. import WorkflowAbortReason, WorkflowPurpose, WorkflowStage
from ._engine_support import (
    _ConcreteDeadlineEngine,
    _ConcreteDraft,
    _fixtures,
    _obligation,
    _period,
    _run_for_obligation,
    _run_for_period,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class TestVerifyPurpose:
    """``WorkflowPurpose.VERIFY`` makes the run deadline-independent."""

    def test_verify_reaches_done_without_a_pending_obligation(self) -> None:
        fx = _fixtures()
        fx.deadline_engine.obligation = None

        file_result = _run_for_obligation(fx, purpose=WorkflowPurpose.FILE)
        assert file_result.aborted_reason is WorkflowAbortReason.NO_PENDING_OBLIGATION

        verify_result = _run_for_obligation(fx, purpose=WorkflowPurpose.VERIFY)
        assert verify_result.final_stage is WorkflowStage.DONE
        assert verify_result.aborted_reason is None

    def test_verify_reaches_done_for_a_closed_filing_window(self) -> None:
        fx = _fixtures()
        past = _obligation(period=_period(2025, "4T"), closes_on=date(2026, 1, 20))
        fx.deadline_engine = _ConcreteDeadlineEngine(obligation=past, profile=fx.profile)
        fx.draft = _ConcreteDraft(period=past.period, profile_tax_id=fx.profile.tax_id)
        fx.draft_builder.draft = fx.draft

        file_result = _run_for_period(
            fx.engine(),
            fx.profile,
            past.modelo,
            past.period,
            today=fx.today,
            purpose=WorkflowPurpose.FILE,
        )
        assert file_result.aborted_reason is not WorkflowAbortReason.DEADLINE_PASSED

        verify_result = _run_for_period(
            fx.engine(),
            fx.profile,
            past.modelo,
            past.period,
            today=fx.today,
            purpose=WorkflowPurpose.VERIFY,
        )
        assert verify_result.final_stage is WorkflowStage.DONE
        assert verify_result.aborted_reason is None

    def test_verify_records_deadline_stage_as_informational(self) -> None:
        fx = _fixtures()
        fx.deadline_engine.obligation = None

        result = _run_for_obligation(fx, purpose=WorkflowPurpose.VERIFY)
        deadline_step = next(s for s in result.steps if s.stage is WorkflowStage.COMPUTING_DEADLINES)
        assert deadline_step.success is True
        assert deadline_step.details is not None
        assert deadline_step.details["deadline_role"] == "informational"
        assert deadline_step.details["filing_window"] == "absent"

    def test_verify_skips_the_preflight_deadline_window_gate(self) -> None:
        fx = _fixtures()

        _run_for_obligation(fx, purpose=WorkflowPurpose.VERIFY)
        assert fx.submission_engine.skip_deadline_window_calls == [True]

        fresh = _fixtures()
        _run_for_obligation(fresh, purpose=WorkflowPurpose.FILE)
        assert fresh.submission_engine.skip_deadline_window_calls == [True]

    def test_verify_still_refuses_an_unsound_draft(self) -> None:
        fx = _fixtures()
        fx.deadline_engine.obligation = None
        fx.draft = _ConcreteDraft(
            profile_tax_id=fx.profile.tax_id,
            findings=(ModeloFinding(severity=BaseSeverity.ERROR, message="translation"),),
        )
        fx.draft_builder.draft = fx.draft

        result = _run_for_obligation(fx, purpose=WorkflowPurpose.VERIFY)
        assert result.aborted_reason is WorkflowAbortReason.DRAFT_HAS_ERRORS
