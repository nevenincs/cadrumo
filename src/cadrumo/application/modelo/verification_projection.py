"""Strict public snapshots of one canonical verification completion."""

from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel, model_validator

from ...core.casilla_id import CasillaId
from ...core.filing_year import FilingYear
from ...core.identity.hex_ids import CalculationRevisionId, VerificationReportId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from ...domain.calculations.registry.ids import LegalRefId, ModeloId, RevisionId, SourceRefId, VerificationExpectationId
from ...domain.modelos.filing_text import ModeloActorLabel
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
)
from ..operations.public_scalar import (
    PublicNamedScalar,
    PublicScalar,
    project_facts,
    project_scalar,
    restore_facts,
    restore_scalar,
)
from ..operator_actions.models import ActionArgumentBinding, ActionReference, ConditionEvidence, PreconditionVerdict
from .preconditions import ModeloPreconditionFailure
from .verification_preconditions import ModeloVerificationResult, VerificationFindingPreconditionProjection


class ModeloRegistrySnapshotCoordinates(BaseModel):
    """Published revision coordinates without domain coercion in the wire schema."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    modelo: ModeloId
    revision_id: RevisionId
    modelo_year: FilingYear
    period: str


class ModeloFindingSnapshot(BaseModel):
    """Locale-neutral finding preserving the exact scalar type of every fact."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: ModeloVerificationFindingKind
    severity: ModeloVerificationFindingSeverity
    casilla_id: CasillaId | None
    expectation_id: VerificationExpectationId | None
    message_locale_key: str
    message_facts: tuple[PublicNamedScalar, ...]
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]

    @classmethod
    def from_finding(cls, finding: ModeloVerificationFinding) -> Self:
        """Encode decimals without changing report identity or finding order."""
        return cls.model_validate(
            finding.model_dump(mode="python") | {"message_facts": project_facts(finding.message_facts)}
        )

    def to_finding(self) -> ModeloVerificationFinding:
        """Restore through the canonical finding validator."""
        return ModeloVerificationFinding.model_validate(
            self.model_dump(mode="python") | {"message_facts": restore_facts(self.message_facts)}
        )


class ModeloConditionEvidenceSnapshot(BaseModel):
    """Typed precondition evidence with exact wire scalar variants."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    condition_id: str
    evidence_id: str
    provenance: ActionEvidenceProvenance
    values: tuple[PublicNamedScalar, ...]

    @classmethod
    def from_evidence(cls, evidence: ConditionEvidence) -> Self:
        """Project only declared evidence facts."""
        return cls.model_validate(evidence.model_dump(mode="python") | {"values": project_facts(evidence.values)})

    def to_evidence(self) -> ConditionEvidence:
        """Restore canonical evidence without widening its type."""
        return ConditionEvidence.model_validate(self.model_dump(mode="python") | {"values": restore_facts(self.values)})


class ModeloArgumentSnapshot(BaseModel):
    """A declared recovery argument, not an executable command."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    argument_name: str
    status: ActionArgumentStatus
    value: PublicScalar | None
    source: ActionArgumentSource | None
    source_key: str | None
    source_evidence_id: str | None

    @classmethod
    def from_argument(cls, argument: ActionArgumentBinding) -> Self:
        """Preserve the application's exact argument facts."""
        return cls.model_validate(
            argument.model_dump(mode="python")
            | {"value": project_scalar(argument.value) if argument.value is not None else None}
        )

    def to_argument(self) -> ActionArgumentBinding:
        """Validate the restored canonical recovery argument."""
        return ActionArgumentBinding.model_validate(
            self.model_dump(mode="python") | {"value": restore_scalar(self.value) if self.value is not None else None}
        )


