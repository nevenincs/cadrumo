"""Strict application records for machine-resolvable action outcomes."""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType
from typing import Final

from pydantic import (
    BaseModel,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from ...core import (
    STRICT_FROZEN_CONFIG as _STRICT_FROZEN,
)
from ...core import (
    ActionArgumentResolution,
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)

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


class ConditionEvidence(BaseModel):
    """Typed facts supporting a failed condition from one authority."""

    model_config = _STRICT_FROZEN

    condition_id: str = Field(pattern=_NAMESPACED_ID_PATTERN, min_length=3, max_length=160)
    evidence_id: str = Field(pattern=_NAMESPACED_ID_PATTERN, min_length=3, max_length=160)
    provenance: ActionEvidenceProvenance
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


class ActionArgumentBinding(ActionArgumentResolution):
    """One recovery-action argument and the verdict data that can supply it."""

    model_config = _STRICT_FROZEN


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

        self._reject_arguments_their_evidence_does_not_support()

        missing_from_bindings = tuple(
            item.argument_name for item in self.argument_bindings if item.status is ActionArgumentStatus.MISSING
        )
        if self.missing_argument_names != missing_from_bindings:
            raise ValueError("missing_argument_names must exactly match missing action arguments")

        self._reject_conditionality_the_outcome_contradicts(
            has_no_recovery=has_no_recovery,
            missing_from_bindings=missing_from_bindings,
        )
        return self

    def _reject_arguments_their_evidence_does_not_support(self) -> None:
        """Refuse any condition-evidence argument the declared evidence cannot back.

        The value equality is deliberately type-strict. A binding whose value
        merely compares equal to its evidence fact -- ``1`` against ``True``, or
        a string against the number it spells -- would present the operator an
        argument the evidence does not actually state, which is the whole thing
        this projection exists to rule out.
        """
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

    def _reject_conditionality_the_outcome_contradicts(
        self,
        *,
        has_no_recovery: bool,
        missing_from_bindings: tuple[str, ...],
    ) -> None:
        """Refuse a conditionality the verdict's own shape rules out.

        Conditionality is not free-standing: it is derivable from whether a
        recovery exists and whether its arguments resolved. Declaring it anyway
        and then checking it here is what makes a mismatch between the two an
        error rather than a silent reinterpretation of the verdict.
        """
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


__all__ = [
    "ActionArgumentBinding",
    "ActionReference",
    "ConditionEvidence",
    "PreconditionVerdict",
]
