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

from ...adapters.persistence.storage.attachment import AttachmentStore
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...core._models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.config import Settings, load_settings
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
    LLMSplitProposer,
    Transaction,
    TransactionLifecycleState,
    TransactionNotFoundError,
    TransactionValidationError,
    prompt_spec_with_every_spending_category,
    prompt_spec_with_saturation_fields,
    resolve_classifier,
    resolve_split_proposer,
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
from ._actions_split_merge import split_transaction
from ._evidence import PurchaseInvoiceEvidenceInputError, PurchaseInvoiceEvidenceService
from ._evidence_advisory import printed_iva_advisory
from ._evidence_input import (
    cloud_evidence_read_permitted,
    resolve_attachment_evidence_input,
    resolve_purchase_invoice_evidence_input,
)
from ._evidence_split import derive_child_amounts
from ._evidence_textlayer import extract_evidence_text
from ._models import ManualLedgerTransactionPatch, ManualLedgerTransactionResult, SplitChildCommand

_logger = get_logger(__name__)

_BUCKET_EVENT_PAYLOAD_VERSION = 1


class LLMProvider(StrEnum):
    """Subprocess LLM provider names accepted by the classify surface.

    Each value names a local CLI (``claude`` / ``antigravity`` / ``codex``) the
    :class:`aeat.domain.transactions.SubprocessLLMClassifier` shells out to.
    ``antigravity`` shells to ``agy``, Google's agentic CLI and the supported
    successor to the retired standalone ``gemini`` CLI.
    """

    CLAUDE = "claude"
    ANTIGRAVITY = "antigravity"
    CODEX = "codex"


# The CLI binary each subprocess provider shells out to. Used by
# :func:`available_llm_providers` to probe PATH without spawning the process.
# ``antigravity`` resolves to the ``agy`` binary.
_PROVIDER_CLI_BINARY: dict[LLMProvider, str] = {
    LLMProvider.CLAUDE: "claude",
    LLMProvider.ANTIGRAVITY: "agy",
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
    evidence_id: str | None = None


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
            ),
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


def _resolve_evidence_text(
    transaction: Transaction,
    *,
    bucket_id: str,
    settings: Settings,
    evidence_acknowledged: bool,
) -> tuple[str | None, str | None]:
    """Resolve a transaction's linked evidence to on-host text plus its reference.

    Returns ``(None, None)`` when the transaction has no linked evidence,
    otherwise ``(extracted_text, evidence_reference)`` where the reference is the
    consulted ``purchase_invoice_evidence_id`` or ``attachment_id`` (for
    provenance). The only classifiers wired today are cloud subprocess agents, so
    reading evidence transmits it off-host; this is gated by the cloud-upload
    consent posture (default-off, gestor-barred, per-invocation). Bytes are read
    from secure storage into memory and the text layer is extracted on-host --
    nothing is written to disk (``sensitive-financial-data-secure-storage-only``).

    Raises:
        PurchaseInvoiceEvidenceInputError: When evidence is linked but the cloud
            consent gate is not satisfied, or the evidence cannot be read on-host
            (image evidence has no text layer until the on-host vision reader lands).
    """
    evidence_id = transaction.purchase_invoice_evidence_id
    attachment_ids = transaction.attachment_ids
    if evidence_id is None and not attachment_ids:
        return None, None
    if not cloud_evidence_read_permitted(settings, acknowledged=evidence_acknowledged):
        raise PurchaseInvoiceEvidenceInputError(
            "reading attached evidence sends it to a cloud model, which requires the explicit "
            "per-invocation consent acknowledgement; it is off by default and barred for gestor "
            "deployments",
            suggestion="enable the cloud-upload consent posture and acknowledge the upload",
        )
    store = AttachmentStore(objects=secure_object_repository_for_bucket(bucket_id, settings))
    if evidence_id is not None:
        record = PurchaseInvoiceEvidenceService(settings=settings).view(bucket_id=bucket_id, evidence_id=evidence_id)
        evidence_input = resolve_purchase_invoice_evidence_input(record, store=store)
        reference = evidence_id
    else:
        reference = attachment_ids[0]
        evidence_input = resolve_attachment_evidence_input(reference, store=store)
    return extract_evidence_text(evidence_input), reference


