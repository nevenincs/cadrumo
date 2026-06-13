"""Typed ``--json`` payload schemas for ledger rule commands.

Every declared payload is an :class:`OutputSchema` subclass registered for
the ledger rule command JSON-contract surface.
"""

from __future__ import annotations

from ._schemas import OutputSchema, register_schema


class ClassificationRulePayload(OutputSchema):
    """One classification-rule row (matches the dict emitted by rule.add / rule.list)."""

    rule_id: str
    description_pattern: str
    classification: str
    category_id: str | None = None
    priority: int
    actor: str
    created_at: str


@register_schema("ledger.rule.add")
class RuleAddResult(ClassificationRulePayload):
    """JSON envelope for ``aeat app ledger rule add``."""


@register_schema("ledger.rule.list")
class RuleListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger rule list``."""

    rules: list[ClassificationRulePayload]


class RuleApplyMatchPayload(OutputSchema):
    """One dry-run match row for ``rule apply --dry-run``."""

    transaction_id: str
    description: str
    matched_rule_id: str
    classification: str


class RuleApplyAppliedPayload(OutputSchema):
    """One live-applied rule row nested in ``ledger rule apply``."""

    transaction_id: str
    matched_rule_id: str
    classification: str


@register_schema("ledger.rule.apply")
class RuleApplyResult(OutputSchema):
    """JSON envelope for ``aeat app ledger rule apply``.

    Covers both the dry-run branch (``dry_run``, ``would_match``,
    ``count``) and the live-apply branch (``rules_evaluated``,
    ``transactions_scanned``, ``matched``, ``skipped_already_classified``,
    ``no_match``, ``applied``). All fields are optional so both branches
    validate cleanly.
    """

    # Dry-run path
    dry_run: bool | None = None
    would_match: list[RuleApplyMatchPayload] | None = None
    count: int | None = None
    # Live-apply path
    rules_evaluated: int | None = None
    transactions_scanned: int | None = None
    matched: int | None = None
    skipped_already_classified: int | None = None
    no_match: int | None = None
    applied: list[RuleApplyAppliedPayload] | None = None


class LLMProviderAvailabilityPayload(OutputSchema):
    """One subprocess LLM provider's PATH availability (nested)."""

    provider: str
    cli_binary: str
    available: bool
    resolved_path: str | None = None


@register_schema("ledger.providers")
class LedgerProvidersResult(OutputSchema):
    """JSON envelope for ``aeat app ledger providers``."""

    providers: list[LLMProviderAvailabilityPayload]
