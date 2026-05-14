"""Unit tests for the strict pydantic v2 records in
:mod:`aeat.application.workflow._models`.

Exercises :func:`aeat.application.workflow.compute_run_id` hash
stability and the validators on :class:`aeat.application.workflow.WorkflowStep`,
:class:`aeat.application.workflow.SiteHealthAlert`, and
:class:`aeat.application.workflow.WorkflowResult`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest
from pydantic import ValidationError

from ...adapters.outbound.aeat.browser._site_health import (
    _URL_ADAPTER,
    SiteHealthEvidence,
    SiteHealthState,
    SiteHealthStatus,
)
from . import (
    SiteHealthAlert,
    WorkflowAbortReason,
    WorkflowResult,
    WorkflowStage,
    WorkflowStep,
    compute_run_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


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
            summary="translation",
            details={"key": "value"},
        )
        assert step.details == {"key": "value"}

    def test_details_rejects_non_string_value(self) -> None:
        """Strict validation rejects non-string values in the details dict."""
        now = datetime(2026, 4, 12, tzinfo=UTC)
        with pytest.raises(ValidationError, match=r"valid string"):
            WorkflowStep(
                stage=WorkflowStage.LOADING_PROFILE,
                started_at=now,
                ended_at=now,
                success=True,
                summary="translation",
                details=cast(dict[str, str], {"key": 42}),
            )


class TestSiteHealthAlert:
    """Validation invariants on
    :class:`aeat.application.workflow.SiteHealthAlert`.
    """

    def _status(self) -> SiteHealthStatus:
        evidence = SiteHealthEvidence(
            url=_URL_ADAPTER.validate_python("https://sede.agenciatributaria.gob.es/"),
            http_status=503,
            html_fragment="<html>mantenimiento</html>",
            detected_markers=("mantenimiento",),
        )
        return SiteHealthStatus(
            state=SiteHealthState.MANTENIMIENTO,
            evidence=evidence,
            observed_at=datetime.now(tz=UTC),
        )

    def test_alert_composes_stage_and_status(self) -> None:
        alert = SiteHealthAlert(
            stage=WorkflowStage.BUILDING_DRAFT,
            status=self._status(),
            run_id="run-1234",
        )
        assert alert.stage is WorkflowStage.BUILDING_DRAFT
        assert alert.status.state is SiteHealthState.MANTENIMIENTO

    def test_alert_rejects_empty_run_id(self) -> None:
        with pytest.raises(ValidationError, match=r"at least 1 character"):
            SiteHealthAlert(
                stage=WorkflowStage.BUILDING_DRAFT,
                status=self._status(),
                run_id="",
            )

    def test_ended_at_must_not_precede_started_at(self) -> None:
        """A completed step must have ``ended_at >= started_at``."""
        now = datetime(2026, 4, 12, 12, 0, tzinfo=UTC)
        earlier = datetime(2026, 4, 12, 10, 0, tzinfo=UTC)
        with pytest.raises(ValidationError, match=r"precedes started_at"):
            WorkflowStep(
                stage=WorkflowStage.LOADING_PROFILE,
                started_at=now,
                ended_at=earlier,
                success=True,
                summary="translation",
            )


class TestWorkflowResultTerminal:
    """Terminal-state invariants on the result envelope."""

    def _step(self) -> WorkflowStep:
        now = datetime(2026, 4, 12, tzinfo=UTC)
        return WorkflowStep(
            stage=WorkflowStage.LOADING_PROFILE,
            started_at=now,
            ended_at=now,
            success=True,
            summary="translation",
        )

    def test_done_rejects_reason(self) -> None:
        """A DONE result must not carry an aborted_reason."""
        now = datetime(2026, 4, 12, tzinfo=UTC)
        with pytest.raises(ValidationError, match=r"DONE results must not carry an aborted_reason"):
            WorkflowResult(
                run_id="a" * 16,
                started_at=now,
                ended_at=now,
                final_stage=WorkflowStage.DONE,
                aborted_reason=WorkflowAbortReason.USER_CANCELLED,
                steps=(self._step(),),
                summary="translation",
            )

    def test_aborted_requires_reason(self) -> None:
        """An ABORTED result must carry an aborted_reason."""
        now = datetime(2026, 4, 12, tzinfo=UTC)
        with pytest.raises(ValidationError, match=r"ABORTED results must carry an aborted_reason"):
            WorkflowResult(
                run_id="a" * 16,
                started_at=now,
                ended_at=now,
                final_stage=WorkflowStage.ABORTED,
                aborted_reason=None,
                steps=(self._step(),),
                summary="translation",
            )

    def test_non_terminal_stage_rejected(self) -> None:
        """final_stage must be DONE or ABORTED."""
        now = datetime(2026, 4, 12, tzinfo=UTC)
        with pytest.raises(ValidationError, match=r"final_stage must be DONE or ABORTED"):
            WorkflowResult(
                run_id="a" * 16,
                started_at=now,
                ended_at=now,
                final_stage=WorkflowStage.BUILDING_DRAFT,
                steps=(self._step(),),
                summary="translation",
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
            submission_id=None,
            steps=(self._step(),),
            summary="translation",
        )
        blob = original.model_dump_json()
        reconstructed = WorkflowResult.model_validate_json(blob)
        assert reconstructed == original

    def test_resumed_result_records_prior_run_id(self) -> None:
        """Resume attempts carry the prior workflow-run id."""
        now = datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC)
        result = WorkflowResult(
            run_id="1" * 16,
            started_at=now,
            ended_at=now,
            final_stage=WorkflowStage.DONE,
            resumed_from="0" * 16,
            steps=(self._step(),),
            summary="resumed run",
        )
        assert result.resumed_from == "0" * 16

    def test_resumed_result_refuses_self_reference(self) -> None:
        """A workflow result cannot resume from itself."""
        now = datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC)
        with pytest.raises(ValidationError, match=r"resumed_from must reference a different workflow run"):
            WorkflowResult(
                run_id="1" * 16,
                started_at=now,
                ended_at=now,
                final_stage=WorkflowStage.DONE,
                resumed_from="1" * 16,
                steps=(self._step(),),
                summary="invalid resume link",
            )
