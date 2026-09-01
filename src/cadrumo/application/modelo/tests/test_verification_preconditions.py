"""Real contract tests for modelo verification precondition projections."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    derive_verification_report_id,
)
from ..verification_preconditions import (
    ModeloVerificationResult,
    VerificationFindingPreconditionProjection,
    build_verification_precondition_failure,
    project_verification_findings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CALCULATION_REVISION_ID = "a" * 64
_WORK_UNIT_ID = "b" * 64
_LEGAL_REFS = ("ley-58-2003:art-119",)


def _finding(*, severity: ModeloVerificationFindingSeverity) -> ModeloVerificationFinding:
    return ModeloVerificationFinding(
        kind=(
            ModeloVerificationFindingKind.BLOCKING_RULE
            if severity is ModeloVerificationFindingSeverity.BLOCKING
            else ModeloVerificationFindingKind.ADVISORY
        ),
        severity=severity,
        message_locale_key="application.modelo.findings.test_evidence",
        message_facts={},
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


def test_registry_snapshot_failure_is_exactly_linked_to_the_canonical_action() -> None:
    finding = _finding(severity=ModeloVerificationFindingSeverity.BLOCKING)
    failure = build_verification_precondition_failure(
        calculation_revision_id=_CALCULATION_REVISION_ID,
        work_unit_id=_WORK_UNIT_ID,
        condition_id="modelo.work.verify.registry_snapshot.available",
        scenario_id="modelo.work.verify.registry_snapshot.unavailable",
        evidence_id="modelo.work.verify.registry_snapshot",
        evidence_values={"modelo": "303", "year": 2026, "period": "1T"},
        provenance=ActionEvidenceProvenance.REGISTRY_RECORD,
        action_id="operator.registry.verify",
    )

    (projection,) = project_verification_findings(
        (finding,),
        failures_by_finding_id={id(finding): failure},
    )

    assert projection.precondition_failure is failure
    assert failure.identity == (
        "modelo.work.verify",
        "modelo.work.verify.registry_snapshot.available",
        "modelo.work.verify.registry_snapshot.unavailable",
    )
    assert failure.verdict.action is not None
    assert failure.verdict.action.action_id == "operator.registry.verify"
    assert failure.verdict.argument_bindings == ()
    assert failure.verdict.conditionality is ActionConditionality.IMMEDIATE


def test_operator_decision_failure_preserves_branch_identity_and_typed_facts() -> None:
    failure = build_verification_precondition_failure(
        calculation_revision_id=_CALCULATION_REVISION_ID,
        work_unit_id=_WORK_UNIT_ID,
        condition_id="modelo.work.verify.registry_predicate.satisfied",
        scenario_id="modelo.work.verify.registry_predicate.failed",
        evidence_id="modelo.work.verify.registry_predicate",
        evidence_values={"predicate_id": "m303-base-cuota-consistent"},
        provenance=ActionEvidenceProvenance.REGISTRY_RECORD,
    )

    assert failure.verdict.action is None
    assert failure.verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert failure.verdict.evidence[0].values["predicate_id"] == "m303-base-cuota-consistent"
    assert "message" not in failure.model_dump(mode="json")


def test_warning_cannot_receive_a_failed_precondition() -> None:
    blocking = _finding(severity=ModeloVerificationFindingSeverity.BLOCKING)
    warning = _finding(severity=ModeloVerificationFindingSeverity.WARNING)
    failure = build_verification_precondition_failure(
        calculation_revision_id=_CALCULATION_REVISION_ID,
        work_unit_id=_WORK_UNIT_ID,
        condition_id="modelo.work.verify.ledger_snapshot.current",
        scenario_id="modelo.work.verify.ledger_snapshot.drift_detected",
        evidence_id="modelo.work.verify.ledger_snapshot",
        evidence_values={"snapshot_anchored": False},
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
    )

    assert VerificationFindingPreconditionProjection(finding=blocking, precondition_failure=failure)
    with pytest.raises(ValidationError, match="blocking verification findings"):
        VerificationFindingPreconditionProjection(finding=blocking)
    with pytest.raises(ValidationError, match="warning verification findings"):
        VerificationFindingPreconditionProjection(finding=warning, precondition_failure=failure)


def test_application_result_requires_exact_ordered_finding_projection() -> None:
    blocking = _finding(severity=ModeloVerificationFindingSeverity.BLOCKING)
    warning = _finding(severity=ModeloVerificationFindingSeverity.WARNING)
    failure = build_verification_precondition_failure(
        calculation_revision_id=_CALCULATION_REVISION_ID,
        work_unit_id=_WORK_UNIT_ID,
        condition_id="modelo.work.verify.oss_evidence.present",
        scenario_id="modelo.work.verify.oss_evidence.missing",
        evidence_id="modelo.work.verify.oss_evidence",
        evidence_values={"source_ref_count": 0},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
    )
    projections = project_verification_findings(
        (blocking, warning),
        failures_by_finding_id={id(blocking): failure},
    )

    result = ModeloVerificationResult(
        report=_blocked_report((blocking, warning)),
        finding_preconditions=projections,
    )
    assert result.finding_preconditions[0].precondition_failure is failure
    assert result.finding_preconditions[1].precondition_failure is None

    with pytest.raises(ValidationError, match="in order"):
        ModeloVerificationResult(
            report=_blocked_report((blocking, warning)),
            finding_preconditions=tuple(reversed(projections)),
        )