class ModeloPreconditionSnapshot(BaseModel):
    """A complete application refusal identity and its canonical recovery facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    subject_leaf_key: str
    scenario_id: str
    failed_condition_id: str
    evidence: tuple[ModeloConditionEvidenceSnapshot, ...]
    action: ActionReference | None
    argument_bindings: tuple[ModeloArgumentSnapshot, ...]
    missing_argument_names: tuple[str, ...]
    conditionality: ActionConditionality
    no_recovery_outcome: NoRecoveryOutcome | None

    @classmethod
    def from_failure(cls, failure: ModeloPreconditionFailure) -> Self:
        """Flatten one verdict without losing its discriminators or evidence."""
        verdict = failure.verdict
        return cls.model_validate(
            verdict.model_dump(mode="python")
            | {
                "subject_leaf_key": failure.subject_leaf_key,
                "scenario_id": failure.scenario_id,
                "evidence": tuple(ModeloConditionEvidenceSnapshot.from_evidence(item) for item in verdict.evidence),
                "argument_bindings": tuple(
                    ModeloArgumentSnapshot.from_argument(item) for item in verdict.argument_bindings
                ),
            }
        )

    def to_failure(self) -> ModeloPreconditionFailure:
        """Reapply the canonical action and condition declarations."""
        verdict = PreconditionVerdict.model_validate(
            self.model_dump(mode="python", exclude={"subject_leaf_key", "scenario_id"})
            | {
                "evidence": tuple(item.to_evidence() for item in self.evidence),
                "argument_bindings": tuple(item.to_argument() for item in self.argument_bindings),
            }
        )
        return ModeloPreconditionFailure(
            subject_leaf_key=self.subject_leaf_key, scenario_id=self.scenario_id, verdict=verdict
        )


class ModeloFindingPreconditionSnapshot(BaseModel):
    """An ordered finding paired with its exact application decision."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    finding: ModeloFindingSnapshot
    precondition_failure: ModeloPreconditionSnapshot | None


class ModeloVerificationReportSnapshot(BaseModel):
    """All report facts, retained in their canonical order and representation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    verification_report_id: VerificationReportId
    calculation_revision_id: CalculationRevisionId
    registry_snapshot_ref: ModeloRegistrySnapshotCoordinates
    completeness_status: VerificationCompletenessStatus
    findings: tuple[ModeloFindingSnapshot, ...]
    resolved_casilla_ids: tuple[CasillaId, ...]
    missing_required_casilla_ids: tuple[CasillaId, ...]
    run_at: datetime
    verified_by: ModeloActorLabel
    granted_verificado_completo: bool

    @classmethod
    def from_report(cls, report: VerificationReport) -> Self:
        """Retain every canonical report field and ordered finding."""
        return cls.model_validate(
            report.model_dump(mode="python")
            | {"findings": tuple(ModeloFindingSnapshot.from_finding(finding) for finding in report.findings)}
        )

    def to_report(self) -> VerificationReport:
        """Restore the content-addressed report through its owning validator."""
        return VerificationReport.model_validate(
            self.model_dump(mode="python") | {"findings": tuple(finding.to_finding() for finding in self.findings)}
        )


class ModeloVerificationSnapshot(BaseModel):
    """One settled report, its recovery decisions and publication witness."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    report: ModeloVerificationReportSnapshot
    published: bool
    finding_preconditions: tuple[ModeloFindingPreconditionSnapshot, ...]

    @classmethod
    def from_verification(cls, outcome: ModeloVerificationResult) -> Self:
        """Retain the authority's actual completion without a later report read."""
        return cls(
            report=ModeloVerificationReportSnapshot.from_report(outcome.report),
            published=outcome.published,
            finding_preconditions=tuple(
                ModeloFindingPreconditionSnapshot(
                    finding=ModeloFindingSnapshot.from_finding(item.finding),
                    precondition_failure=(
                        ModeloPreconditionSnapshot.from_failure(item.precondition_failure)
                        if item.precondition_failure is not None
                        else None
                    ),
                )
                for item in outcome.finding_preconditions
            ),
        )

    def to_verification(self) -> ModeloVerificationResult:
        """Restore canonical report and findings for locale-aware presentation."""
        return ModeloVerificationResult(
            report=self.report.to_report(),
            published=self.published,
            finding_preconditions=tuple(
                VerificationFindingPreconditionProjection(
                    finding=item.finding.to_finding(),
                    precondition_failure=(
                        item.precondition_failure.to_failure() if item.precondition_failure is not None else None
                    ),
                )
                for item in self.finding_preconditions
            ),
        )

    @model_validator(mode="after")
    def _canonical_report(self) -> Self:
        self.to_verification()
        return self
