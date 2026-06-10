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

**Stage-1 constraint.** :func:`suggest_llm_classification` /
:func:`apply_llm_classification` persist only the non-regulated
``business_classification`` and optional expense ``category``; they never set a
regulated tax value.

**Stage-2 saturation.** :func:`saturate_llm_classification` /
:func:`apply_saturated_llm_classification` additionally persist the
model-selected ``iva_category`` and the system-DERIVED ``taxable_base`` /
``iva_rate`` / ``iva_amount``. The model still never emits a number — the rate
is looked up from the registry and the base and amount are derived with
``round_to_cents`` (see ``2026-06-04-llm-ledger-classification-adr``).
``irpf_category`` remains operator-only.
"""

from __future__ import annotations

import shutil
from datetime import date, datetime
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
from ...domain.iva import IvaCategory, resolve_category_rate, split_gross_at_rate
from ...domain.transactions import (
    BusinessClassification,
    LLMClassifier,
    TransactionLifecycleState,
    TransactionNotFoundError,
    TransactionValidationError,
    prompt_spec_with_every_spending_category,
    prompt_spec_with_saturation_fields,
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
from ._actions_manual import update_manual_transaction_fields
from ._models import ManualLedgerTransactionPatch, ManualLedgerTransactionResult

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


# ── stage-2 saturation: grounded rich tax metadata ────────────────


class LLMSaturatedSuggestion(BaseModel):
    """A saturated LLM suggestion: business decision + grounded tax substrate.

    Extends the stage-1 decision (classification, expense category) with the
    IVA situation the model SELECTED and the regulated euro figures the system
    DERIVED from the registry rate — never numbers the model emitted. Each
    field carries its origin so the operator reviewing the preview can see
    which values are model selections (``llm:``) and which are system
    derivations (``derived:``).

    When the selected :attr:`iva_category` has no simple derivable Spanish
    domestic rate (intra-community, reverse-charge, export, import, recargo,
    régimen simplificado, not-subject) the numbers are left unset and
    :attr:`derivation_note` states why the operator must complete them — the
    system never guesses.

    Produced by :func:`saturate_llm_classification`; consumed for review and,
    on accept, by :func:`apply_saturated_llm_classification`.
    """

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1)
    provider: LLMProvider
    provenance: str = Field(min_length=1)
    classification: BusinessClassification
    category: SpendingCategory | None = None
    confidence: Decimal
    reason: str = Field(min_length=1)
    iva_category: IvaCategory | None = None
    business_pct: Decimal | None = None
    iva_rate: Decimal | None = None
    taxable_base: Decimal | None = None
    iva_amount: Decimal | None = None
    rate_derivable: bool = False
    derivation_note: str = ""


def _resolve_saturation_classifier(provider: LLMProvider) -> LLMClassifier:
    """Resolve the production classifier for ``provider`` with the saturation prompt.

    Builds the classifier with
    :func:`aeat.domain.transactions.prompt_spec_with_saturation_fields` so the
    model also selects an expense :class:`SpendingCategory` and an
    :class:`aeat.domain.iva.IvaCategory` from the registry-grounded allow-list,
    keeping the allow-list-guarded ``parse_response`` path intact.
    """
    return resolve_classifier(provider.value, spec=prompt_spec_with_saturation_fields())


def _derive_iva_substrate(
    iva_category: IvaCategory,
    *,
    gross: Decimal,
    on_date: date,
) -> tuple[Decimal | None, Decimal | None, Decimal | None, bool, str]:
    """Derive ``(iva_rate, taxable_base, iva_amount, derivable, note)`` for a category.

    Resolves the registry rate for ``iva_category`` via
    :func:`aeat.domain.iva.resolve_category_rate` and, when derivable, splits
    the absolute ``gross`` at that rate with
    :func:`aeat.domain.iva.split_gross_at_rate`. The model never supplies these
    numbers; they trace to the registry rate and a deterministic inverse split.

    Returns the derived rate/base/amount (or ``None`` for each when the
    category has no simple derivable Spanish domestic rate), the
    ``derivable`` flag, and an operator-facing ``note`` explaining a
    non-derivable category.
    """
    resolution = resolve_category_rate(iva_category, on_date=on_date)
    if not resolution.derivable or resolution.rate is None:
        return None, None, None, False, resolution.reason
    taxable_base, iva_amount = split_gross_at_rate(abs(gross), resolution.rate)
    return resolution.rate, taxable_base, iva_amount, True, ""


def saturate_llm_classification(
    *,
    bucket_id: str,
    transaction_id: str,
    provider: LLMProvider,
    classifier: LLMClassifier | None = None,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    on_date: date | None = None,
) -> LLMSaturatedSuggestion:
    """Run the saturating LLM classifier for one transaction and return a suggestion.

    Loads the transaction, runs the injected classifier (default-resolved from
    ``provider`` with the saturation prompt spec), then DERIVES the regulated
    tax substrate from the model's selected :class:`aeat.domain.iva.IvaCategory`
    using the registry rate and a deterministic inverse split. **Persists
    nothing** — this is the suggest step; rejecting a suggestion is simply not
    applying it.

    Args:
        bucket_id: Active profile bucket id.
        transaction_id: Stable id of the transaction to classify.
        provider: Subprocess provider to resolve when ``classifier`` is None.
        classifier: Injected classifier (dependency injection for tests). When
            None, resolved via :func:`resolve_classifier` for ``provider`` with
            the saturation prompt spec.
        transaction_repository: Injected catalogue repository.
        on_date: Effective date used to resolve the registry rate; defaults to
            the transaction's value date (or booked date).

    Returns:
        A :class:`LLMSaturatedSuggestion` carrying the model's selections and
        the system-derived euro substrate.

    Raises:
        TransactionNotFoundError: When the transaction id is unknown.
        LLMClassifierError: When the classifier fails (provider CLI
            unavailable, hallucinated out-of-allow-list value).
    """
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    transaction = repository.load().get(transaction_id)
    if transaction is None:
        raise TransactionNotFoundError(f"transaction not found: {transaction_id}")
    resolved_classifier = classifier if classifier is not None else _resolve_saturation_classifier(provider)
    response = resolved_classifier.classify(transaction)
    effective_date = on_date or transaction.raw.value_date or transaction.raw.booked_date

    iva_rate: Decimal | None = None
    taxable_base: Decimal | None = None
    iva_amount: Decimal | None = None
    rate_derivable = False
    derivation_note = ""
    if response.iva_category is not None:
        iva_rate, taxable_base, iva_amount, rate_derivable, derivation_note = _derive_iva_substrate(
            response.iva_category,
            gross=transaction.raw.amount,
            on_date=effective_date,
        )
    _logger.info(
        "llm saturate: transaction=%s provider=%s classification=%s iva_category=%s derivable=%s",
        transaction_id,
        provider.value,
        response.classification.value,
        response.iva_category.value if response.iva_category is not None else "",
        rate_derivable,
    )
    return LLMSaturatedSuggestion(
        transaction_id=transaction_id,
        provider=provider,
        provenance=resolved_classifier.decided_by,
        classification=response.classification,
        category=response.category,
        confidence=response.confidence,
        reason=response.reason,
        iva_category=response.iva_category,
        business_pct=response.business_pct,
        iva_rate=iva_rate,
        taxable_base=taxable_base,
        iva_amount=iva_amount,
        rate_derivable=rate_derivable,
        derivation_note=derivation_note,
    )


def apply_saturated_llm_classification(
    suggestion: LLMSaturatedSuggestion,
    *,
    bucket_id: str,
    business_pct: Decimal | None = None,
    actor: str = "operator",
    source_command: str = "aeat app ledger classify --llm --saturate --apply",
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
) -> ManualLedgerTransactionResult:
    """Persist an accepted saturated suggestion through the manual write path.

    Composes the established single-writer manual-command write
    (:func:`update_manual_transaction_fields`) rather than re-implementing it,
    so the regulated fields land with their existing validators plus the
    ``gross == taxable_base + iva_amount`` invariant, and stamps
    ``classified_by`` with the suggestion's ``llm:<model>`` provenance via
    ``classified_by_override``.

    The non-regulated business decision (classification, expense category) and
    the model-selected ``iva_category`` are persisted; the regulated euro
    figures are persisted only when the category was derivable (a
    non-derivable category leaves the operator to complete the numbers). A
    ``MIXED`` suggestion requires a business percentage — the model's proposed
    ``business_pct`` is used unless the caller overrides it; apply refuses
    instructively when neither is present.

    Args:
        suggestion: The accepted :class:`LLMSaturatedSuggestion`.
        bucket_id: Active profile bucket id.
        business_pct: Operator override for the MIXED business percentage;
            falls back to the model's proposed ``business_pct``.
        actor: Operator identity for the audit event.
        source_command: Source-command label recording the operator's verb.
        transaction_repository: Injected catalogue repository.
        bucket_event_repository: Injected audit-event repository.
        occurred_at: Override clock for deterministic tests.

    Returns:
        A :class:`ManualLedgerTransactionResult` reflecting the persisted state.

    Raises:
        TransactionValidationError: When a ``MIXED`` suggestion is applied with
            no business percentage available.
    """
    classification = suggestion.classification
    effective_business_pct = business_pct if business_pct is not None else suggestion.business_pct
    if classification is BusinessClassification.MIXED and effective_business_pct is None:
        raise TransactionValidationError(
            "applying a MIXED saturated suggestion requires a business percentage; "
            "pass --business-pct (the model proposes the split direction but the percentage is operator-owned)",
            context={"transaction_id": suggestion.transaction_id},
        )

    patch_fields: dict[str, object] = {"business_classification": classification}
    if classification is BusinessClassification.MIXED:
        patch_fields["business_pct"] = effective_business_pct
    category_carrying = classification in {BusinessClassification.BUSINESS, BusinessClassification.MIXED}
    if category_carrying and suggestion.category is not None:
        patch_fields["category_id"] = suggestion.category.value
    if suggestion.iva_category is not None:
        patch_fields["iva_category"] = suggestion.iva_category
    if suggestion.rate_derivable:
        patch_fields["taxable_base"] = suggestion.taxable_base
        patch_fields["iva_rate"] = suggestion.iva_rate
        patch_fields["iva_amount"] = suggestion.iva_amount
    patch = ManualLedgerTransactionPatch.model_validate(patch_fields)

    # Compose the single-writer manual write rather than re-implementing the
    # regulated-field persistence (composition-service-no-parallel-write-path).
    # The operator's verb is recorded via ``source_command`` on the manual
    # write's own classification event, and model provenance via
    # ``classified_by_override``; we deliberately do not emit a second,
    # parallel LLM-specific event here.
    result = update_manual_transaction_fields(
        bucket_id=bucket_id,
        transaction_id=suggestion.transaction_id,
        patch=patch,
        actor=actor,
        source_command=source_command,
        classified_by_override=suggestion.provenance,
        transaction_repository=transaction_repository,
        bucket_event_repository=bucket_event_repository,
        occurred_at=occurred_at,
    )
    _logger.info(
        "llm saturate apply: transaction=%s classified_by=%s iva_category=%s derived=%s",
        suggestion.transaction_id,
        suggestion.provenance,
        suggestion.iva_category.value if suggestion.iva_category is not None else "",
        suggestion.rate_derivable,
    )
    return result


__all__ = [
    "LLMClassificationSuggestion",
    "LLMProvider",
    "LLMProviderAvailability",
    "LLMSaturatedSuggestion",
    "apply_llm_classification",
    "apply_saturated_llm_classification",
    "available_llm_providers",
    "is_llm_provider_available",
    "saturate_llm_classification",
    "suggest_llm_classification",
]
