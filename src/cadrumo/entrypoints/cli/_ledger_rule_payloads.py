"""Typed ``--json`` payload schemas for ledger rule commands.

Every declared payload is an
:class:`OutputSchema` subclass referenced by
production-authored CommandSpec as deferred public schema targets for the ledger rule
command JSON-contract surface carried by
:class:`SchemaEnvelope` through
:func:`emit_envelope`. These schemas are the CLI projection of the secure,
profile-local rule engine: persisted :class:`LedgerClassificationRule` records
are listed and added through :mod:`_ledger_rules_cli`, while
:func:`apply_classification_rules` owns live mutation semantics. The parent
:mod:`_ledger_payloads` module re-exports these split schemas so existing ledger
command emitters keep one payload import surface.
"""

from __future__ import annotations

from pydantic import NonNegativeInt, model_validator

from ...application.ledger.llm_diagnostics import LlmProviderName
from ...core.hex import Hex64Str
from ...core.identity import TransactionId
from ...core.json_contract import OutputSchema
from ...core.time.utc import UtcInstant
from ...domain.transactions.classification_rule import (
    LedgerClassificationRule,
    RuleActor,
    RuleDescriptionPattern,
    RulePriority,
)
from ...domain.transactions.enums import BusinessClassification
from ._decimal_wire import DecimalWireText


class ClassificationRulePayload(OutputSchema):
    """One persisted ledger classification rule row.

    Mirrors :class:`LedgerClassificationRule` as
    emitted by
    :class:`RuleAddResult` and
    nested in
    :class:`RuleListResult`.
    ``rule_id`` is the content-addressed id, ``description_pattern`` is the
    regex evaluated against transaction descriptions, and lower ``priority``
    values run before higher ones.
    """

    rule_id: Hex64Str
    description_pattern: RuleDescriptionPattern
    classification: BusinessClassification
    category_id: str | None = None
    priority: RulePriority
    actor: RuleActor
    created_at: UtcInstant

    @model_validator(mode="after")
    def _validate_canonical_rule(self) -> ClassificationRulePayload:
        LedgerClassificationRule(
            rule_id=self.rule_id,
            description_pattern=self.description_pattern,
            classification=self.classification,
            category_id=self.category_id,
            priority=self.priority,
            created_at=self.created_at,
            actor=self.actor,
        )
        return self


class RuleAddResult(ClassificationRulePayload):
    """JSON envelope for ``aeat app ledger rule add``.

    The command persists one
    :class:`LedgerClassificationRule` through
    :class:`LedgerClassificationRuleRepository`; adding
    the same pattern/classification/category tuple is idempotent because the
    rule id is content-addressed.
    """


class RuleListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger rule list``.

    Rows are returned in the application evaluation order exposed by
    :meth:`LedgerClassificationRuleRepository.list_rules`: priority ascending,
    then creation time ascending for ties.
    """

    rules: list[ClassificationRulePayload]


class RuleApplyMatchPayload(OutputSchema):
    """One non-mutating preview row for ``ledger rule apply --dry-run``.

    The row reports the first rule that would classify the transaction if the
    operator re-ran without ``--dry-run``. It previews the same priority-ordered
    :class:`LedgerClassificationRule` match selection
    as :func:`apply_classification_rules`, but remains evidence only: no
    transaction state or bucket event is written for these :class:`RuleApplyResult`
    rows.
    """

    transaction_id: TransactionId
    description: str
    matched_rule_id: Hex64Str
    classification: BusinessClassification


class RuleApplyAppliedPayload(OutputSchema):
    """One transaction classified by a live ``ledger rule apply`` pass.

    Nested in
    :class:`RuleApplyResult` and
    mirrors
    :class:`ApplyRulesAppliedRow`: the transaction id,
    the matched content-addressed rule id, and the classification persisted
    through the shared manual transaction mutation path with ``rule:<rule_id>``
    provenance.
    """

    transaction_id: TransactionId
    matched_rule_id: Hex64Str
    classification: BusinessClassification


class RuleApplyResult(OutputSchema):
    """JSON envelope for ``aeat app ledger rule apply``.

    Covers both the dry-run branch (``dry_run``, ``would_match``,
    ``count``) and the live-apply branch (``rules_evaluated``,
    ``transactions_scanned``, ``matched``, ``skipped_already_classified``,
    ``no_match``, ``applied``).  Live counts mirror
    :class:`ApplyRulesResult`; dry-run rows preview the
    same first-match rule selection without writing transaction state.  Rows
    already classified by an operator are skipped unless the command is run with
    the explicit ``--reaffirm`` consent flag.
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


