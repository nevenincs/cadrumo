"""Typed recovery outcomes for blocking verification findings.

The persisted :class:`~cadrumo.domain.modelos.ModeloVerificationFinding` is an
audit fact.  This module derives the application-owned precondition record
that a later transport can resolve against the live operator action catalogue;
it deliberately never writes command prose back into the domain report.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, model_validator

from ...core import STRICT_FROZEN_CONFIG
from ...domain.modelos import (
    ModeloVerificationFinding,
    ModeloVerificationFindingSeverity,
    VerificationReport,
)
from ..operator_actions import (
    ActionConditionality,
    ActionReference,
    ConditionEvidence,
    ConditionEvidenceProvenance,
    NoRecoveryOutcome,
    PreconditionVerdict,
)


class VerificationFindingPreconditionProjection(BaseModel):
    """One application projection of a persisted verification finding.

    Warnings remain report-visible facts but are not failed preconditions, so
    they cannot acquire a recovery slot.  A blocking finding must instead
    carry one strict verdict with either an action reference or an explicit
    no-recovery outcome.
    """

    model_config = STRICT_FROZEN_CONFIG

    finding: ModeloVerificationFinding
    precondition_verdict: PreconditionVerdict | None = None

    @model_validator(mode="after")
    def _require_a_verdict_only_for_blocking_findings(self) -> VerificationFindingPreconditionProjection:
        """Keep report severity and application recovery semantics aligned."""
        is_blocking = self.finding.severity is ModeloVerificationFindingSeverity.BLOCKING
        if is_blocking != (self.precondition_verdict is not None):
            raise ValueError("only blocking verification findings require a precondition verdict")
        return self


class ModeloVerificationResult(BaseModel):
    """Application verification output with domain facts and recovery verdicts.

    The report remains the sole persisted audit artifact.  This transient
    application result pairs each report finding with the verdict the CLI can
    resolve, so a transport never has to derive an action from finding prose.
    """

    model_config = STRICT_FROZEN_CONFIG

    report: VerificationReport
    finding_preconditions: tuple[VerificationFindingPreconditionProjection, ...]

    @model_validator(mode="after")
    def _require_exact_report_finding_projection(self) -> ModeloVerificationResult:
        """Require one ordered projection for every report finding."""
        if tuple(projection.finding for projection in self.finding_preconditions) != self.report.findings:
            raise ValueError("verification preconditions must project the report findings in order")
        return self


def project_verification_finding_no_recovery(
    finding: ModeloVerificationFinding,
    *,
    calculation_revision_id: str,
    outcome: NoRecoveryOutcome = NoRecoveryOutcome.OPERATOR_DECISION,
) -> VerificationFindingPreconditionProjection:
    """Project a finding whose remedy requires an operator decision.

    Multiple materially different remedies (for example correcting a ledger
    row *or* reclassifying it) must not be collapsed into a counterfeit
    command.  The explicit closed outcome preserves that fact without
    presenting a non-executable recovery action.
    """
    return _project_finding(
        finding,
        calculation_revision_id=calculation_revision_id,
        condition_id=f"modelo.verification.{finding.kind.value}",
        evidence_id="modelo.verification.finding",
        no_recovery_outcome=outcome,
    )


def project_registry_snapshot_unresolved_finding(
    finding: ModeloVerificationFinding,
    *,
    calculation_revision_id: str,
) -> VerificationFindingPreconditionProjection:
    """Project the one verified registry-snapshot failure to ``registry verify``.

    Registry validation is the single honest zero-argument recovery for this
    application-owned availability condition.  Callers use this narrow entry
    point only for the snapshot-resolution branch, never by inferring it from
    arbitrary finding prose or a shared finding kind.
    """
    return _project_finding(
        finding,
        calculation_revision_id=calculation_revision_id,
        condition_id="modelo.verification.registry_snapshot.available",
        evidence_id="modelo.verification.registry_snapshot",
        action_id="operator.registry.verify",
    )


def project_verification_findings(
    findings: Iterable[ModeloVerificationFinding],
    *,
    calculation_revision_id: str,
    registry_snapshot_finding_ids: frozenset[int] = frozenset(),
) -> tuple[VerificationFindingPreconditionProjection, ...]:
    """Project one in-flight verification finding sequence without prose inference.

    The verifier marks the exact object constructed by its registry-snapshot
    failure branch.  Every other blocking fact has no invented recovery;
    warnings receive no verdict.  An unmatched marker is a programming error,
    rather than permission to fall back to a finding kind or rendered message.
    """
    matched_registry_snapshot_ids: set[int] = set()
    projections: list[VerificationFindingPreconditionProjection] = []
    for finding in findings:
        if id(finding) in registry_snapshot_finding_ids:
            matched_registry_snapshot_ids.add(id(finding))
            projections.append(
                project_registry_snapshot_unresolved_finding(
                    finding,
                    calculation_revision_id=calculation_revision_id,
                ),
            )
            continue
        projections.append(
            project_verification_finding_no_recovery(
                finding,
                calculation_revision_id=calculation_revision_id,
            ),
        )
    if frozenset(matched_registry_snapshot_ids) != registry_snapshot_finding_ids:
        raise ValueError("registry snapshot recovery marker must match an in-flight verification finding")
    return tuple(projections)


def _project_finding(
    finding: ModeloVerificationFinding,
    *,
    calculation_revision_id: str,
    condition_id: str,
    evidence_id: str,
    action_id: str | None = None,
    no_recovery_outcome: NoRecoveryOutcome | None = None,
) -> VerificationFindingPreconditionProjection:
    """Build the closed carrier while keeping the domain finding transport-free."""
    if finding.severity is ModeloVerificationFindingSeverity.WARNING:
        return VerificationFindingPreconditionProjection(finding=finding)
    if (action_id is None) == (no_recovery_outcome is None):
        raise ValueError("blocking finding projection requires exactly one action or no-recovery outcome")

    evidence = (
        ConditionEvidence(
            condition_id=condition_id,
            evidence_id=evidence_id,
            provenance=ConditionEvidenceProvenance.APPLICATION_STATE,
            values={
                "calculation_revision_id": calculation_revision_id,
                "finding_kind": finding.kind.value,
                "is_blocking": True,
            },
        ),
    )
    verdict = PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=evidence,
        action=ActionReference(action_id=action_id) if action_id is not None else None,
        conditionality=(
            ActionConditionality.IMMEDIATE
            if action_id is not None
            else ActionConditionality.NOT_APPLICABLE
        ),
        no_recovery_outcome=no_recovery_outcome,
    )
    return VerificationFindingPreconditionProjection(
        finding=finding,
        precondition_verdict=verdict,
    )


__all__ = [
    "ModeloVerificationResult",
    "VerificationFindingPreconditionProjection",
    "project_registry_snapshot_unresolved_finding",
    "project_verification_finding_no_recovery",
    "project_verification_findings",
]
