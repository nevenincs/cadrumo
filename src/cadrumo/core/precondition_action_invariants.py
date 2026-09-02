"""Canonical factual evidence and outcome invariants for operator actions."""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType
from typing import Final, Self

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator

from .action_argument_resolution import ActionArgumentResolution
from .identifier_grammar import FIELD_KEY_PATTERN, NamespacedId
from .models import STRICT_FROZEN_CONFIG
from .operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)

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
_RAW_AEAT_COMMAND_PATTERN: Final[re.Pattern[str]] = re.compile(r"(?:^|[\s`'\";|&()])aeat(?=$|[\s`'\";|&()])")


def _is_presentation_key(key: str) -> bool:
    """Return whether a factual key carries presentation or action guidance."""
    return any(token in _PRESENTATION_KEY_TOKENS for token in re.split(r"[._]", key))


class PreconditionEvidence(BaseModel):
    """Immutable factual evidence for one evaluated precondition."""

    model_config = STRICT_FROZEN_CONFIG

    condition_id: NamespacedId
    evidence_id: NamespacedId
    provenance: ActionEvidenceProvenance
    values: Mapping[str, str | int | bool | Decimal] = Field(min_length=1)

    @field_validator("values")
    @classmethod
    def _freeze_values(
        cls,
        value: Mapping[str, str | int | bool | Decimal],
    ) -> Mapping[str, str | int | bool | Decimal]:
        """Freeze lexically ordered factual values and refuse presentation prose."""
        if any(not re.fullmatch(FIELD_KEY_PATTERN, key) for key in value):
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
        """Emit immutable facts as one deterministic ordinary mapping."""
        return dict(value)


class PreconditionActionIdentity(BaseModel):
    """Stable action identity shared by application and wire projections."""

    model_config = STRICT_FROZEN_CONFIG

    action_id: NamespacedId


def _require_argument_matches_its_evidence(
    argument: ActionArgumentResolution,
    evidence_by_id: Mapping[str, PreconditionEvidence],
) -> None:
    """Refuse a condition-evidence argument whose declared fact is absent or divergent.

    The value comparison is type-exact on purpose: a ``1`` that reads as an ``int``
    where the evidence recorded ``True`` is a different fact, not a match.
    """
    source_evidence_id = argument.source_evidence_id
    source_key = argument.source_key
    if source_evidence_id is None or source_key is None:
        raise ValueError("condition-evidence action argument must name both its evidence id and its evidence key")
    evidence = evidence_by_id.get(source_evidence_id)
    if evidence is None:
        raise ValueError("condition-evidence action argument must reference declared evidence")
    evidence_value = evidence.values.get(source_key)
    if evidence_value is None and source_key not in evidence.values:
        raise ValueError("condition-evidence action argument must reference a declared evidence fact")
    if type(argument.value) is not type(evidence_value) or argument.value != evidence_value:
        raise ValueError("condition-evidence action argument value must exactly match its evidence fact")


class PreconditionOutcomeInvariant[
    EvidenceT: PreconditionEvidence,
    ActionT: BaseModel,
    ArgumentT: ActionArgumentResolution,
](BaseModel):
    """Canonical consistency rules for an actionable or closed precondition outcome."""

    model_config = STRICT_FROZEN_CONFIG

    failed_condition_id: NamespacedId
    evidence: tuple[EvidenceT, ...] = Field(min_length=1)
    action: ActionT | None = None
    argument_bindings: tuple[ArgumentT, ...] = Field(default_factory=tuple)
    missing_argument_names: tuple[str, ...] = Field(default_factory=tuple)
    conditionality: ActionConditionality
    no_recovery_outcome: NoRecoveryOutcome | None = None

    @field_validator("evidence")
    @classmethod
    def _canonicalize_evidence(cls, value: tuple[EvidenceT, ...]) -> tuple[EvidenceT, ...]:
        """Reject duplicate evidence identities and produce deterministic order."""
        evidence_ids = tuple(item.evidence_id for item in value)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("condition evidence identities must be unique")
        return tuple(sorted(value, key=lambda item: item.evidence_id))

    @field_validator("argument_bindings")
    @classmethod
    def _canonicalize_arguments(cls, value: tuple[ArgumentT, ...]) -> tuple[ArgumentT, ...]:
        """Reject competing materialisations of one target argument."""
        names = tuple(item.argument_name for item in value)
        if len(set(names)) != len(names):
            raise ValueError("action argument names must be unique")
        return tuple(sorted(value, key=lambda item: item.argument_name))

    @field_validator("missing_argument_names")
    @classmethod
    def _canonicalize_missing_names(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Keep the public missing-input list stable and unambiguous."""
        if any(not re.fullmatch(FIELD_KEY_PATTERN, name) for name in value):
            raise ValueError("missing action argument names must be stable identifiers")
        if len(set(value)) != len(value):
            raise ValueError("missing action argument names must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def _validate_outcome(self) -> Self:
        """Enforce factual joins, one outcome shape, and derived conditionality."""
        if any(item.condition_id != self.failed_condition_id for item in self.evidence):
            raise ValueError("condition evidence must identify the failed condition")

        has_action = self.action is not None
        has_no_recovery = self.no_recovery_outcome is not None
        if has_action == has_no_recovery:
            raise ValueError("a precondition outcome requires exactly one action or no_recovery_outcome")

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
        """Refuse condition-evidence arguments not backed by declared facts."""
        evidence_by_id = {item.evidence_id: item for item in self.evidence}
        for argument in self.argument_bindings:
            if argument.source is not ActionArgumentSource.CONDITION_EVIDENCE:
                continue
            _require_argument_matches_its_evidence(argument, evidence_by_id)

    def _reject_conditionality_the_outcome_contradicts(
        self,
        *,
        has_no_recovery: bool,
        missing_from_bindings: tuple[str, ...],
    ) -> None:
        """Refuse a conditionality the outcome's own shape rules out."""
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
    "PreconditionActionIdentity",
    "PreconditionEvidence",
    "PreconditionOutcomeInvariant",
]
