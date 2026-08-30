"""Typed, locale-neutral precondition projections for modelo verification."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal

from pydantic import BaseModel, model_validator

from ...core import STRICT_FROZEN_CONFIG, ActionEvidenceProvenance
from ...core.identity import CalculationRevisionId
from ...domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingSeverity, VerificationReport
from ._preconditions import ModeloPreconditionFailure, build_modelo_precondition_failure


class VerificationFindingPreconditionProjection(BaseModel):
    """Pair one report fact with its exact application precondition identity."""

    model_config = STRICT_FROZEN_CONFIG

    finding: ModeloVerificationFinding
    precondition_failure: ModeloPreconditionFailure | None = None

    @model_validator(mode="after")
    def _require_a_failure_only_for_blocking_findings(self) -> VerificationFindingPreconditionProjection:
        is_blocking = self.finding.severity is ModeloVerificationFindingSeverity.BLOCKING
        if not is_blocking and self.precondition_failure is not None:
            raise ValueError("warning verification findings cannot carry a precondition failure")
        if is_blocking and self.precondition_failure is None:
            raise ValueError("blocking verification findings require a precondition failure")
        if self.precondition_failure is not None and self.precondition_failure.subject_leaf_key != "modelo.work.verify":
            raise ValueError("verification finding preconditions must identify the verify leaf")
        return self


class ModeloVerificationResult(BaseModel):
    """Persisted report facts paired with transient application decisions."""

    model_config = STRICT_FROZEN_CONFIG

    report: VerificationReport
    finding_preconditions: tuple[VerificationFindingPreconditionProjection, ...]

    @model_validator(mode="after")
    def _require_exact_report_finding_projection(self) -> ModeloVerificationResult:
        if tuple(projection.finding for projection in self.finding_preconditions) != self.report.findings:
            raise ValueError("verification preconditions must project the report findings in order")
        return self


def build_verification_precondition_failure(
    *,
    calculation_revision_id: CalculationRevisionId,
    work_unit_id: str,
    condition_id: str,
    scenario_id: str,
    evidence_id: str,
    evidence_values: Mapping[str, str | int | bool | Decimal],
    provenance: ActionEvidenceProvenance,
    action_id: str | None = None,
) -> ModeloPreconditionFailure:
    """Build one verify failure with the common persisted addressing facts."""
    return build_modelo_precondition_failure(
        subject_leaf_key="modelo.work.verify",
        condition_id=condition_id,
        scenario_id=scenario_id,
        evidence_id=evidence_id,
        evidence_values={
            "calculation_revision_id": calculation_revision_id,
            "work_unit_id": work_unit_id,
            **evidence_values,
        },
        provenance=provenance,
        action_id=action_id,
        action_argument_values={} if action_id is not None else None,
    )


def project_verification_findings(
    findings: Iterable[ModeloVerificationFinding],
    *,
    failures_by_finding_id: Mapping[int, ModeloPreconditionFailure],
) -> tuple[VerificationFindingPreconditionProjection, ...]:
    """Project findings by constructor identity; never classify from rendered text."""
    matched_ids: set[int] = set()
    projections: list[VerificationFindingPreconditionProjection] = []
    for finding in findings:
        failure = failures_by_finding_id.get(id(finding))
        if failure is not None:
            matched_ids.add(id(finding))
        projections.append(
            VerificationFindingPreconditionProjection(
                finding=finding,
                precondition_failure=failure,
            ),
        )
    if matched_ids != set(failures_by_finding_id):
        raise ValueError("verification precondition identity must match an in-flight finding")
    return tuple(projections)


__all__ = [
    "ModeloVerificationResult",
    "VerificationFindingPreconditionProjection",
    "build_verification_precondition_failure",
    "project_verification_findings",
]