def suggest_llm_classification(
    *,
    bucket_id: str,
    transaction_id: str,
    provider: LLMProvider,
    classifier: LLMClassifier | None = None,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    read_evidence: bool = False,
    evidence_acknowledged: bool = False,
    settings: Settings | None = None,
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
        read_evidence: When True, resolve the transaction's linked evidence, extract
            its text on-host, and inject it into the prompt. Off by default.
        evidence_acknowledged: Per-invocation acknowledgement that sending the evidence
            to a cloud model is accepted; required by the cloud-upload consent gate when
            ``read_evidence`` is set.
        settings: Injected settings; defaults to ``load_settings()``.

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
    evidence_text, evidence_reference = (
        _resolve_evidence_text(
            transaction,
            bucket_id=bucket_id,
            settings=settings if settings is not None else load_settings(),
            evidence_acknowledged=evidence_acknowledged,
        )
        if read_evidence
        else (None, None)
    )
    response = resolved_classifier.classify(transaction, evidence_text=evidence_text)
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
        evidence_id=evidence_reference,
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
    evidence_id: str | None = None
    evidence_advisory: str = ""


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
    read_evidence: bool = False,
    evidence_acknowledged: bool = False,
    settings: Settings | None = None,
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
        read_evidence: When True, resolve the transaction's linked evidence, extract
            its text on-host, and inject it into the prompt. Off by default.
        evidence_acknowledged: Per-invocation acknowledgement that sending the evidence
            to a cloud model is accepted; required by the cloud-upload consent gate when
            ``read_evidence`` is set.
        settings: Injected settings; defaults to ``load_settings()``.

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
    evidence_text, evidence_reference = (
        _resolve_evidence_text(
            transaction,
            bucket_id=bucket_id,
            settings=settings if settings is not None else load_settings(),
            evidence_acknowledged=evidence_acknowledged,
        )
        if read_evidence
        else (None, None)
    )
    response = resolved_classifier.classify(transaction, evidence_text=evidence_text)
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
        evidence_id=evidence_reference,
        evidence_advisory=printed_iva_advisory(evidence_text, iva_amount) or "",
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


# ── stage-3b: evidence-driven N-way split ─────────────────────────


class LLMSplitChildSuggestion(BaseModel):
    """One reviewed child of an evidence-driven split, with derived numbers.

    The model proposed a *proportion* of the parent and selected the child's
    expense :class:`SpendingCategory` and :class:`aeat.domain.iva.IvaCategory`;
    this record carries the system-DERIVED euro ``amount`` (from the parent gross
    and the proportion) and the system-DERIVED regulated substrate
    (``iva_rate`` / ``taxable_base`` / ``iva_amount``) looked up from the registry.
    The model never emits a euro amount or a regulated number
    (``llm-selects-system-derives-tax-numbers``).
    """

    model_config = _STRICT_FROZEN

    proportion: Decimal
    amount: Decimal
    description: str = Field(min_length=1)
    category: SpendingCategory | None = None
    iva_category: IvaCategory | None = None
    iva_rate: Decimal | None = None
    taxable_base: Decimal | None = None
    iva_amount: Decimal | None = None
    rate_derivable: bool = False
    derivation_note: str = ""
    evidence_citation: str = ""


class LLMSplitSuggestion(BaseModel):
    """An evidence-driven N-way split proposal with derived child amounts.

    Produced by :func:`suggest_evidence_split` (persists nothing); consumed for
    review and, on accept, by :func:`apply_evidence_split`. The child amounts sum
    exactly to ``parent_amount`` to the cent.
    """

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1)
    provider: LLMProvider
    provenance: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    parent_amount: Decimal
    children: tuple[LLMSplitChildSuggestion, ...]
    evidence_id: str | None = None


class LLMSplitApplyResult(BaseModel):
    """Outcome of applying a reviewed evidence-driven split."""

    model_config = _STRICT_FROZEN

    bucket_id: str = Field(min_length=1)
    parent_transaction_id: str = Field(min_length=1)
    split_group_id: str = Field(min_length=1)
    child_transaction_ids: tuple[str, ...]
    provenance: str = Field(min_length=1)
    classified_child_count: int


def _resolve_default_split_proposer(provider: LLMProvider) -> LLMSplitProposer:
    """Resolve the production split proposer for ``provider`` with the saturation prompt.

    Uses :func:`aeat.domain.transactions.prompt_spec_with_saturation_fields` so each
    proposed child carries the same allow-list-guarded expense-category and
    IVA-category selections the saturate path uses.
    """
    return resolve_split_proposer(provider.value, spec=prompt_spec_with_saturation_fields())


def _split_child_description(child_index: int, *, citation: str, category: SpendingCategory | None) -> str:
    """Build a distinct, operator-facing description for one split child.

    The 1-based ordinal prefix guarantees distinct child descriptions (hence
    distinct split-child ids) even when two children share an amount and a
    category; the label prefers the model's evidence citation, then the expense
    category, then a neutral fallback.
    """
    label = citation.strip() or (category.value if category is not None else "línea")
    return f"{child_index + 1}. {label}"


