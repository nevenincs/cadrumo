"""Closed public snapshots of canonical action evidence and precondition verdicts."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, model_validator

from ...core.identifier_grammar import NamespacedId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from ..operations.public_scalar import (
    PublicNamedScalar,
    PublicScalar,
    project_facts,
    project_scalar,
    restore_facts,
    restore_scalar,
)
from .models import ActionArgumentBinding, ActionReference, ConditionEvidence, PreconditionVerdict


class ConditionEvidenceSnapshot(BaseModel):
    """One canonical condition evidence with typed immutable scalar facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    condition_id: NamespacedId
    evidence_id: NamespacedId
    provenance: ActionEvidenceProvenance
    values: tuple[PublicNamedScalar, ...]

    @classmethod
    def from_evidence(cls, evidence: ConditionEvidence) -> Self:
        """Copy validated evidence without its mutable-map wire shape."""
        return cls(
            condition_id=evidence.condition_id,
            evidence_id=evidence.evidence_id,
            provenance=evidence.provenance,
            values=project_facts(evidence.values),
        )

    def to_evidence(self) -> ConditionEvidence:
        """Restore the canonical evidence grammar and factual checks."""
        return ConditionEvidence(
            condition_id=self.condition_id,
            evidence_id=self.evidence_id,
            provenance=self.provenance,
            values=restore_facts(self.values),
        )

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        self.to_evidence()
        return self


class ActionArgumentSnapshot(BaseModel):
    """One bounded recovery argument with its canonical provenance."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    argument_name: str
    status: ActionArgumentStatus
    value: PublicScalar | None = None
    source: ActionArgumentSource | None = None
    source_key: str | None = None
    source_evidence_id: str | None = None

    @classmethod
    def from_argument(cls, argument: ActionArgumentBinding) -> Self:
        """Copy a canonical argument without untagged decimal drift."""
        return cls(
            argument_name=argument.argument_name,
            status=argument.status,
            value=project_scalar(argument.value) if argument.value is not None else None,
            source=argument.source,
            source_key=argument.source_key,
            source_evidence_id=argument.source_evidence_id,
        )

    def to_argument(self) -> ActionArgumentBinding:
        """Restore the canonical argument shape."""
        return ActionArgumentBinding(
            argument_name=self.argument_name,
            status=self.status,
            value=restore_scalar(self.value) if self.value is not None else None,
            source=self.source,
            source_key=self.source_key,
            source_evidence_id=self.source_evidence_id,
        )

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        self.to_argument()
        return self


class PreconditionVerdictSnapshot(BaseModel):
    """Typed action evidence needed by the existing CLI action resolver."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    failed_condition_id: NamespacedId
    evidence: tuple[ConditionEvidenceSnapshot, ...]
    action_id: NamespacedId | None = None
    argument_bindings: tuple[ActionArgumentSnapshot, ...] = ()
    missing_argument_names: tuple[str, ...] = ()
    conditionality: ActionConditionality
    no_recovery_outcome: NoRecoveryOutcome | None = None

    @classmethod
    def from_verdict(cls, verdict: PreconditionVerdict) -> Self:
        """Copy one canonical verdict without its mapping serializer."""
        return cls(
            failed_condition_id=verdict.failed_condition_id,
            evidence=tuple(ConditionEvidenceSnapshot.from_evidence(item) for item in verdict.evidence),
            action_id=verdict.action.action_id if verdict.action is not None else None,
            argument_bindings=tuple(ActionArgumentSnapshot.from_argument(item) for item in verdict.argument_bindings),
            missing_argument_names=verdict.missing_argument_names,
            conditionality=verdict.conditionality,
            no_recovery_outcome=verdict.no_recovery_outcome,
        )

    def to_verdict(self) -> PreconditionVerdict:
        """Revalidate evidence joins, action arguments, and closed outcome."""
        return PreconditionVerdict(
            failed_condition_id=self.failed_condition_id,
            evidence=tuple(item.to_evidence() for item in self.evidence),
            action=ActionReference(action_id=self.action_id) if self.action_id is not None else None,
            argument_bindings=tuple(item.to_argument() for item in self.argument_bindings),
            missing_argument_names=self.missing_argument_names,
            conditionality=self.conditionality,
            no_recovery_outcome=self.no_recovery_outcome,
        )

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        self.to_verdict()
        return self
