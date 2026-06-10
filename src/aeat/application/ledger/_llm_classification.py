"""LLM-assisted ledger classification: suggest / apply / provider availability.

Wires the existing :class:`aeat.domain.transactions.LLMClassifier` engine into
the operator suggest -> review -> confirm / override / reject loop without
rebuilding the classifier. The contract is deliberately thin:

* :func:`suggest_llm_classification` loads one transaction, runs the
  (injected, default-resolved) classifier with the category-enabled prompt
  spec, and returns a typed :class:`LLMClassificationSuggestion` **without
  persisting anything**. Rejecting a suggestion is simply not applying it.
* :func:`apply_llm_classification` persists an accepted suggestion through the
  established classification write (:func:`aeat.domain.transactions.set_classification`),
  stamping ``classified_by`` with the classifier's ``decided_by`` (``llm:<model>``
  provenance, distinct from manual / ``rule:``) and recording the model's
  ``confidence`` and ``reason``. The accepted decision is appended to the
  profile audit trail through a :class:`BucketEventHistoryRepository` as a
  ``ledger.transaction.classified`` event.
* :func:`available_llm_providers` reports which subprocess providers have a
  usable CLI on ``PATH`` so the CLI can refuse instructively rather than crash.

Hallucination containment stays inside the engine: the classifier's
``classify`` runs the allow-list-guarded
:func:`aeat.domain.transactions.parse_response`, so an out-of-allow-list
value is rejected before it ever reaches this module.

**Hard constraint (MVP).** This path persists only the non-regulated
``business_classification`` and optional expense ``category``. It never sets
or persists a regulated tax value (``taxable_base``, ``iva_rate``,
``iva_amount``, ``iva_category``, ``irpf_category``) — those are deferred to a
separate, legally-grounded ADR.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from ...core._models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.logging import get_logger
from ...core.time import now
from ...core.time._utc import coerce_utc_aware
from ...domain.buckets import (
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
)
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
from ...domain.categories import SpendingCategory
from ...domain.transactions import (
    BusinessClassification,
    LLMClassifier,
    TransactionLifecycleState,
    TransactionNotFoundError,
    TransactionValidationError,
    prompt_spec_with_every_spending_category,
    resolve_classifier,
    set_classification,
)
from ...domain.transactions._protocols import TransactionCatalogueRepositoryProtocol
from ._actions_common import (
    _build_bucket_event,
    _result,
    _save_transaction_catalogue_and_events,
    _transaction_repository,
)
from ._models import ManualLedgerTransactionResult

_logger = get_logger(__name__)

_BUCKET_EVENT_PAYLOAD_VERSION = 1


class LLMProvider(StrEnum):
    """Subprocess LLM provider names accepted by the classify surface.

    Each value names a local CLI (``claude`` / ``gemini`` / ``codex``) the
    :class:`aeat.domain.transactions.SubprocessLLMClassifier` shells out to.
    """

    CLAUDE = "claude"
    GEMINI = "gemini"
    CODEX = "codex"


# The CLI binary each subprocess provider shells out to. Used by
# :func:`available_llm_providers` to probe PATH without spawning the process.
_PROVIDER_CLI_BINARY: dict[LLMProvider, str] = {
    LLMProvider.CLAUDE: "claude",
    LLMProvider.GEMINI: "gemini",
    LLMProvider.CODEX: "codex",
}


class LLMClassificationSuggestion(BaseModel):
    """One LLM classification suggestion for a transaction, not yet persisted.

    Carries the decision the model proposed plus the provenance string that
    will be stamped as ``classified_by`` if the operator applies it. Produced
    by :func:`suggest_llm_classification`; consumed for review and, on accept,
    by :func:`apply_llm_classification`.
    """

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1)
    provider: LLMProvider
    provenance: str = Field(min_length=1)
    classification: BusinessClassification
    category: SpendingCategory | None = None
    confidence: Decimal
    reason: str = Field(min_length=1)


class LLMProviderAvailability(BaseModel):
    """Whether one subprocess LLM provider has a usable CLI on ``PATH``."""

    model_config = _STRICT_FROZEN

    provider: LLMProvider
    cli_binary: str = Field(min_length=1)
    available: bool
    resolved_path: str | None = None


def available_llm_providers() -> tuple[LLMProviderAvailability, ...]:
    """Report which subprocess LLM providers are usable on this host.

    Probes ``PATH`` for each provider's CLI binary with :func:`shutil.which`
    (no process is spawned). The CLI surfaces this so an operator can discover
    which providers are installed before classifying.

    Returns:
        One :class:`LLMProviderAvailability` per :class:`LLMProvider`, ordered
        by enum declaration.
    """
    listings: list[LLMProviderAvailability] = []
    for provider in LLMProvider:
        binary = _PROVIDER_CLI_BINARY[provider]
        resolved = shutil.which(binary)
        listings.append(
            LLMProviderAvailability(
                provider=provider,
                cli_binary=binary,
                available=resolved is not None,
                resolved_path=resolved,
            )
        )
    return tuple(listings)


def is_llm_provider_available(provider: LLMProvider) -> bool:
    """Return whether ``provider``'s CLI binary is resolvable on ``PATH``."""
    return shutil.which(_PROVIDER_CLI_BINARY[provider]) is not None