def suggest_evidence_split(
    *,
    bucket_id: str,
    transaction_id: str,
    provider: LLMProvider,
    proposer: LLMSplitProposer | None = None,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    on_date: date | None = None,
    read_evidence: bool = True,
    evidence_acknowledged: bool = False,
    settings: Settings | None = None,
) -> LLMSplitSuggestion:
    """Propose an evidence-driven N-way split for one transaction.

    Loads the transaction, runs the injected proposer (default-resolved from
    ``provider`` with the saturation prompt spec) over the optional on-host
    evidence text, DERIVES each child's euro amount from the parent gross and the
    model's proportion (summing exactly to the parent), and DERIVES each child's
    regulated tax substrate from the registry rate for the model-selected IVA
    category. **Persists nothing** — this is the suggest step.

    Args:
        bucket_id: Active profile bucket id.
        transaction_id: Stable id of the transaction to split.
        provider: Subprocess provider to resolve when ``proposer`` is None.
        proposer: Injected split proposer (dependency injection for tests). When
            None, resolved via :func:`resolve_split_proposer` for ``provider``.
        transaction_repository: Injected catalogue repository.
        on_date: Effective date used to resolve each child's registry rate;
            defaults to the transaction's value date (or booked date).
        read_evidence: When True (default for splitting), resolve the
            transaction's linked evidence, extract its text on-host, and inject it
            into the prompt.
        evidence_acknowledged: Per-invocation acknowledgement that sending the
            evidence to a cloud model is accepted; required by the cloud-upload
            consent gate when ``read_evidence`` is set and evidence is linked.
        settings: Injected settings; defaults to ``load_settings()``.

    Returns:
        A :class:`LLMSplitSuggestion` whose child amounts sum exactly to the parent.

    Raises:
        TransactionNotFoundError: When the transaction id is unknown.
        LLMClassifierError: When the proposer fails (provider CLI unavailable,
            hallucinated out-of-allow-list value, or a malformed split response).
    """
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    transaction = repository.load().get(transaction_id)
    if transaction is None:
        raise TransactionNotFoundError(f"transaction not found: {transaction_id}")
    resolved_proposer = proposer if proposer is not None else _resolve_default_split_proposer(provider)
    evidence_text, evidence_reference = (
        _resolve_evidence_text(
            transaction,
            bucket_id=bucket_id,
            settings=settings if settings is not None else load_settings(),
            evidence_acknowledged=evidence_acknowledged,
        )
        if read_evidence
        else (None, None)
    )
    response = resolved_proposer.propose_split(transaction, evidence_text=evidence_text)
    proportions = tuple(child.proportion for child in response.children)
    amounts = derive_child_amounts(transaction.raw.amount, proportions)
    effective_date = on_date or transaction.raw.value_date or transaction.raw.booked_date
    children: list[LLMSplitChildSuggestion] = []
    for index, (child, amount) in enumerate(zip(response.children, amounts, strict=True)):
        iva_rate: Decimal | None = None
        taxable_base: Decimal | None = None
        iva_amount: Decimal | None = None
        rate_derivable = False
        derivation_note = ""
        if child.iva_category is not None:
            iva_rate, taxable_base, iva_amount, rate_derivable, derivation_note = _derive_iva_substrate(
                child.iva_category,
                gross=amount,
                on_date=effective_date,
            )
        children.append(
            LLMSplitChildSuggestion(
                proportion=child.proportion,
                amount=amount,
                description=_split_child_description(index, citation=child.evidence_citation, category=child.category),
                category=child.category,
                iva_category=child.iva_category,
                iva_rate=iva_rate,
                taxable_base=taxable_base,
                iva_amount=iva_amount,
                rate_derivable=rate_derivable,
                derivation_note=derivation_note,
                evidence_citation=child.evidence_citation,
            ),
        )
    _logger.info(
        "llm split suggest: transaction=%s provider=%s children=%d",
        transaction_id,
        provider.value,
        len(children),
    )
    return LLMSplitSuggestion(
        transaction_id=transaction_id,
        provider=provider,
        provenance=resolved_proposer.decided_by,
        reason=response.reason,
        parent_amount=transaction.raw.amount,
        children=tuple(children),
        evidence_id=evidence_reference,
    )


