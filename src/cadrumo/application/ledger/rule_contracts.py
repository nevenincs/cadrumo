"""Canonical typed requests and results for ledger classification-rule operations."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.hex import Hex64Str
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.transactions.classification_rule import (
    LedgerClassificationRule,
    RuleActor,
    RuleDescriptionPattern,
    RulePriority,
)
from ...domain.transactions.enums import BusinessClassification

MAX_RULE_VALIDATION_MESSAGES = 32
_VALIDATION_MESSAGE = Annotated[str, Field(min_length=1, max_length=2048)]
RuleValidationMessages = Annotated[tuple[_VALIDATION_MESSAGE, ...], Field(max_length=MAX_RULE_VALIDATION_MESSAGES)]
RuleValidationCode = Literal["empty_pattern", "invalid_pattern", "category", "invalid_command"]


class LedgerRuleRowProjection(BaseModel):
    """Complete stored rule projection used by add, list, and apply matching."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    rule_id: Hex64Str
    description_pattern: RuleDescriptionPattern
    classification: BusinessClassification
    category_id: str | None = None
    priority: RulePriority
    actor: RuleActor
    created_at: datetime

    @model_validator(mode="after")
    def _canonical_rule(self) -> LedgerRuleRowProjection:
        """Validate canonical rule meaning without custom public field schemas."""
        LedgerClassificationRule.model_validate(self.model_dump(mode="python"))
        return self

    @classmethod
    def from_rule(cls, rule: LedgerClassificationRule) -> LedgerRuleRowProjection:
        """Copy every canonical persisted field without changing its meaning."""
        return cls(
            rule_id=str(rule.rule_id),
            description_pattern=rule.description_pattern,
            classification=rule.classification,
            category_id=rule.category_id,
            priority=rule.priority,
            actor=rule.actor,
            created_at=rule.created_at,
        )


class LedgerRuleAddRequest(BaseModel):
    """Private secure-reference input for ``ledger.rule.add``."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    # Keep this as a plain string at the operation boundary so an empty or
    # whitespace-only value reaches the canonical pre-write refusal path and
    # retains the existing CLI's instructive message.
    description_pattern: str
    classification: BusinessClassification
    category_id: str | None = None
    priority: RulePriority = 100
    actor: str | None = None


class LedgerRuleAddProjection(BaseModel):
    """Complete saved rule or bounded validation refusal for rule add."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    outcome: Literal["added", "validation_error"]
    rule: LedgerRuleRowProjection | None = None
    validation_code: RuleValidationCode | None = None
    validation_messages: RuleValidationMessages = ()
    category_example: str | None = None

    @model_validator(mode="after")
    def _complete_outcome(self) -> LedgerRuleAddProjection:
        if self.outcome == "added":
            _validate_rule_add_success(self)
        else:
            _validate_rule_add_refusal(self)
        return self


def _validate_rule_add_success(projection: LedgerRuleAddProjection) -> None:
    if (
        projection.rule is None
        or projection.validation_code is not None
        or projection.validation_messages
        or projection.category_example
    ):
        raise ValueError("added rule projection requires one rule and no refusal details")


def _validate_rule_add_refusal(projection: LedgerRuleAddProjection) -> None:
    if (
        projection.rule is not None
        or projection.validation_code is None
        or not projection.validation_messages
        or (projection.validation_code == "category") != (projection.category_example is not None)
    ):
        raise ValueError("rule add validation projection requires only bounded refusal details")


class LedgerRuleListRequest(BaseModel):
    """Credential-free selector for the active profile's complete rule list."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID


class LedgerRuleListProjection(BaseModel):
    """All stored rules in the repository's canonical evaluation order."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    rules: tuple[LedgerRuleRowProjection, ...]


class LedgerRuleApplyRequest(BaseModel):
    """Private exact-profile rule apply or non-mutating preview request."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    reaffirm: bool = False
    dry_run: bool = False
    actor: str | None = None


class LedgerRuleApplyMatchProjection(BaseModel):
    """One exact dry-run match, including the existing raw description field."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction_id: TransactionId
    description: str
    matched_rule_id: Hex64Str
    classification: BusinessClassification


class LedgerRuleApplyAppliedProjection(BaseModel):
    """One transaction the canonical rule engine reports as applied."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction_id: TransactionId
    matched_rule_id: Hex64Str
    classification: BusinessClassification


class LedgerRuleApplyProjection(BaseModel):
    """Full CLI payload semantics plus the worker-owned profile/effect evidence."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    outcome: Literal["dry_run", "applied", "validation_error"]
    dry_run: Literal[True] | None = None
    would_match: tuple[LedgerRuleApplyMatchProjection, ...] | None = None
    count: NonNegativeInt | None = None
    rules_evaluated: NonNegativeInt | None = None
    transactions_scanned: NonNegativeInt | None = None
    matched: NonNegativeInt | None = None
    skipped_already_classified: NonNegativeInt | None = None
    no_match: NonNegativeInt | None = None
    applied: tuple[LedgerRuleApplyAppliedProjection, ...] | None = None
    bucket_event_count: NonNegativeInt = 0
    validation_code: RuleValidationCode | None = None
    validation_messages: RuleValidationMessages = ()

    @model_validator(mode="after")
    def _complete_outcome(self) -> LedgerRuleApplyProjection:
        if self.outcome == "dry_run":
            _validate_rule_apply_preview(self)
        elif self.outcome == "applied":
            _validate_rule_apply_success(self)
        else:
            _validate_rule_apply_refusal(self)
        return self


def _validate_rule_apply_preview(projection: LedgerRuleApplyProjection) -> None:
    live_fields = (
        projection.rules_evaluated,
        projection.transactions_scanned,
        projection.matched,
        projection.skipped_already_classified,
        projection.no_match,
        projection.applied,
    )
    if (
        projection.dry_run is not True
        or projection.would_match is None
        or projection.count != len(projection.would_match)
        or any(value is not None for value in live_fields)
        or projection.bucket_event_count
        or projection.validation_code is not None
        or projection.validation_messages
    ):
        raise ValueError("dry-run projection requires only a no-effect match preview")


def _validate_rule_apply_success(projection: LedgerRuleApplyProjection) -> None:
    dry_fields = (projection.dry_run, projection.would_match, projection.count)
    live_fields = (
        projection.rules_evaluated,
        projection.transactions_scanned,
        projection.matched,
        projection.skipped_already_classified,
        projection.no_match,
        projection.applied,
    )
    if (
        any(value is not None for value in dry_fields)
        or any(value is None for value in live_fields)
        or projection.matched != len(projection.applied or ())
        or projection.validation_code is not None
        or projection.validation_messages
    ):
        raise ValueError("applied projection requires complete live counts and applied rows")


def _validate_rule_apply_refusal(projection: LedgerRuleApplyProjection) -> None:
    all_fields = (
        projection.dry_run,
        projection.would_match,
        projection.count,
        projection.rules_evaluated,
        projection.transactions_scanned,
        projection.matched,
        projection.skipped_already_classified,
        projection.no_match,
        projection.applied,
    )
    if (
        any(value is not None for value in all_fields)
        or projection.bucket_event_count
        or projection.validation_code is None
        or not projection.validation_messages
    ):
        raise ValueError("rule apply validation projection requires only bounded refusal details")


class LedgerRuleAddExecutionResult(BaseModel):
    """Encrypted add outcome released only through its validated terminal receipt."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: LedgerRuleAddProjection


class LedgerRuleApplyExecutionResult(BaseModel):
    """Encrypted apply outcome, including refusal evidence requiring receipt validation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: LedgerRuleApplyProjection
