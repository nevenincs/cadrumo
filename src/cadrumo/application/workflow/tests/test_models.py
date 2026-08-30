"""Unit tests for the strict pydantic v2 records in
:mod:`cadrumo.application.workflow.run_models`.

Exercises :func:`cadrumo.application.workflow.compute_run_id` hash
stability and the validators on :class:`cadrumo.application.workflow.WorkflowStep`,
:class:`cadrumo.application.workflow.SiteHealthAlert`, and
:class:`cadrumo.application.workflow.WorkflowResult`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast

import pytest
from pydantic import ValidationError

from ....adapters.outbound.aeat.browser import (
    SiteHealthEvidence,
    SiteHealthStatus,
)
from ....adapters.outbound.aeat.browser._site_health import parse_site_health_url
from ....core import (
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    Modelo,
    NoRecoveryOutcome,
)
from ....core.period import Period
from ....core.errors.hierarchy import SiteHealthState
from ....domain.deadlines.models import ModeloDeadline, ObligationStatus, RecargoBand, Recovery
from ....tests.aeat_literal_fixtures import aeat_url
from ...operator_actions import (
    ActionArgumentBinding,
    ActionReference,
    ConditionEvidence,
    PreconditionVerdict,
)
from ..abort import WorkflowAbortReason
from ..engine_helpers import DeadlineRole
from ..run_models import (
    SiteHealthAlert,
    WorkflowDeadlineContextDetails,
    WorkflowObligationFacts,
    WorkflowResult,
    WorkflowSiteHealthFacts,
    WorkflowStage,
    WorkflowStep,
    WorkflowValidationFailedDetails,
    compute_run_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RUN_STARTED_AT = datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC)
_SITE_HEALTH_OBSERVED_AT = datetime(2026, 4, 12, 10, 0, 0, tzinfo=UTC)


def _period(year: int = 2026, code: str = "1T") -> Period:
    return Period.from_year_and_code(year, code)


class TestComputeRunId:
    """Stable hash for a workflow run."""

    def test_deterministic(self) -> None:
        """Same seed → same 16-char hex id."""
        started = datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC)
        a = compute_run_id(tax_id="X1234567L", modelo="130", period=_period(), started_at=started)
        b = compute_run_id(tax_id="X1234567L", modelo="130", period=_period(), started_at=started)
        assert a == b
        assert a == "71f95b6c466e52b7"
        assert len(a) == 16
        assert all(c in "0123456789abcdef" for c in a)

    def test_differs_by_tax_id(self) -> None:
        """Different tax ids produce different ids."""
        started = datetime(2026, 4, 12, 9, 0, 0, tzinfo=UTC)
        a = compute_run_id(tax_id="A", modelo="130", period=_period(), started_at=started)
        b = compute_run_id(tax_id="B", modelo="130", period=_period(), started_at=started)
        assert a != b

    def test_rejects_combined_string_period(self) -> None:
        """A combined token must not enter the workflow run-id contract."""
        combined_period = cast(Any, "2026Q1")
        with pytest.raises(TypeError, match=r"cadrumo\.core\.Period"):
            compute_run_id(
                tax_id="X1234567L",
                modelo="130",
                period=combined_period,
                started_at=_RUN_STARTED_AT,
            )


class TestWorkflowStepValidation:
    """Strict pydantic validation on workflow step records."""

    def test_deadline_details_are_one_closed_context_shape(self) -> None:
        now = datetime(2026, 4, 12, tzinfo=UTC)
        step = WorkflowStep(
            stage=WorkflowStage.COMPUTING_DEADLINES,
            started_at=now,
            ended_at=now,
            success=True,
            summary_locale_key="application.workflow.steps.deadline_open",
            details=WorkflowDeadlineContextDetails(
                kind="deadline_context",
                modelo=Modelo.M303,
                period=_period(),
                opens_on=datetime(2026, 4, 1, tzinfo=UTC).date(),
                closes_on=datetime(2026, 4, 20, tzinfo=UTC).date(),
            ),
        )
        assert isinstance(step.details, WorkflowDeadlineContextDetails)
        assert step.details.modelo is Modelo.M303
        assert step.details.period == _period()
        assert step.details.kind == "deadline_context"

    @pytest.mark.parametrize("legacy_key", ("next_action", "error_message", "provider_operator_impact", "key"))
    def test_details_reject_legacy_prose_and_arbitrary_fields(self, legacy_key: str) -> None:
        now = datetime(2026, 4, 12, tzinfo=UTC)
        with pytest.raises(ValidationError, match=legacy_key):
            WorkflowStep.model_validate(
                {
                    "stage": WorkflowStage.LOADING_PROFILE,
                    "started_at": now,
                    "ended_at": now,
                    "success": True,
                    "summary_locale_key": "application.workflow.steps.profile_loaded",
                    "details": {
                        "kind": "workflow_failure",
                        "error_code": "workflow.failure.unhandled",
                        legacy_key: "Run: aeat app modelo work.calculate",
                    },
                },
            )

    def test_deadline_details_reject_a_role_without_a_window(self) -> None:
        now = datetime(2026, 4, 12, tzinfo=UTC)
        with pytest.raises(ValidationError, match="deadline_role and filing_window"):
            WorkflowStep.model_validate(
                {
                    "stage": WorkflowStage.COMPUTING_DEADLINES,
                    "started_at": now,
                    "ended_at": now,
                    "success": True,
                    "summary_locale_key": "application.workflow.steps.deadline_open",
                    "details": {
                        "kind": "deadline_context",
                        "modelo": Modelo.M303,
                        "period": _period(),
                        "deadline_role": DeadlineRole.BINDING,
                    },
                },
            )

    def test_summary_requires_an_abstract_locale_key(self) -> None:
        now = datetime(2026, 4, 12, tzinfo=UTC)
        with pytest.raises(ValidationError, match="stable dotted locale key"):
            WorkflowStep(
                stage=WorkflowStage.LOADING_PROFILE,
                started_at=now,
                ended_at=now,
                success=True,
                summary_locale_key="Profile loaded successfully",
            )

    def test_summary_rejects_an_unemitted_dotted_locale_key(self) -> None:
        """Only engine-produced identities may enter persisted workflow records."""
        now = datetime(2026, 4, 12, tzinfo=UTC)
        with pytest.raises(ValidationError, match="closed workflow producer keys"):
            WorkflowStep(
                stage=WorkflowStage.COMPUTING_DEADLINES,
                started_at=now,
                ended_at=now,
                success=True,
                summary_locale_key="application.workflow.steps.deadline_checked",
            )

    def test_actionable_precondition_verdict_round_trips_without_command_prose(self) -> None:
        now = datetime(2026, 4, 12, tzinfo=UTC)
        verdict = PreconditionVerdict(
            failed_condition_id="workflow.draft.ready",
            evidence=(
                ConditionEvidence(
                    condition_id="workflow.draft.ready",
                    evidence_id="workflow.draft.status",
                    provenance=ActionEvidenceProvenance.PERSISTED_STATE,
                    values={"draft_id": "draft-303", "draft_status": "BORRADOR"},
                ),
            ),
            action=ActionReference(action_id="operator.modelo.verification_report.list"),
            argument_bindings=(
                ActionArgumentBinding(
                    argument_name="calculation_revision_id",
                    status=ActionArgumentStatus.MISSING,
                ),
            ),
            missing_argument_names=("calculation_revision_id",),
            conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
        )
        step = WorkflowStep(
            stage=WorkflowStage.BUILDING_DRAFT,
            started_at=now,
            ended_at=now,
            success=False,
            summary_locale_key="application.workflow.steps.draft_not_ready",
            details=WorkflowValidationFailedDetails(
                kind="validation_failed",
                error_count=1,
            ),
            precondition_verdict=verdict,
        )

        reconstructed = WorkflowStep.model_validate_json(step.model_dump_json())

        assert reconstructed == step
        assert reconstructed.precondition_verdict == verdict

    @pytest.mark.parametrize(
        ("evidence_key", "evidence_value"),
        (
            ("state_code", "Draft input is not ready"),
            ("failure_reason", "runtime_error"),
            ("failure_exception", "runtime_error"),
            ("failure_code", "RuntimeError:boom"),
        ),
    )
    def test_precondition_evidence_rejects_rendered_or_exception_prose(
        self,
        evidence_key: str,
        evidence_value: str,
    ) -> None:
        now = datetime(2026, 4, 12, tzinfo=UTC)
        verdict = PreconditionVerdict(
            failed_condition_id="workflow.draft.ready",
            evidence=(
                ConditionEvidence(
                    condition_id="workflow.draft.ready",
                    evidence_id="workflow.draft.failure",
                    provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                    values={evidence_key: evidence_value},
                ),
            ),
            conditionality=ActionConditionality.NOT_APPLICABLE,
            no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
        )
        with pytest.raises(ValidationError, match="cannot persist rendered or exception prose"):
            WorkflowStep(
                stage=WorkflowStage.BUILDING_DRAFT,
                started_at=now,
                ended_at=now,
                success=False,
                summary_locale_key="application.workflow.steps.draft_not_ready",
                precondition_verdict=verdict,
            )

    def test_refusal_details_require_the_typed_precondition_verdict(self) -> None:
        now = datetime(2026, 4, 12, tzinfo=UTC)
        with pytest.raises(ValidationError, match="require a typed precondition verdict"):
            WorkflowStep(
                stage=WorkflowStage.VALIDATING_DRAFT,
                started_at=now,
                ended_at=now,
                success=False,
                summary_locale_key="application.workflow.steps.validation_failed",
                details=WorkflowValidationFailedDetails(
                    kind="validation_failed",
                    error_count=1,
                ),
            )

    def test_no_recovery_verdict_round_trips_as_a_closed_outcome(self) -> None:
        now = datetime(2026, 4, 12, tzinfo=UTC)
        verdict = PreconditionVerdict(
            failed_condition_id="workflow.submission.safe",
            evidence=(
                ConditionEvidence(
                    condition_id="workflow.submission.safe",
                    evidence_id="workflow.submission.safety_state",
                    provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                    values={"safe": False},
                ),
            ),
            conditionality=ActionConditionality.NOT_APPLICABLE,
            no_recovery_outcome=NoRecoveryOutcome.SAFETY,
        )
        step = WorkflowStep(
            stage=WorkflowStage.RUNNING_PREFLIGHT,
            started_at=now,
            ended_at=now,
            success=False,
            summary_locale_key="application.workflow.steps.preflight_failed",
            precondition_verdict=verdict,
        )

        assert WorkflowStep.model_validate_json(step.model_dump_json()) == step


class TestSiteHealthAlert:
    """Validation invariants on
    :class:`cadrumo.application.workflow.SiteHealthAlert`.
    """

    def _status(self) -> SiteHealthStatus:
        evidence = SiteHealthEvidence(
            url=parse_site_health_url(aeat_url("sede", "/")),
            http_status=503,
            html_fragment="<html>servicio temporalmente no disponible</html>",
            detected_markers=("servicio temporalmente no disponible",),
        )
        return SiteHealthStatus(
            state=SiteHealthState.MANTENIMIENTO,
            evidence=evidence,
            observed_at=_SITE_HEALTH_OBSERVED_AT,
        )

    def test_alert_composes_stage_and_status(self) -> None:
        status = self._status()
        alert = SiteHealthAlert(
            stage=WorkflowStage.BUILDING_DRAFT,
            status=WorkflowSiteHealthFacts.from_status(status),
            run_id="run-1234",
        )
        assert alert.stage is WorkflowStage.BUILDING_DRAFT
        assert alert.status.state is SiteHealthState.MANTENIMIENTO
        assert alert.status.alert_code == "workflow.site.mantenimiento"
        assert alert.status.http_status == 503
        assert alert.status.detected_marker_count == 1
        persisted = alert.model_dump_json()
        assert status.evidence.html_fragment not in persisted
        assert str(status.evidence.url) not in persisted
        assert status.evidence.detected_markers[0] not in persisted

    def test_workflow_projection_rejects_adapter_evidence_shape(self) -> None:
        """Raw adapter evidence cannot cross the strict workflow boundary."""
        with pytest.raises(ValidationError):
            WorkflowSiteHealthFacts.model_validate(self._status().model_dump())

    def test_alert_rejects_empty_run_id(self) -> None:
        with pytest.raises(ValidationError, match=r"at least 1 character"):
            SiteHealthAlert(
                stage=WorkflowStage.BUILDING_DRAFT,
                status=WorkflowSiteHealthFacts.from_status(self._status()),
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
                summary_locale_key="application.workflow.steps.profile_loaded",
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
            summary_locale_key="application.workflow.steps.profile_loaded",
        )

    @pytest.mark.parametrize(
        ("overrides", "match"),
        (
            (
                {
                    "final_stage": WorkflowStage.DONE,
                    "aborted_reason": WorkflowAbortReason.USER_CANCELLED,
                },
                r"DONE results must not carry an aborted_reason",
            ),
            (
                {
                    "final_stage": WorkflowStage.ABORTED,
                    "aborted_reason": None,
                },
                r"ABORTED results must carry an aborted_reason",
            ),
            (
                {
                    "final_stage": WorkflowStage.BUILDING_DRAFT,
                },
                r"final_stage must be DONE or ABORTED",
            ),
        ),
    )
    def test_terminal_result_rejects_invalid_combinations(self, overrides: dict[str, Any], match: str) -> None:
        """Terminal workflow results reject impossible stage/reason combinations."""
        now = datetime(2026, 4, 12, tzinfo=UTC)
        values: dict[str, Any] = {
            "run_id": "a" * 16,
            "started_at": now,
            "ended_at": now,
            "final_stage": WorkflowStage.DONE,
            "aborted_reason": None,
            "steps": (self._step(),),
            "summary_locale_key": "application.workflow.results.completed",
        }
        values.update(overrides)

        with pytest.raises(ValidationError, match=match):
            WorkflowResult(**values)

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
            summary_locale_key="application.workflow.results.completed",
        )
        blob = original.model_dump_json()
        reconstructed = WorkflowResult.model_validate_json(blob)
        assert reconstructed == original


def test_workflow_obligation_projection_excludes_source_language_and_raw_recovery_command() -> None:
    """The real domain deadline projects to stable persisted facts only."""
    deadline = ModeloDeadline(
        modelo=Modelo.M303,
        period=_period(2025),
        opens_on=date(2025, 4, 1),
        closes_on=date(2025, 4, 20),
        payment_cutoff_on=date(2025, 4, 15),
        status=ObligationStatus.OVERDUE,
        applies_because="Régimen general de IVA.",
        boe_references=("orden-hfp-105-2017:art-1",),
        recovery=Recovery(
            still_filable=True,
            recargo_band=RecargoBand(
                id="completed_months_2",
                min_completed_months=2,
                max_completed_months=2,
                surcharge_pct=Decimal("3.00"),
                interest_applies=False,
                legal_ref="ley-58-2003:art-27.2",
            ),
        ),
    )

    projected = WorkflowObligationFacts.from_deadline(deadline)
    payload = projected.model_dump(mode="json")

    assert projected.modelo is Modelo.M303
    assert projected.period == _period(2025)
    assert projected.recovery is not None
    assert projected.recovery.still_filable is True
    assert projected.recovery.recargo_band_id == "completed_months_2"
    assert projected.recovery.min_completed_months == 2
    assert projected.recovery.max_completed_months == 2
    assert projected.recovery.surcharge_pct == Decimal("3.00")
    assert projected.recovery.interest_applies is False
    assert projected.recovery.legal_ref == "ley-58-2003:art-27.2"
    assert "applies_because" not in payload
    assert isinstance(payload["recovery"], dict)
    assert "Régimen general de IVA." not in projected.model_dump_json()
