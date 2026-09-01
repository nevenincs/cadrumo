"""LLM usage, cost, and classification-confidence diagnostics aggregation.

Folds the two metric stores the system already persists into one typed,
operator-facing report:

* the encrypted LLM usage log written by
  :class:`~adapters.outbound.llm.UsageRecorder` (per call: provider,
  model, input/output tokens, estimated cost, cache-hit flag); and
* the classification confidence stamped on each ledger
  :class:`~domain.transactions.Transaction` whose active decision came
  from an LLM classifier (``classified_by`` shaped ``llm:<provider>:<model>``
  with a ``classification_confidence`` in ``[0, 1]``), loaded from the active
  bucket's :class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository`
  when callers do not inject transactions directly.

No new tracking is introduced here: every figure is aggregated from records
already on disk. The usage store and the classification store use distinct
provider namespaces (the completion adapter's :class:`LLMProvider` versus the
subprocess classifier provenance), so the report presents them as two parallel
sections rather than a lossy cross-namespace join.

The report reads only accounting metadata (token counts, cost, confidence
scores, provider labels); it never surfaces the persisted response text or any
financial content, honouring ``sensitive-financial-data-secure-storage-only``.

See Also:
    :func:`build_llm_diagnostics_report`:
        Public aggregator that folds the usage log and ledger confidence rows.
    :class:`~adapters.outbound.llm.UsageRecorder`:
        Storage boundary for provider/token/cost accounting records.
    :class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository`:
        Bucket-scoped ledger catalogue reader used for confidence diagnostics.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, StringConstraints

from ...adapters.outbound.llm.usage import UsageRecorder
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core.bucket_pointer import resolve_active_bucket_id
from ...domain.transactions.models import Transaction
from ...llm.models import UsageRecord

__all__ = [
    "DEFAULT_LOW_CONFIDENCE_THRESHOLD",
    "LlmConfidenceProviderMetrics",
    "LlmDiagnosticsReport",
    "LlmUsageCostProviderMetrics",
    "build_llm_diagnostics_report",
]


#: Default confidence floor below which an LLM classification is reported as
#: low-confidence. Operator-facing display threshold, overridable per call.
DEFAULT_LOW_CONFIDENCE_THRESHOLD = Decimal("0.5")

#: Fixed distribution-bucket floors. The high/medium/low buckets partition every
#: classified decision independently of the tunable low-confidence threshold, so
#: the distribution stays stable while ``low_confidence_count`` tracks the
#: operator's chosen floor.
_HIGH_CONFIDENCE_FLOOR = Decimal("0.8")
_MEDIUM_CONFIDENCE_FLOOR = Decimal("0.5")

_LLM_PROVENANCE_PREFIX = "llm:"
_MEAN_QUANTUM = Decimal("0.0001")


LlmProviderName = Annotated[str, StringConstraints(min_length=1)]
"""The LLM provider a diagnostics row is attributed to."""

#: Deliberately NOT the canonical ``STRICT_FROZEN_CONFIG``: the records below are
#: ``RootModel`` subclasses, and pydantic refuses ``extra`` on a root model
#: outright -- ``PydanticUserError: RootModel does not support setting
#: model_config['extra']``. The canonical config carries ``extra="forbid"``, so it
#: cannot be applied here at all. This is a constraint-shape divergence, not a
#: weaker config nobody chose.
_STRICT_FROZEN = ConfigDict(strict=True, frozen=True)


class LlmUsageCostProviderMetrics(BaseModel):
    """Per-provider aggregate of the LLM usage/cost log.

    Aggregated from :class:`~llm.UsageRecord` rows for a
    single :attr:`provider`. ``calls`` counts every recorded call (cache hits
    included); ``cache_hits`` counts the subset served from the local cache.
    """

    model_config = _STRICT_FROZEN

    provider: LlmProviderName
    calls: NonNegativeInt
    cache_hits: NonNegativeInt
    input_tokens: NonNegativeInt
    output_tokens: NonNegativeInt
    total_tokens: NonNegativeInt
    cost_estimate_usd: Decimal | None
    unpriced_calls: int = Field(default=0, ge=0)


class LlmConfidenceProviderMetrics(BaseModel):
    """Per-provider confidence distribution over LLM-classified transactions.

    Aggregated from the active ledger catalogue's transactions whose
    ``classified_by`` carries an ``llm:`` provenance and a non-null
    ``classification_confidence``. ``low_confidence_count`` is the number of
    those decisions below the report's tunable threshold.
    ``high_confidence_count`` (``>= 0.8``) and ``medium_confidence_count``
    (``[0.5, 0.8)``) are fixed-floor distribution buckets; the remaining
    decisions fall below ``0.5``.
    """

    model_config = _STRICT_FROZEN

    provider: LlmProviderName
    classified_count: NonNegativeInt
    low_confidence_count: NonNegativeInt
    high_confidence_count: NonNegativeInt
    medium_confidence_count: NonNegativeInt
    min_confidence: Decimal | None = None
    max_confidence: Decimal | None = None
    mean_confidence: Decimal | None = None


class LlmDiagnosticsReport(BaseModel):
    """Typed LLM usage / cost / confidence diagnostics report.

    Produced by :func:`build_llm_diagnostics_report`. The usage section folds
    the encrypted usage log; the confidence section folds the classification
    confidence stamped on ledger transactions. :attr:`has_data` is ``False``
    when neither store carries any LLM activity, so callers can print an
    instructive empty message.
    """

    model_config = _STRICT_FROZEN

    since: date | None = None
    until: date | None = None
    low_confidence_threshold: Decimal
    usage_providers: tuple[LlmUsageCostProviderMetrics, ...] = ()
    total_calls: int = Field(default=0, ge=0)
    total_cache_hits: int = Field(default=0, ge=0)
    total_input_tokens: int = Field(default=0, ge=0)
    total_output_tokens: int = Field(default=0, ge=0)
    total_cost_estimate_usd: Decimal | None = Decimal("0")
    total_unpriced_calls: int = Field(default=0, ge=0)
    confidence_providers: tuple[LlmConfidenceProviderMetrics, ...] = ()
    total_classified: int = Field(default=0, ge=0)
    total_low_confidence: int = Field(default=0, ge=0)

    @property
    def has_data(self) -> bool:
        """Return ``True`` when either metric store carried LLM activity."""
        return bool(self.usage_providers) or bool(self.confidence_providers)


def build_llm_diagnostics_report(
    *,
    since: date | None = None,
    until: date | None = None,
    low_confidence_threshold: Decimal = DEFAULT_LOW_CONFIDENCE_THRESHOLD,
    usage_recorder: UsageRecorder | None = None,
    bucket_id: str | None = None,
    transactions: Iterable[Transaction] | None = None,
) -> LlmDiagnosticsReport:
    """Aggregate the existing usage and confidence metric stores into a report.

    Args:
        since: Inclusive lower usage-record date bound, or ``None``.
        until: Inclusive upper usage-record date bound, or ``None``.
        low_confidence_threshold: Confidence floor below which a classification
            counts as low-confidence.
        usage_recorder: Injected recorder; defaults to the active-bucket
            :class:`~adapters.outbound.llm.UsageRecorder`.
        bucket_id: Ledger bucket whose
            :class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository`
            supplies confidence rows; defaults to the active bucket. Ignored
            when ``transactions`` is supplied.
        transactions: Injected transaction iterable; when ``None`` the active
            (or ``bucket_id``) ledger catalogue is loaded.

    Returns:
        The populated :class:`LlmDiagnosticsReport`.
    """
    recorder = usage_recorder or UsageRecorder()
    usage_records = recorder.load_records(since=since, until=until)
    usage_providers = _aggregate_usage(usage_records)

    resolved_transactions = tuple(transactions) if transactions is not None else _load_bucket_transactions(bucket_id)
    confidence_providers = _aggregate_confidence(resolved_transactions, low_confidence_threshold)

    return LlmDiagnosticsReport(
        since=since,
        until=until,
        low_confidence_threshold=low_confidence_threshold,
        usage_providers=usage_providers,
        total_calls=sum(row.calls for row in usage_providers),
        total_cache_hits=sum(row.cache_hits for row in usage_providers),
        total_input_tokens=sum(row.input_tokens for row in usage_providers),
        total_output_tokens=sum(row.output_tokens for row in usage_providers),
        total_cost_estimate_usd=(
            None
            if any(row.cost_estimate_usd is None for row in usage_providers)
            else sum((row.cost_estimate_usd or Decimal("0") for row in usage_providers), start=Decimal("0"))
        ),
        total_unpriced_calls=sum(row.unpriced_calls for row in usage_providers),
        confidence_providers=confidence_providers,
        total_classified=sum(row.classified_count for row in confidence_providers),
        total_low_confidence=sum(row.low_confidence_count for row in confidence_providers),
    )


def _load_bucket_transactions(bucket_id: str | None) -> tuple[Transaction, ...]:
    """Load the target bucket's transactions, or empty when no bucket is active."""
    resolved = bucket_id or resolve_active_bucket_id()
    if resolved is None:
        return ()
    catalogue = TransactionCatalogueRepository(bucket_id=resolved).load()
    return tuple(catalogue.values())


def _aggregate_usage(records: Sequence[UsageRecord]) -> tuple[LlmUsageCostProviderMetrics, ...]:
    """Fold usage records into one metric row per provider, provider-sorted."""
    calls: dict[str, int] = {}
    cache_hits: dict[str, int] = {}
    input_tokens: dict[str, int] = {}
    output_tokens: dict[str, int] = {}
    cost: dict[str, Decimal] = {}
    # A provider with ANY unpriced record reports no cost at all, rather than
    # the sum of the rows that happened to be priced. Skipping the unpriced ones
    # would hand the operator a smaller number wearing the shape of a total.
    unpriced: dict[str, int] = {}
    for record in records:
        provider = record.provider.value
        calls[provider] = calls.get(provider, 0) + 1
        cache_hits[provider] = cache_hits.get(provider, 0) + (1 if record.cache_hit else 0)
        input_tokens[provider] = input_tokens.get(provider, 0) + record.input_tokens
        output_tokens[provider] = output_tokens.get(provider, 0) + record.output_tokens
        if record.cost_estimate_usd is None:
            unpriced[provider] = unpriced.get(provider, 0) + 1
        else:
            cost[provider] = cost.get(provider, Decimal("0")) + record.cost_estimate_usd
    return tuple(
        LlmUsageCostProviderMetrics(
            provider=provider,
            calls=calls[provider],
            cache_hits=cache_hits[provider],
            input_tokens=input_tokens[provider],
            output_tokens=output_tokens[provider],
            total_tokens=input_tokens[provider] + output_tokens[provider],
            cost_estimate_usd=None if unpriced.get(provider) else cost.get(provider, Decimal("0")),
            unpriced_calls=unpriced.get(provider, 0),
        )
        for provider in sorted(calls)
    )


def _aggregate_confidence(
    transactions: Iterable[Transaction],
    threshold: Decimal,
) -> tuple[LlmConfidenceProviderMetrics, ...]:
    """Fold LLM-classified transactions into one confidence row per provider."""
    scores: dict[str, list[Decimal]] = {}
    for transaction in transactions:
        classified_by = transaction.classified_by
        confidence = transaction.classification_confidence
        if confidence is None or not classified_by.startswith(_LLM_PROVENANCE_PREFIX):
            continue
        provider = _confidence_provider(classified_by)
        scores.setdefault(provider, []).append(confidence)
    return tuple(_confidence_row(provider, scores[provider], threshold) for provider in sorted(scores))


def _confidence_row(
    provider: str,
    values: list[Decimal],
    threshold: Decimal,
) -> LlmConfidenceProviderMetrics:
    """Build one provider's confidence-distribution row from its scores.

    ``low_confidence_count`` tracks the tunable ``threshold``; the fixed
    high/medium/low buckets partition every score independently of it.
    """
    low_confidence = sum(1 for value in values if value < threshold)
    high = sum(1 for value in values if value >= _HIGH_CONFIDENCE_FLOOR)
    medium = sum(1 for value in values if _MEDIUM_CONFIDENCE_FLOOR <= value < _HIGH_CONFIDENCE_FLOOR)
    mean = (sum(values, start=Decimal("0")) / Decimal(len(values))).quantize(_MEAN_QUANTUM)
    return LlmConfidenceProviderMetrics(
        provider=provider,
        classified_count=len(values),
        low_confidence_count=low_confidence,
        high_confidence_count=high,
        medium_confidence_count=medium,
        min_confidence=min(values),
        max_confidence=max(values),
        mean_confidence=mean,
    )


def _confidence_provider(classified_by: str) -> str:
    """Extract the provider label from an ``llm:<provider>:<model>`` provenance."""
    remainder = classified_by.removeprefix(_LLM_PROVENANCE_PREFIX)
    provider, _, _ = remainder.partition(":")
    return provider.strip() or "unknown"
