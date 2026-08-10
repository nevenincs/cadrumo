"""Strict application records for machine-resolvable action outcomes."""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from pydantic import (
    BaseModel,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN

_NAMESPACED_ID_PATTERN = r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$"
_FIELD_KEY_PATTERN = r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$"
_PRESENTATION_KEY_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "action",
        "command",
        "help",
        "hint",
        "instruction",
        "label",
        "message",
        "next",
        "prose",
        "remediation",
        "suggestion",
        "text",
        "title",
    }
)
_RAW_AEAT_COMMAND_PATTERN: Final[re.Pattern[str]] = re.compile(r"(?i)(?:^|[\s`'\";|&()])aeat(?:\s+|$)")


def _is_presentation_key(key: str) -> bool:
    """Return whether a factual key contains a presentation/action-prose token."""
    return any(token in _PRESENTATION_KEY_TOKENS for token in re.split(r"[._]", key))


class ConditionEvidenceProvenance(StrEnum):
    """Authority that observed one failed-condition fact."""

    APPLICATION_STATE = "application_state"
    DOMAIN_EVALUATION = "domain_evaluation"
    PERSISTED_STATE = "persisted_state"
    REGISTRY_RECORD = "registry_record"
    RUNTIME_OBSERVATION = "runtime_observation"


class ActionArgumentSource(StrEnum):
    """Namespaced origins for action argument materialisation.

    This intentionally is not the AEAT registry binding-source taxonomy.  Its
    values identify only data already available to an application verdict.
    """

    VERDICT_CONTEXT = "operator_action.verdict_context"
    CONDITION_EVIDENCE = "operator_action.condition_evidence"
    REQUEST_CONTEXT = "operator_action.request_context"


class ActionArgumentStatus(StrEnum):
    """Whether one action argument has a concrete value."""

    RESOLVED = "resolved"
    MISSING = "missing"


class ActionConditionality(StrEnum):
    """Whether a recovery action is presently materialisable."""

    IMMEDIATE = "immediate"
    REQUIRES_ARGUMENTS = "requires_arguments"
    NOT_APPLICABLE = "not_applicable"


class NoRecoveryOutcome(StrEnum):
    """Closed reasons a refusal deliberately has no recovery action."""

    TERMINAL = "terminal"
    SAFETY = "safety"
    OPERATOR_DECISION = "operator_decision"


class ConditionEvidence(BaseModel):
    """Typed facts supporting a failed condition from one authority."""

    model_config = _STRICT_FROZEN

    condition_id: str = Field(pattern=_NAMESPACED_ID_PATTERN, min_length=3, max_length=160)
    evidence_id: str = Field(pattern=_NAMESPACED_ID_PATTERN, min_length=3, max_length=160)
    provenance: ConditionEvidenceProvenance
    values: Mapping[str, str | int | bool | Decimal] = Field(min_length=1)

    @field_validator("values")
    @classmethod
    def _freeze_values(
        cls,
        value: Mapping[str, str | int | bool | Decimal],
    ) -> Mapping[str, str | int | bool | Decimal]:
        """Freeze a lexically ordered evidence map for deterministic output."""
        if any(not re.fullmatch(_FIELD_KEY_PATTERN, key) for key in value):
            raise ValueError("condition evidence value keys must be stable fact identifiers")
        if any(_is_presentation_key(key) for key in value):
            raise ValueError("condition evidence value keys cannot carry presentation or action prose")
        if any(isinstance(item, str) and _RAW_AEAT_COMMAND_PATTERN.search(item) for item in value.values()):
            raise ValueError("condition evidence values cannot carry raw aeat command prose")
        return MappingProxyType(dict(sorted(value.items())))

    @field_serializer("values")
    def _serialize_values(
        self,
        value: Mapping[str, str | int | bool | Decimal],
    ) -> dict[str, str | int | bool | Decimal]:
        """Project the immutable value map as an ordinary deterministic mapping."""
        return dict(value)


class ActionReference(BaseModel):
    """Stable action identity; catalogue resolution is owned by a later layer."""

    model_config = _STRICT_FROZEN

    action_id: str = Field(pattern=_NAMESPACED_ID_PATTERN, min_length=3, max_length=160)


class ActionArgumentBinding(BaseModel):
    """One recovery-action argument and the verdict data that can supply it."""

    model_config = _STRICT_FROZEN

    argument_name: str = Field(pattern=_FIELD_KEY_PATTERN, min_length=1, max_length=120)
    status: ActionArgumentStatus
    value: str | int | bool | Decimal | None = None
    source: ActionArgumentSource | None = None
    source_key: str | None = Field(default=None, pattern=_FIELD_KEY_PATTERN, min_length=1, max_length=160)
    source_evidence_id: str | None = Field(
        default=None,
        pattern=_NAMESPACED_ID_PATTERN,
        min_length=3,
        max_length=160,
    )

    @model_validator(mode="after")
    def _validate_resolution(self) -> ActionArgumentBinding:
        """Keep resolved and missing argument states unambiguous."""
        if self.status is ActionArgumentStatus.RESOLVED:
            if self.value is None or self.source is None or self.source_key is None:
                raise ValueError("resolved action arguments require value, source, and source_key")
            if self.source is ActionArgumentSource.CONDITION_EVIDENCE and self.source_evidence_id is None:
                raise ValueError("condition-evidence action arguments require source_evidence_id")
            if self.source is not ActionArgumentSource.CONDITION_EVIDENCE and self.source_evidence_id is not None:
                raise ValueError("only condition-evidence action arguments can carry source_evidence_id")
        elif (
            self.value is not None
            or self.source is not None
            or self.source_key is not None
            or self.source_evidence_id is not None
        ):
            raise ValueError("missing action arguments cannot carry value or source")
        return self