class LlmUsageCostProviderPayload(OutputSchema):
    """Per-provider LLM usage/cost row.

    Mirrors :class:`LlmUsageCostProviderMetrics`, aggregated
    from the encrypted usage log. ``calls`` counts every recorded call
    (cache hits included); ``cost_estimate_usd`` is the summed estimate.
    """

    provider: LlmProviderName
    calls: NonNegativeInt
    cache_hits: NonNegativeInt
    # unpriced_calls is unbounded here: the canonical LlmUsageCostProviderMetrics
    # (application/ledger/llm_diagnostics.py) now declares `Field(default=0, ge=0)`
    # itself, and this payload is built only from an already-validated instance of
    # it (entrypoints/cli/_ledger_rule_payloads.py's sole producer dumps a real
    # LlmUsageCostProviderMetrics), so restating the bound here would be redundant.
    unpriced_calls: int = 0
    input_tokens: NonNegativeInt
    output_tokens: NonNegativeInt
    total_tokens: NonNegativeInt
    # The canonical LlmUsageCostProviderMetrics declares this a plain Decimal with
    # no bound, so the transport asserts the decimal grammar only.
    cost_estimate_usd: DecimalWireText | None


class LlmConfidenceProviderPayload(OutputSchema):
    """Per-provider classification-confidence distribution row.

    Mirrors :class:`LlmConfidenceProviderMetrics`,
    aggregated from LLM-classified ledger transactions. ``low_confidence_count``
    is the count below the tunable report threshold; ``high_confidence_count``
    (>= 0.8) and ``medium_confidence_count`` ([0.5, 0.8)) are fixed-floor
    distribution buckets.
    """

    provider: LlmProviderName
    classified_count: NonNegativeInt
    low_confidence_count: NonNegativeInt
    high_confidence_count: NonNegativeInt
    medium_confidence_count: NonNegativeInt
    # Unbounded on purpose: the canonical LlmConfidenceProviderMetrics carries
    # these as `Decimal | None` with no range, so the transport mirrors that
    # rather than inventing a [0, 1] bound the contract does not state.
    min_confidence: DecimalWireText | None = None
    max_confidence: DecimalWireText | None = None
    mean_confidence: DecimalWireText | None = None


class LedgerLlmDiagnosticsResult(OutputSchema):
    """JSON envelope for ``aeat app ledger llm-diagnostics``.

    Presents the two existing LLM metric stores in one read-only report: the
    usage/cost log aggregated per provider
    (:class:`LlmUsageCostProviderMetrics`) and the
    classification-confidence distribution over LLM-classified ledger
    transactions (:class:`LlmConfidenceProviderMetrics`),
    both sourced from
    :func:`build_llm_diagnostics_report`. It reports only accounting metadata,
    never response text or financial content.
    """

    since: str | None = None
    until: str | None = None
    low_confidence_threshold: DecimalWireText
    usage_providers: list[LlmUsageCostProviderPayload]
    total_calls: NonNegativeInt
    total_cache_hits: NonNegativeInt
    total_input_tokens: NonNegativeInt
    total_output_tokens: NonNegativeInt
    total_cost_estimate_usd: DecimalWireText | None
    # Unbounded for the same reason as LlmUsageCostProviderPayload.unpriced_calls
    # above: the canonical LlmDiagnosticsReport.total_unpriced_calls now carries
    # `Field(default=0, ge=0)` itself, and this payload's sole producer
    # (entrypoints/cli/_ledger_read_cli.py `_llm_diagnostics_result`) builds it
    # from an already-validated `LlmDiagnosticsReport` instance.
    total_unpriced_calls: int = 0
    confidence_providers: list[LlmConfidenceProviderPayload]
    total_classified: NonNegativeInt
    total_low_confidence: NonNegativeInt
    has_data: bool
