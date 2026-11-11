"""Canonical factual evidence and outcome invariants for operator actions."""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Final, Self

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator

from .action_argument_resolution import ActionArgumentResolution
from .errors.hierarchy import pydantic_validation_boundary
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
    @pydantic_validation_boundary
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


def _canonical_argument_bindings[ArgumentT: ActionArgumentResolution](
    value: tuple[ArgumentT, ...],
) -> tuple[ArgumentT, ...]:
    """Reject competing materialisations of one target argument and order them by name."""
    names = tuple(item.argument_name for item in value)
    if len(set(names)) != len(names):
        raise ValueError("action argument names must be unique")
    return tuple(sorted(value, key=lambda item: item.argument_name))


def _canonical_missing_names(value: tuple[str, ...]) -> tuple[str, ...]:
    """Keep a public missing-input list stable and unambiguous."""
    if any(not re.fullmatch(FIELD_KEY_PATTERN, name) for name in value):
        raise ValueError("missing action argument names must be stable identifiers")
    if len(set(value)) != len(value):
        raise ValueError("missing action argument names must be unique")
    return tuple(sorted(value))


def _missing_names_of_bindings(
    missing_argument_names: tuple[str, ...],
    argument_bindings: tuple[ActionArgumentResolution, ...],
) -> tuple[str, ...]:
    """Return the missing bindings' names, refusing a missing-name list that names any other set."""
    missing_from_bindings = tuple(
        item.argument_name for item in argument_bindings if item.status is ActionArgumentStatus.MISSING
    )
    if missing_argument_names != missing_from_bindings:
        raise ValueError("missing_argument_names must exactly match missing action arguments")
    return missing_from_bindings


def _require_recovery_conditionality(
    conditionality: ActionConditionality,
    missing_from_bindings: tuple[str, ...],
) -> None:
    """Refuse a recovery action whose conditionality its own bindings contradict."""
    if conditionality is ActionConditionality.NOT_APPLICABLE:
        raise ValueError("recovery actions cannot use not_applicable conditionality")
    if missing_from_bindings and conditionality is not ActionConditionality.REQUIRES_ARGUMENTS:
        raise ValueError("missing action arguments require requires_arguments conditionality")
    if not missing_from_bindings and conditionality is not ActionConditionality.IMMEDIATE:
        raise ValueError("fully resolved recovery actions require immediate conditionality")


def _is_empty(value: tuple[object, ...]) -> bool:
    """Whether an optional ordered list holds nothing, so the serialized record leaves it out."""
    return not value


