"""Domain model for a ledger classification rule.

A rule binds a regex description-pattern to a target
:class:`~cadrumo.domain.transactions.enums.BusinessClassification`.
Rule IDs are content-addressed (SHA-256 of the rule's key fields) so
creation is idempotent: adding the same pattern + classification pair
twice produces the same rule_id and the repository overwrites the prior
entry rather than duplicating it.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Final

from pydantic import BaseModel, Field, StringConstraints, field_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.hashing import sha256_hex
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.pattern_search_worker import PATTERN_COMPILE_FAILURES, PATTERN_FLAGS
from ...core.time.clock import now
from ...core.time.utc import UtcInstant
from .enums import RULE_DECIDED_STATES, BusinessClassification, rule_names_category
from .errors import ClassificationRuleError

RuleDescriptionPattern = Annotated[str, StringConstraints(min_length=1)]
"""The regular expression a rule matches a transaction description against."""

RulePriority = Annotated[int, Field(ge=1)]
"""Resolution order for competing rules; the lower integer wins."""

RuleActor = Annotated[str, StringConstraints(min_length=1)]
"""Who authored the rule, as recorded on it."""


RULE_PATTERN_ENTRY_MAX_LENGTH: Final = 2048
"""The longest pattern taken at entry: reading one holds the interpreter lock, here a few tens of milliseconds.

It holds a new pattern only. A stored rule longer than this is still read and still runs.
"""


def description_pattern_error(description_pattern: str) -> Exception | None:
    """Return why the rule engine cannot read a pattern, or ``None`` where it can."""
    try:
        re.compile(description_pattern, PATTERN_FLAGS)
    except PATTERN_COMPILE_FAILURES as exc:
        return exc
    return None


def _compute_rule_id(
    description_pattern: str,
    classification: BusinessClassification,
    category_id: str | None,
) -> str:
    """Return the SHA-256 content-addressed rule id."""
    raw = f"{description_pattern}|{classification.value}|{category_id or ''}"
    return sha256_hex(raw.encode())


class LedgerClassificationRule(BaseModel):
    """A persisted ledger classification rule.

    ``rule_id`` is content-addressed so that persisting the same pattern
    twice is idempotent.  Priority resolution: lower ``priority`` integer
    wins; ties broken by ``created_at`` ascending (earliest rule wins).
    """

    model_config = STRICT_FROZEN_CONFIG

    rule_id: ContentDigest
    description_pattern: RuleDescriptionPattern
    classification: BusinessClassification
    category_id: str | None = None
    priority: RulePriority = 100
    created_at: UtcInstant
    actor: RuleActor

    @field_validator("description_pattern")
    @classmethod
    @pydantic_validation_boundary
    def _validate_regex(cls, value: str) -> str:
        error = description_pattern_error(value)
        if error is not None:
            raise ClassificationRuleError(f"description_pattern is not a valid regex: {error}") from error
        return value

    @classmethod
    def create(
        cls,
        *,
        description_pattern: str,
        classification: BusinessClassification,
        category_id: str | None = None,
        priority: int = 100,
        actor: str,
        created_at: datetime | None = None,
    ) -> LedgerClassificationRule:
        """Construct a :class:`LedgerClassificationRule` with the content-addressed ``rule_id``."""
        rule_id = _compute_rule_id(description_pattern, classification, category_id)
        return cls(
            rule_id=rule_id,
            description_pattern=description_pattern,
            classification=classification,
            category_id=category_id,
            priority=priority,
            created_at=created_at or now(),
            actor=actor,
        )


def require_new_rule_decision(classification: BusinessClassification, category_id: str | None) -> None:
    """Refuse a new rule whose decision no classification write could carry out.

    A Mixed rule names no share, so every row it matches would fail; an exclusion
    would take rows out of every tax aggregation without a person seeing one of
    them; the other dispositions decide nothing. Only a Business write keeps a
    category, so one named with anything else would be dropped from each row. A
    rule already stored stays readable: this asks only of a rule being added.
    """
    if classification not in RULE_DECIDED_STATES:
        raise ClassificationRuleError(f"a rule cannot decide {classification.value}")
    if category_id is not None and not rule_names_category(classification):
        raise ClassificationRuleError(f"a rule deciding {classification.value} cannot name a category")


__all__ = [
    "RULE_PATTERN_ENTRY_MAX_LENGTH",
    "LedgerClassificationRule",
    "_compute_rule_id",
    "description_pattern_error",
    "require_new_rule_decision",
]