def apply_evidence_split(
    suggestion: LLMSplitSuggestion,
    *,
    bucket_id: str,
    actor: str = "operator",
    source_command: str = "aeat app ledger split --llm --apply",
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
) -> LLMSplitApplyResult:
    """Apply a reviewed evidence-driven split through the single-writer split path.

    Composes the established single writers rather than re-implementing them
    (``composition-service-no-parallel-write-path``): first
    :func:`split_transaction` redistributes the parent into children whose
    magnitudes sum exactly to the parent, then for each child
    :func:`update_manual_transaction_fields` stamps the model-selected expense
    category and IVA category, the registry-DERIVED regulated numbers, the parent
    invoice's evidence link, and the ``llm:<model>`` provenance.

    The split path enforces children-sum-to-parent and the non-negative-magnitude
    invariant; the per-child write enforces the
    ``gross == taxable_base + iva_amount`` invariant. The LLM never supplies a
    persisted euro amount or regulated number.

    Args:
        suggestion: The accepted :class:`LLMSplitSuggestion`.
        bucket_id: Active profile bucket id.
        actor: Operator identity for the audit events.
        source_command: Source-command label recording the operator's verb.
        transaction_repository: Injected catalogue repository.
        bucket_event_repository: Injected audit-event repository.
        occurred_at: Override clock for deterministic tests.

    Returns:
        An :class:`LLMSplitApplyResult` naming the split group and its children.

    Raises:
        TransactionNotFoundError: When the parent transaction id is unknown.
        TransactionValidationError: When the split invariants are violated.
    """
    repository = _transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    parent = repository.load().get(suggestion.transaction_id)
    if parent is None:
        raise TransactionNotFoundError(f"transaction not found: {suggestion.transaction_id}")

    commands = tuple(
        SplitChildCommand(amount=child.amount, description=child.description) for child in suggestion.children
    )
    split_result = split_transaction(
        bucket_id=bucket_id,
        transaction_id=suggestion.transaction_id,
        children=commands,
        actor=actor,
        source_command=source_command,
        reason=suggestion.reason,
        transaction_repository=repository,
        bucket_event_repository=bucket_event_repository,
        occurred_at=occurred_at,
    )

    evidence_link: dict[str, object] = {}
    if parent.purchase_invoice_evidence_id is not None:
        evidence_link["purchase_invoice_evidence_id"] = parent.purchase_invoice_evidence_id
    elif parent.attachment_ids:
        evidence_link["attachment_ids"] = parent.attachment_ids

    classified = 0
    for child_txn, child in zip(split_result.child_transactions, suggestion.children, strict=True):
        patch_fields: dict[str, object] = {
            "business_classification": BusinessClassification.BUSINESS,
            **evidence_link,
        }
        if child.category is not None:
            patch_fields["category_id"] = child.category.value
        if child.iva_category is not None:
            patch_fields["iva_category"] = child.iva_category
        if child.rate_derivable:
            patch_fields["taxable_base"] = child.taxable_base
            patch_fields["iva_rate"] = child.iva_rate
            patch_fields["iva_amount"] = child.iva_amount
        patch = ManualLedgerTransactionPatch.model_validate(patch_fields)
        update_manual_transaction_fields(
            bucket_id=bucket_id,
            transaction_id=child_txn.transaction_id,
            patch=patch,
            actor=actor,
            source_command=source_command,
            classified_by_override=suggestion.provenance,
            transaction_repository=repository,
            bucket_event_repository=bucket_event_repository,
            occurred_at=occurred_at,
        )
        classified += 1

    _logger.info(
        "llm split apply: parent=%s split_group=%s children=%d classified=%d classified_by=%s",
        split_result.parent_transaction_id,
        split_result.split_group_id,
        len(split_result.child_transaction_ids),
        classified,
        suggestion.provenance,
    )
    return LLMSplitApplyResult(
        bucket_id=bucket_id,
        parent_transaction_id=split_result.parent_transaction_id,
        split_group_id=split_result.split_group_id,
        child_transaction_ids=split_result.child_transaction_ids,
        provenance=suggestion.provenance,
        classified_child_count=classified,
    )


__all__ = [
    "LLMClassificationSuggestion",
    "LLMProvider",
    "LLMProviderAvailability",
    "LLMSaturatedSuggestion",
    "LLMSplitApplyResult",
    "LLMSplitChildSuggestion",
    "LLMSplitSuggestion",
    "apply_evidence_split",
    "apply_llm_classification",
    "apply_saturated_llm_classification",
    "available_llm_providers",
    "is_llm_provider_available",
    "saturate_llm_classification",
    "suggest_evidence_split",
    "suggest_llm_classification",
]
