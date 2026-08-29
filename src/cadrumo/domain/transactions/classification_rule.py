"""Domain model for a ledger classification rule.

A rule binds a regex description-pattern to a target
:class:`~cadrumo.domain.transactions._enums.BusinessClassification`.
Rule IDs are content-addressed (SHA-256 of the rule's key fields) so
creation is idempotent: adding the same pattern + classification pair
twice produces the same rule_id and the repository overwrites the prior
entry rather than duplicating it.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.hashing import sha256_hex
from ...core.identity import ContentDigest
from ...core.logging import get_logger
from ...core.time import UtcInstant, now
from ._enums import BusinessClassification
from .errors import ClassificationRuleError

_logger = get_logger(__name__)

_RULE_ID_LENGTH: int = 64

RuleDescriptionPattern = Annotated[str, StringConstraints(min_length=1)]
"""The regular expression a rule matches a transaction description against."""

RulePriority = Annotated[int, Field(ge=1)]
"""Resolution order for competing rules; the lower integer wins."""

RuleActor = Annotated[str, StringConstraints(min_length=1)]
"""Who authored the rule, as recorded on it."""



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

    model_config = _STRICT_FROZEN

    rule_id: ContentDigest
    description_pattern: RuleDescriptionPattern
    classification: BusinessClassification
    category_id: str | None = None
    priority: RulePriority = 100
    created_at: UtcInstant
    actor: RuleActor

    @field_validator("description_pattern")
    @classmethod
    def _validate_regex(cls, value: str) -> str:
        try:
            re.compile(value)
        except re.error as exc:
            raise ClassificationRuleError(f"description_pattern is not a valid regex: {exc}") from exc
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

    def matches(self, description: str) -> bool:
        """Return ``True`` when this rule's pattern matches ``description`` (case-insensitive)."""
        return bool(re.search(self.description_pattern, description, re.IGNORECASE))


__all__ = [
    "LedgerClassificationRule",
    "_compute_rule_id",
]