class PreconditionAlternativeAction[
    ActionT: PreconditionActionIdentity,
    ArgumentT: ActionArgumentResolution,
](BaseModel):
    """One further recovery action that clears the same failed condition as the primary one.

    It follows the argument grammar of the outcome's primary action: unique
    argument names, missing names matching the missing bindings, and the
    conditionality those bindings derive. Arguments drawn from condition
    evidence are checked by the outcome, which holds the evidence.
    """

    model_config = STRICT_FROZEN_CONFIG

    action: ActionT
    argument_bindings: tuple[ArgumentT, ...] = Field(default_factory=tuple)
    missing_argument_names: tuple[str, ...] = Field(default_factory=tuple)
    conditionality: ActionConditionality

    @field_validator("argument_bindings")
    @classmethod
    @pydantic_validation_boundary
    def _canonicalize_alternative_arguments(cls, value: tuple[ArgumentT, ...]) -> tuple[ArgumentT, ...]:
        """Reject competing materialisations of one target argument."""
        return _canonical_argument_bindings(value)

    @field_validator("missing_argument_names")
    @classmethod
    @pydantic_validation_boundary
    def _canonicalize_alternative_missing_names(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Keep the public missing-input list stable and unambiguous."""
        return _canonical_missing_names(value)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_alternative(self) -> Self:
        """Derive the alternative's conditionality from its own bindings."""
        missing_from_bindings = _missing_names_of_bindings(self.missing_argument_names, self.argument_bindings)
        _require_recovery_conditionality(self.conditionality, missing_from_bindings)
        return self

    def offered_action_id(self) -> str:
        """Return the catalogue identity of the offered action."""
        return self.action.action_id

    def offered_arguments(self) -> tuple[ActionArgumentResolution, ...]:
        """Return the offered action's argument bindings."""
        return self.argument_bindings


class PreconditionOutcomeInvariant[
    EvidenceT: PreconditionEvidence,
    ActionT: PreconditionActionIdentity,
    ArgumentT: ActionArgumentResolution,
    AlternativeT: PreconditionAlternativeAction[Any, Any],
](BaseModel):
    """Canonical consistency rules for an actionable or closed precondition outcome.

    ``action`` and its argument fields describe the primary recovery action. An
    actionable outcome may add ``alternative_actions``: further ways to clear
    the same failed condition, offered in list order after the primary one. An
    outcome without alternatives leaves the list out of its serialized form, so
    it reads and hashes exactly as a record written before the list existed.
    """

    model_config = STRICT_FROZEN_CONFIG

    failed_condition_id: NamespacedId
    evidence: tuple[EvidenceT, ...] = Field(min_length=1)
    action: ActionT | None = None
    argument_bindings: tuple[ArgumentT, ...] = Field(default_factory=tuple)
    missing_argument_names: tuple[str, ...] = Field(default_factory=tuple)
    conditionality: ActionConditionality
    no_recovery_outcome: NoRecoveryOutcome | None = None
    alternative_actions: tuple[AlternativeT, ...] = Field(default_factory=tuple, exclude_if=_is_empty)

    @field_validator("evidence")
    @classmethod
    @pydantic_validation_boundary
    def _canonicalize_evidence(cls, value: tuple[EvidenceT, ...]) -> tuple[EvidenceT, ...]:
        """Reject duplicate evidence identities and produce deterministic order."""
        evidence_ids = tuple(item.evidence_id for item in value)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("condition evidence identities must be unique")
        return tuple(sorted(value, key=lambda item: item.evidence_id))

    @field_validator("argument_bindings")
    @classmethod
    @pydantic_validation_boundary
    def _canonicalize_arguments(cls, value: tuple[ArgumentT, ...]) -> tuple[ArgumentT, ...]:
        """Reject competing materialisations of one target argument."""
        return _canonical_argument_bindings(value)

    @field_validator("missing_argument_names")
    @classmethod
    @pydantic_validation_boundary
    def _canonicalize_missing_names(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Keep the public missing-input list stable and unambiguous."""
        return _canonical_missing_names(value)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_outcome(self) -> Self:
        """Enforce factual joins, one outcome shape, and derived conditionality."""
        if any(item.condition_id != self.failed_condition_id for item in self.evidence):
            raise ValueError("condition evidence must identify the failed condition")

        has_action = self.action is not None
        has_no_recovery = self.no_recovery_outcome is not None
        if has_action == has_no_recovery:
            raise ValueError("a precondition outcome requires exactly one action or no_recovery_outcome")

        self._reject_arguments_their_evidence_does_not_support()

        missing_from_bindings = _missing_names_of_bindings(self.missing_argument_names, self.argument_bindings)

        self._reject_conditionality_the_outcome_contradicts(
            has_no_recovery=has_no_recovery,
            missing_from_bindings=missing_from_bindings,
        )
        self._reject_alternatives_the_outcome_cannot_carry()
        return self

    def _reject_arguments_their_evidence_does_not_support(self) -> None:
        """Refuse condition-evidence arguments, of any offered action, not backed by declared facts."""
        evidence_by_id = {item.evidence_id: item for item in self.evidence}
        arguments: tuple[ActionArgumentResolution, ...] = (
            *self.argument_bindings,
            *(argument for alternative in self.alternative_actions for argument in alternative.offered_arguments()),
        )
        for argument in arguments:
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
            return
        _require_recovery_conditionality(self.conditionality, missing_from_bindings)

    def _reject_alternatives_the_outcome_cannot_carry(self) -> None:
        """Refuse alternatives beside a closed outcome, and any action offered twice."""
        if not self.alternative_actions:
            return
        if self.action is None:
            raise ValueError("alternative recovery actions require a primary recovery action")
        action_ids = (self.action.action_id, *(item.offered_action_id() for item in self.alternative_actions))
        if len(set(action_ids)) != len(action_ids):
            raise ValueError("recovery action identities must be unique across the primary and its alternatives")


__all__ = [
    "PreconditionActionIdentity",
    "PreconditionAlternativeAction",
    "PreconditionEvidence",
    "PreconditionOutcomeInvariant",
]