def _resolve_default_classifier(provider: LLMProvider) -> LLMClassifier:
    """Resolve the production classifier for ``provider`` with the category prompt.

    Builds the classifier with
    :func:`aeat.domain.transactions.prompt_spec_with_every_spending_category`
    so the model also suggests an expense :class:`SpendingCategory`, and keeps
    the allow-list-guarded ``parse_response`` path intact.
    """
    return resolve_classifier(provider.value, spec=prompt_spec_with_every_spending_category())


def suggest_llm_classification(
    *,
    bucket_id: str,
    transaction_id: str,
    provider: LLMProvider,
    classifier: LLMClassifier | None = None,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
) -> LLMClassificationSuggestion:
    """Run the LLM classifier for one transaction and return a suggestion.

    Loads the transaction, runs the injected classifier (default-resolved from
    ``provider`` with the category-enabled prompt spec), and returns the typed
    suggestion. **Persists nothing** — this is the suggest step of the
    suggest / review / confirm / reject loop.

    Args:
        bucket_id: Active profile bucket id.
        transaction_id: Stable id of the transaction to classify.
        provider: Subprocess provider to resolve when ``classifier`` is None.
        classifier: Injected classifier (dependency injection for tests). When
            None, resolved via :func:`resolve_classifier` for ``provider``.
        transaction_repository: Injected catalogue repository.

    Returns:
        A :class:`LLMClassificationSuggestion`.

    Raises:
        TransactionNotFoundError: When the transaction id is unknown.
        LLMClassifierError: When the classifier fails (e.g. provider CLI
            unavailable, hallucinated out-of-allow-list value).
    """
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    transaction = repository.load().get(transaction_id)
    if transaction is None:
        raise TransactionNotFoundError(f"transaction not found: {transaction_id}")
    resolved_classifier = classifier if classifier is not None else _resolve_default_classifier(provider)
    response = resolved_classifier.classify(transaction)
    _logger.info(
        "llm suggest: transaction=%s provider=%s classification=%s confidence=%s",
        transaction_id,
        provider.value,
        response.classification.value,
        response.confidence,
    )
    return LLMClassificationSuggestion(
        transaction_id=transaction_id,
        provider=provider,
        provenance=resolved_classifier.decided_by,
        classification=response.classification,
        category=response.category,
        confidence=response.confidence,
        reason=response.reason,
    )