class PreconditionVerdict(BaseModel):
    """Application-owned outcome for one failed precondition.

    The record identifies the rejected condition and evidence, then carries
    exactly one actionable recovery reference or an explicit closed
    no-recovery outcome.  It neither resolves an action catalogue nor embeds
    presentation text or an executable command.
    """

    model_config = _STRICT_FROZEN

    failed_condition_id: str = Field(pattern=_NAMESPACED_ID_PATTERN, min_length=3, max_length=160)
    evidence: tuple[ConditionEvidence, ...] = Field(min_length=1)
    action: ActionReference | None = None
    argument_bindings: tuple[ActionArgumentBinding, ...] = Field(default_factory=tuple)
    missing_argument_names: tuple[str, ...] = Field(default_factory=tuple)
    conditionality: ActionConditionality
    no_recovery_outcome: NoRecoveryOutcome | None = None

    @field_validator("evidence")
    @classmethod
    def _evidence_matches_failed_condition(cls, value: tuple[ConditionEvidence, ...]) -> tuple[ConditionEvidence, ...]:
        """Require unique evidence identities before cross-field condition matching."""
        evidence_ids = tuple(item.evidence_id for item in value)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("condition evidence identities must be unique")
        return tuple(sorted(value, key=lambda item: item.evidence_id))

    @field_validator("argument_bindings")
    @classmethod
    def _argument_names_are_unique(
        cls,
        value: tuple[ActionArgumentBinding, ...],
    ) -> tuple[ActionArgumentBinding, ...]:
        """Refuse two incompatible materialisations of the same argument."""
        names = tuple(item.argument_name for item in value)
        if len(set(names)) != len(names):
            raise ValueError("action argument names must be unique")
        return tuple(sorted(value, key=lambda item: item.argument_name))

    @field_validator("missing_argument_names")
    @classmethod
    def _missing_argument_names_are_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Keep the public missing-argument list stable and unambiguous."""
        if any(not name or name != name.strip() for name in value):
            raise ValueError("missing argument names must be non-blank")
        if len(set(value)) != len(value):
            raise ValueError("missing argument names must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def _validate_outcome(self) -> PreconditionVerdict:
        """Enforce condition evidence, action/no-recovery exclusivity, and argument consistency."""
        if any(item.condition_id != self.failed_condition_id for item in self.evidence):
            raise ValueError("condition evidence must identify the failed condition")

        has_action = self.action is not None
        has_no_recovery = self.no_recovery_outcome is not None
        if has_action == has_no_recovery:
            raise ValueError("a precondition verdict requires exactly one action or no_recovery_outcome")

        evidence_by_id = {item.evidence_id: item for item in self.evidence}
        for binding in self.argument_bindings:
            if binding.source is not ActionArgumentSource.CONDITION_EVIDENCE:
                continue
            assert binding.source_evidence_id is not None
            evidence = evidence_by_id.get(binding.source_evidence_id)
            if evidence is None:
                raise ValueError("condition-evidence action argument must reference declared evidence")
            assert binding.source_key is not None
            evidence_value = evidence.values.get(binding.source_key)
            if evidence_value is None and binding.source_key not in evidence.values:
                raise ValueError("condition-evidence action argument must reference a declared evidence fact")
            if type(binding.value) is not type(evidence_value) or binding.value != evidence_value:
                raise ValueError("condition-evidence action argument value must exactly match its evidence fact")

        missing_from_bindings = tuple(
            item.argument_name for item in self.argument_bindings if item.status is ActionArgumentStatus.MISSING
        )
        if self.missing_argument_names != missing_from_bindings:
            raise ValueError("missing_argument_names must exactly match missing action arguments")

        if has_no_recovery:
            if self.argument_bindings or self.missing_argument_names:
                raise ValueError("no-recovery outcomes cannot carry action arguments")
            if self.conditionality is not ActionConditionality.NOT_APPLICABLE:
                raise ValueError("no-recovery outcomes require not_applicable conditionality")
        elif self.conditionality is ActionConditionality.NOT_APPLICABLE:
            raise ValueError("recovery actions cannot use not_applicable conditionality")
        elif missing_from_bindings and self.conditionality is not ActionConditionality.REQUIRES_ARGUMENTS:
            raise ValueError("missing action arguments require requires_arguments conditionality")
        elif not missing_from_bindings and self.conditionality is not ActionConditionality.IMMEDIATE:
            raise ValueError("fully resolved recovery actions require immediate conditionality")
        return self


__all__ = [
    "ActionArgumentBinding",
    "ActionArgumentSource",
    "ActionArgumentStatus",
    "ActionConditionality",
    "ActionReference",
    "ConditionEvidence",
    "ConditionEvidenceProvenance",
    "NoRecoveryOutcome",
    "PreconditionVerdict",
]
