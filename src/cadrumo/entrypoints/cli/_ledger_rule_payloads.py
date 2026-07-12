"""Typed ``--json`` payload schemas for ledger rule commands.

Every declared payload is an
:class:`OutputSchema` subclass registered with
:func:`register_schema` for the ledger rule
command JSON-contract surface carried by
:class:`SchemaEnvelope` through
:func:`_emit_envelope`. These schemas are the CLI projection of the secure,
profile-local rule engine: persisted :class:`LedgerClassificationRule` records
are listed and added through :mod:`_ledger_rules_cli`, while
:func:`apply_classification_rules` owns live mutation semantics. The parent
:mod:`_ledger_payloads` module re-exports these split schemas so existing ledger
command emitters keep one payload import surface.
"""

from __future__ import annotations

from ._schemas import OutputSchema, register_schema


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

    rule_id: str
    description_pattern: str
    classification: str
    category_id: str | None = None
    priority: int
    actor: str
    created_at: str


@register_schema("ledger.rule.add")
class RuleAddResult(ClassificationRulePayload):
    """JSON envelope for ``cadrumo app ledger rule add``.

    The command persists one
    :class:`LedgerClassificationRule` through
    :class:`LedgerClassificationRuleRepository`; adding
    the same pattern/classification/category tuple is idempotent because the
    rule id is content-addressed.
    """


@register_schema("ledger.rule.list")
class RuleListResult(OutputSchema):
    """JSON envelope for ``cadrumo app ledger rule list``.

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

    transaction_id: str
    description: str
    matched_rule_id: str
    classification: str


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

    transaction_id: str
    matched_rule_id: str
    classification: str


@register_schema("ledger.rule.apply")
class RuleApplyResult(OutputSchema):
    """JSON envelope for ``cadrumo app ledger rule apply``.

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


class LLMProviderAvailabilityPayload(OutputSchema):
    """One subprocess LLM provider's PATH availability.

    Nested in
    :class:`LedgerProvidersResult`
    and mirrors
    :class:`LLMProviderAvailability` from
    :func:`available_llm_providers`. The probe uses PATH lookup only; it does
    not spawn the provider CLI or send transaction data to a cloud service.
    """

    provider: str
    cli_binary: str
    available: bool
    resolved_path: str | None = None


class VisionProviderPayload(OutputSchema):
    """The on-host Ollama vision model's availability.

    Nested in
    :class:`LedgerProvidersResult`
    and carries the
    :class:`DependencyStatus` fields surfaced
    beside subprocess LLM providers, including operator remediation text when
    the local model or service is unavailable.
    """

    service: str
    available: bool
    detail: str = ""
    remediation: str = ""


@register_schema("ledger.providers")
class LedgerProvidersResult(OutputSchema):
    """JSON envelope for ``cadrumo app ledger providers``.

    Reports subprocess cloud-provider CLIs from
    :func:`available_llm_providers` and the on-host Ollama vision model probed
    by :func:`probe_ollama_vision`, so the operator sees every classification
    backend - cloud and local - in one place before running LLM-assisted
    classification.
    """

    providers: list[LLMProviderAvailabilityPayload]
    vision: VisionProviderPayload | None = None


class LlmUsageProviderPayload(OutputSchema):
    """Per-provider LLM usage/cost row.

    Mirrors :class:`LlmUsageProviderMetrics`, aggregated
    from the encrypted usage log. ``calls`` counts every recorded call
    (cache hits included); ``cost_estimate_usd`` is the summed estimate.
    """

    provider: str
    calls: int
    cache_hits: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_estimate_usd: str


class LlmConfidenceProviderPayload(OutputSchema):
    """Per-provider classification-confidence distribution row.

    Mirrors :class:`LlmConfidenceProviderMetrics`,
    aggregated from LLM-classified ledger transactions. ``low_confidence_count``
    is the count below the tunable report threshold; ``high_confidence_count``
    (>= 0.8) and ``medium_confidence_count`` ([0.5, 0.8)) are fixed-floor
    distribution buckets.
    """

    provider: str
    classified_count: int
    low_confidence_count: int
    high_confidence_count: int
    medium_confidence_count: int
    min_confidence: str | None = None
    max_confidence: str | None = None
    mean_confidence: str | None = None


@register_schema("ledger.llm_diagnostics")
class LedgerLlmDiagnosticsResult(OutputSchema):
    """JSON envelope for ``cadrumo app ledger llm-diagnostics``.

    Presents the two existing LLM metric stores in one read-only report: the
    usage/cost log aggregated per provider
    (:class:`LlmUsageProviderMetrics`) and the
    classification-confidence distribution over LLM-classified ledger
    transactions (:class:`LlmConfidenceProviderMetrics`),
    both sourced from
    :func:`build_llm_diagnostics_report`. It reports only accounting metadata,
    never response text or financial content.
    """

    since: str | None = None
    until: str | None = None
    low_confidence_threshold: str
    usage_providers: list[LlmUsageProviderPayload]
    total_calls: int
    total_cache_hits: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_estimate_usd: str
    confidence_providers: list[LlmConfidenceProviderPayload]
    total_classified: int
    total_low_confidence: int
    has_data: bool