def apply_llm_classification(
    suggestion: LLMClassificationSuggestion,
    *,
    bucket_id: str,
    business_pct: Decimal | None = None,
    actor: str = "operator",
    source_command: str = "aeat app ledger classify --llm",
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
) -> ManualLedgerTransactionResult:
    """Persist an accepted LLM suggestion with ``llm:`` provenance.

    Writes the decision through :func:`aeat.domain.transactions.set_classification`,
    stamping ``classified_by`` with the suggestion's ``provenance`` (the
    classifier's ``decided_by``, e.g. ``llm:<model>``) and recording the
    model's ``confidence`` and ``reason``. Persists the catalogue and emits a
    :attr:`BucketEventType.LEDGER_TRANSACTION_CLASSIFIED` event atomically.

    The MVP persists only the non-regulated ``business_classification`` and
    optional expense ``category``. It never sets a regulated tax value.

    A ``MIXED`` suggestion requires an explicit ``business_pct`` (the LLM does
    not produce one); apply refuses instructively when it is absent. The
    expense ``category`` is recorded only for ``BUSINESS`` / ``MIXED``
    classifications.

    Args:
        suggestion: The accepted :class:`LLMClassificationSuggestion`.
        bucket_id: Active profile bucket id.
        business_pct: Required when ``suggestion.classification`` is ``MIXED``.
        actor: Operator identity for the audit event.
        source_command: Source-command label for the audit event.
        transaction_repository: Injected catalogue repository.
        bucket_event_repository: Injected audit-event repository.
        occurred_at: Override clock for deterministic tests.

    Returns:
        A :class:`ManualLedgerTransactionResult` reflecting the persisted decision.

    Raises:
        TransactionNotFoundError: When the transaction id is unknown.
        TransactionValidationError: When the transaction is not ACTIVE or a
            ``MIXED`` suggestion is applied without a ``business_pct``.
    """
    classification = suggestion.classification
    if classification is BusinessClassification.MIXED and business_pct is None:
        raise TransactionValidationError(
            "applying a MIXED LLM suggestion requires --business-pct; "
            "the LLM proposes the split direction but not the business-use percentage",
            context={"transaction_id": suggestion.transaction_id},
        )
    if classification is not BusinessClassification.MIXED and business_pct is not None:
        raise TransactionValidationError(
            "--business-pct only applies to a MIXED classification",
            context={"transaction_id": suggestion.transaction_id},
        )
    occurred = coerce_utc_aware(occurred_at or now())
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    _event_repo_arg = bucket_event_repository or BucketEventHistoryRepository()
    assert isinstance(_event_repo_arg, BucketEventHistoryRepository), (
        "apply_llm_classification requires a concrete BucketEventHistoryRepository "
        "(to_secure_object_write is not on the protocol)"
    )
    event_repository = _event_repo_arg
    catalogue = repository.load()
    current = catalogue.get(suggestion.transaction_id)
    if current is None:
        raise TransactionNotFoundError(f"transaction not found: {suggestion.transaction_id}")
    if current.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        raise TransactionValidationError(
            "only active ledger transactions can be classified; archived, stashed, and split-parent rows are immutable",
            context={
                "transaction_id": suggestion.transaction_id,
                "lifecycle_state": current.lifecycle_state.value,
            },
        )
    category_id: str | None = None
    if classification in {BusinessClassification.BUSINESS, BusinessClassification.MIXED}:
        category_id = suggestion.category.value if suggestion.category is not None else None
    updated_catalogue = set_classification(
        catalogue,
        suggestion.transaction_id,
        classification=classification,
        business_pct=business_pct,
        category_id=category_id,
        classified_by=suggestion.provenance,
        reason=suggestion.reason,
        confidence=suggestion.confidence,
    )
    updated_transaction = updated_catalogue.get(suggestion.transaction_id)
    assert updated_transaction is not None  # set_classification preserves the id
    event = _build_bucket_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.LEDGER_TRANSACTION_CLASSIFIED,
        occurred_at=occurred,
        actor=actor,
        object_type=BucketEventObjectType.LEDGER_TRANSACTION,
        object_id=suggestion.transaction_id,
        payload={
            "source_command": source_command,
            "classification": classification.value,
            "category_id": category_id or "",
            "classified_by": suggestion.provenance,
            "provider": suggestion.provider.value,
            "confidence": format(suggestion.confidence, "f"),
            "mutation_kind": "llm_classification",
        },
    )
    _save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=event_repository,
        catalogue=updated_catalogue,
        events=(event,),
    )
    _logger.info(
        "llm apply: transaction=%s classified_by=%s classification=%s",
        suggestion.transaction_id,
        suggestion.provenance,
        classification.value,
    )
    return _result(bucket_id, updated_transaction, (event.event_id,))


__all__ = [
    "LLMClassificationSuggestion",
    "LLMProvider",
    "LLMProviderAvailability",
    "apply_llm_classification",
    "available_llm_providers",
    "is_llm_provider_available",
    "suggest_llm_classification",
]
