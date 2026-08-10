"""Real contract tests for verification finding precondition projections."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....domain.modelos import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    derive_verification_report_id,
)
from ...operator_actions import (
    ActionConditionality,
    NoRecoveryOutcome,
    lookup_action,
)
from .._verification_preconditions import (
    ModeloVerificationResult,
    VerificationFindingPreconditionProjection,
    project_registry_snapshot_unresolved_finding,
    project_verification_finding_no_recovery,
    project_verification_findings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CALCULATION_REVISION_ID = "a" * 64
_LEGAL_REFS = ("ley-58-2003:art-119",)


def _finding(*, severity: ModeloVerificationFindingSeverity) -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=(
            ModeloVerificationFindingKind.BLOCKING_RULE
            if severity is ModeloVerificationFindingSeverity.BLOCKING
            else ModeloVerificationFindingKind.ADVISORY
        ),
        severity=severity,
        message="verification evidence is incomplete",
        legal_refs=_LEGAL_REFS,
    )


def _blocked_report(findings: tuple[ModeloVerificationFinding, ...]) -> VerificationReport:
    return VerificationReport(
        verification_report_id=derive_verification_report_id(
            calculation_revision_id=_CALCULATION_REVISION_ID,
            completeness_status=VerificationCompletenessStatus.BLOCKED,
            findings=findings,
            verified_by="operator",
        ),
        calculation_revision_id=_CALCULATION_REVISION_ID,
        completeness_status=VerificationCompletenessStatus.BLOCKED,
        findings=findings,
        run_at=datetime(2026, 8, 10, 12, tzinfo=UTC),
        verified_by="operator",
        granted_verificado_completo=False,
    )


def test_warning_finding_has_no_recovery_slot() -> None:
    projection = project_verification_finding_no_recovery(
        _finding(severity=ModeloVerificationFindingSeverity.WARNING),
        calculation_revision_id=_CALCULATION_REVISION_ID,
    )

    assert projection.precondition_verdict is None


def test_blocking_finding_projects_an_explicit_operator_decision_outcome() -> None:
    projection = project_verification_finding_no_recovery(
        _finding(severity=ModeloVerificationFindingSeverity.BLOCKING),
        calculation_revision_id=_CALCULATION_REVISION_ID,
    )

    verdict = projection.precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "modelo.verification.blocking_rule"
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.evidence[0].values == {
        "calculation_revision_id": _CALCULATION_REVISION_ID,
        "finding_kind": "blocking_rule",
        "is_blocking": True,
    }


def test_registry_snapshot_projection_selects_the_registered_zero_argument_action() -> None:
    projection = project_registry_snapshot_unresolved_finding(
        _finding(severity=ModeloVerificationFindingSeverity.BLOCKING),
        calculation_revision_id=_CALCULATION_REVISION_ID,
    )

    verdict = projection.precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "modelo.verification.registry_snapshot.available"
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.registry.verify"
    assert verdict.conditionality is ActionConditionality.IMMEDIATE
    assert verdict.argument_bindings == ()
    assert lookup_action(verdict.action.action_id).target_command_key == "registry.verify"


def test_warning_cannot_be_given_a_blocking_precondition_verdict() -> None:
    blocking_projection = project_verification_finding_no_recovery(
        _finding(severity=ModeloVerificationFindingSeverity.BLOCKING),
        calculation_revision_id=_CALCULATION_REVISION_ID,
    )
    assert blocking_projection.precondition_verdict is not None

    with pytest.raises(ValidationError, match="only blocking verification findings"):
        VerificationFindingPreconditionProjection(
            finding=_finding(severity=ModeloVerificationFindingSeverity.WARNING),
            precondition_verdict=blocking_projection.precondition_verdict,
        )


def test_application_verification_result_pairs_the_exact_registry_branch_with_its_verdict() -> None:
    registry_snapshot_finding = _finding(severity=ModeloVerificationFindingSeverity.BLOCKING)
    warning_finding = _finding(severity=ModeloVerificationFindingSeverity.WARNING)
    report = _blocked_report((registry_snapshot_finding, warning_finding))

    result = ModeloVerificationResult(
        report=report,
        finding_preconditions=project_verification_findings(
            (registry_snapshot_finding, warning_finding),
            calculation_revision_id=_CALCULATION_REVISION_ID,
            registry_snapshot_finding_ids=frozenset({id(registry_snapshot_finding)}),
        ),
    )

    registry_verdict = result.finding_preconditions[0].precondition_verdict
    assert registry_verdict is not None
    assert registry_verdict.action is not None
    assert registry_verdict.action.action_id == "operator.registry.verify"
    assert result.finding_preconditions[1].precondition_verdict is None
