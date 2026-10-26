"""In-memory categorisation doors that answer with the operations' own public results.

Each door records the exact request it was given and answers through a handler
that builds the operation's real result model, so every screen is driven by the
same request validation and result invariants the registered operation
publishes. A door can be told to refuse, which it does with a recorded
registered error, or to report a lost session.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel

from .....application.ledger.rule_contracts import (
    LedgerRuleAddProjection,
    LedgerRuleAddRequest,
    LedgerRuleApplyAppliedProjection,
    LedgerRuleApplyMatchProjection,
    LedgerRuleApplyProjection,
    LedgerRuleApplyRequest,
    LedgerRuleListProjection,
    LedgerRuleListRequest,
    LedgerRuleRowProjection,
)
from .....core.errors.hierarchy import RecordedRegisteredError
from .....core.identity.transaction_ids import TransactionId
from .....domain.transactions.classification_rule import LedgerClassificationRule
from .....domain.transactions.enums import BusinessClassification
from ...account import AccountSessionExpiredError

CATEGORISATION_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000d2")
CATEGORISATION_REFUSAL_CODE = "REFUSED_CLI_VALIDATION_BOUNDARY"
CATEGORISATION_REFUSAL_KEY = "errors.refused.refused_cli_validation_boundary"
_CREATED_AT = datetime(2026, 3, 1, tzinfo=UTC)


class MemoryDoor[RequestT: BaseModel, ResultT: BaseModel]:
    """A profile-bound door answering each request through the given handler."""

    def __init__(self, handler: Callable[[RequestT], ResultT]) -> None:
        """Answer every request with ``handler`` until told to refuse or expire."""
        self.handler = handler
        self.requests: list[RequestT] = []
        self.refusing = False
        self.expired = False

    @property
    def profile_id(self) -> UUID:
        """The synthetic profile every request must name."""
        return CATEGORISATION_PROFILE_ID

    async def __call__(self, request: RequestT, /) -> ResultT:
        """Record the request, then refuse, expire or answer it."""
        if request.model_dump().get("profile_id") != CATEGORISATION_PROFILE_ID:
            raise AssertionError("the screen sent a request for another profile")
        self.requests.append(request)
        if self.expired:
            raise AccountSessionExpiredError()
        if self.refusing:
            raise RecordedRegisteredError(CATEGORISATION_REFUSAL_CODE, translated_message=CATEGORISATION_REFUSAL_KEY)
        return self.handler(request)


def synthetic_id(index: int) -> TransactionId:
    """A synthetic 64-character entry identifier."""
    return f"{index:064x}"


@dataclass
class MemoryRuleBook:
    """Rules and a small set of entries the rule doors read and change."""

    rules: list[LedgerClassificationRule] = field(default_factory=list)
    entries: dict[TransactionId, tuple[str, BusinessClassification]] = field(default_factory=dict)

    def list_rules(self, request: LedgerRuleListRequest) -> LedgerRuleListProjection:
        ordered = sorted(self.rules, key=lambda rule: (rule.priority, rule.rule_id))
        return LedgerRuleListProjection(
            profile_id=request.profile_id, rules=tuple(LedgerRuleRowProjection.from_rule(rule) for rule in ordered)
        )

    def add_rule(self, request: LedgerRuleAddRequest) -> LedgerRuleAddProjection:
        if not request.description_pattern.strip():
            return LedgerRuleAddProjection(
                profile_id=request.profile_id,
                outcome="validation_error",
                validation_code="empty_pattern",
                validation_messages=("description pattern must not be empty or whitespace",),
            )
        rule = LedgerClassificationRule.create(
            description_pattern=request.description_pattern,
            classification=request.classification,
            category_id=request.category_id,
            priority=request.priority,
            actor="operator",
        ).model_copy(update={"created_at": _CREATED_AT})
        self.rules.append(rule)
        return LedgerRuleAddProjection(
            profile_id=request.profile_id, outcome="added", rule=LedgerRuleRowProjection.from_rule(rule)
        )

    def _matches(self, reaffirm: bool) -> list[tuple[TransactionId, str, LedgerClassificationRule]]:
        found: list[tuple[TransactionId, str, LedgerClassificationRule]] = []
        for transaction_id, (description, classification) in sorted(self.entries.items()):
            if not reaffirm and classification is not BusinessClassification.NOT_YET_PROCESSED:
                continue
            rule = next(
                (
                    item
                    for item in sorted(self.rules, key=lambda rule: rule.priority)
                    if item.description_pattern.lower() in description.lower()
                ),
                None,
            )
            if rule is not None and rule.classification is not classification:
                found.append((transaction_id, description, rule))
        return found

    def apply_rules(self, request: LedgerRuleApplyRequest) -> LedgerRuleApplyProjection:
        matches = self._matches(request.reaffirm)
        if request.dry_run:
            rows = tuple(
                LedgerRuleApplyMatchProjection(
                    transaction_id=transaction_id,
                    description=description,
                    matched_rule_id=rule.rule_id,
                    classification=rule.classification,
                )
                for transaction_id, description, rule in matches
            )
            return LedgerRuleApplyProjection(
                profile_id=request.profile_id, outcome="dry_run", dry_run=True, would_match=rows, count=len(rows)
            )
        applied: list[LedgerRuleApplyAppliedProjection] = []
        for transaction_id, description, rule in matches:
            self.entries[transaction_id] = (description, rule.classification)
            applied.append(
                LedgerRuleApplyAppliedProjection(
                    transaction_id=transaction_id, matched_rule_id=rule.rule_id, classification=rule.classification
                )
            )
        return LedgerRuleApplyProjection(
            profile_id=request.profile_id,
            outcome="applied",
            rules_evaluated=len(self.rules),
            transactions_scanned=len(self.entries),
            matched=len(applied),
            skipped_already_classified=0,
            no_match=len(self.entries) - len(applied),
            applied=tuple(applied),
            bucket_event_count=len(applied),
        )


__all__ = [
    "CATEGORISATION_PROFILE_ID",
    "CATEGORISATION_REFUSAL_CODE",
    "CATEGORISATION_REFUSAL_KEY",
    "MemoryDoor",
    "MemoryRuleBook",
    "synthetic_id",
]
