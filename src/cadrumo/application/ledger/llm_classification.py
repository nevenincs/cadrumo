"""LLM-assisted ledger classification: suggest / apply / provider availability.

Wires the existing :class:`~domain.transactions.llm.LLMClassifier` engine into
the operator suggest -> review -> confirm / override / reject loop without
rebuilding the classifier. The contract is deliberately thin:

* :func:`suggest_llm_classification` loads one transaction, runs the
  caller-composed classifier port with the category-enabled prompt
  spec, and returns a typed
  :class:`~application.ledger.llm_classification_ports.LLMClassificationSuggestion`
  **without persisting anything**. Rejecting a suggestion is simply not
  applying it.
* :func:`apply_llm_classification` persists an accepted suggestion through the
  established classification write (:func:`~domain.transactions.service.set_classification`),
  stamping ``classified_by`` with the classifier's ``decided_by`` (``llm:<model>``
  provenance, distinct from manual / ``rule:``) and recording the model's
  ``confidence`` and ``reason``. The accepted decision is appended to the
  profile audit trail through the caller-injected bucket-event repository as a
  ``ledger.transaction.classified`` event.

Hallucination containment stays inside the engine: the classifier's
``classify`` runs the allow-list-guarded
:func:`~domain.transactions.llm.parse_response`, so an out-of-allow-list
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
``round_to_cents``. ``irpf_category`` remains operator-only.

Core types:
:class:`~cadrumo.domain.transactions.models.TransactionCatalogue`.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.config import Settings
from ...core.logging import get_logger
from ...core.provenance_stamp import provenance_stamp_transport
from ...core.time.clock import now
from ...core.time.utc import coerce_utc_aware
from ...domain.buckets.event import BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH, BucketEventObjectType, BucketEventType
from ...domain.iva.saturation import resolve_category_rate, split_gross_at_rate
from ...domain.iva.schema import IvaCategory
from ...domain.transactions.classification_origin import written_classification_origin
from ...domain.transactions.enums import BUSINESS_BEARING_STATES, BusinessClassification, TransactionLifecycleState
from ...domain.transactions.errors import TransactionNotFoundError, TransactionValidationError
from ...domain.transactions.llm import (
    LLMClassificationResponse,
    LLMClassifier,
    prompt_spec_with_every_spending_category,
    prompt_spec_with_saturation_fields,
)
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ...domain.transactions.service import set_classification
from ..operations.execution_actor import actor_label_is_automation
from .action_ports import LedgerActionPorts
from .actions_common import (
    build_ledger_bucket_event,
    build_manual_ledger_result,
    resolve_revision_guarded_transaction_repository,
    resolve_transaction_repository,
    save_transaction_catalogue_and_events,
)
from .evidence_advisory import printed_iva_advisory
from .llm_classification_ports import (
    LLMClassificationPorts,
    LLMClassificationSuggestion,
    LLMSaturatedSuggestion,
    LLMSplitSuggestion,
    LLMSuggestionRejectionResult,
    OperatorIvaDerivationResult,
    VisionClassifier,
)
from .llm_evidence import ResolvedEvidence, classify_with_evidence, resolve_llm_evidence
from .manual_update import update_manual_transaction_fields
from .models import ManualLedgerTransactionPatch, ManualLedgerTransactionResult
from .protocols import BucketEventHistoryCoCommitWriterProtocol, TransactionCatalogueCoCommitWriterProtocol

_logger = get_logger(__name__)

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


# The CLI binary each subprocess provider shells out to. Used by


def _transport_from_provenance(provenance: str) -> str:
    """Return the transport segment of an ``llm:<transport>:<model>`` stamp.

    The suggestion used to carry a separate ``provider`` enum field, redundant
    with the stamp and able to disagree with it. The audit payload keeps its
    ``provider`` key -- consumers read it -- but derives the value from the one
    place that records which transport actually read the document, so the two
    can no longer disagree.

    The rationale recorded here once added that the field had become meaningless
    when the transport axis collapsed to the local runtime. That is no longer
    true: off-host reading was re-sanctioned behind a per-invocation consent
    gate, so this value is again the thing that says whether a document left the
    host.

    **Delegated rather than parsed here.** The stamp's middle segment is
    ``<transport>-<reader>``, so a colon split alone returned both glued
    together -- ``local-text`` where the field means ``local``. That was
    invisible while every read was on-host and one label was as good as another;
    with off-host reading back it would have published ``openai-text`` as the
    provider, which is wrong in a way a reader believes rather than questions.

    The fix is convergence, not a second split. Two implementations of one
    grammar agree only while somebody maintains both, and this pair had already
    stopped agreeing.

    Falls back to the whole stamp when the grammar does not recognise it, so a
    malformed provenance surfaces in the payload rather than being blanked --
    and deliberately NOT to a transport label, because an unreadable stamp is a
    question this cannot answer and answering it optimistically would hide the
    artefact a withdrawal most needs to surface.
    """
    return provenance_stamp_transport(provenance) or provenance


_PROVENANCE_ELISION = "..."


def _bounded_transport_label(label: str) -> str:
    """Shorten a transport label to fit one bucket-event payload value.

    The recognised transport segment is always short, but the malformed-stamp
    fallback in :func:`_transport_from_provenance` echoes the whole,
    operator-supplied provenance stamp, which carries no length bound of its
    own. Truncating silently would misreport a malformed stamp as a
    recognised one, so the elision marker keeps a shortened value
    self-evidently shortened.
    """
    if len(label) <= BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH:
        return label
    keep = BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH - len(_PROVENANCE_ELISION)
    return label[:keep] + _PROVENANCE_ELISION


# Raised when a split proposal has no reader to route to. The vision
# transcription reader is the only split proposer the composition wires, and it
# reads images only, so a text-layer or evidence-less transaction reaches no
# proposer at all. The remedy is image or scan evidence, or the manual split flags -- not a
# provider, because none is selectable.


def load_llm_transaction(
    *,
    bucket_id: str,
    transaction_id: str,
    transaction_repository: TransactionCatalogueCoCommitWriterProtocol | None,
    reviewed_transaction: Transaction | None = None,
) -> tuple[TransactionCatalogueCoCommitWriterProtocol, Transaction]:
    """Resolve the catalogue port and use the reviewed row or load its exact id."""
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    if reviewed_transaction is not None:
        if reviewed_transaction.transaction_id != transaction_id:
            raise TransactionValidationError(
                "reviewed transaction does not match the suggestion target",
                context={"transaction_id": transaction_id},
            )
        return repository, reviewed_transaction
    transaction = repository.load().get(transaction_id)
    if transaction is None:
        raise TransactionNotFoundError(
            translated_message="application.ledger.errors.transaction_not_found",
            context={"transaction_id": transaction_id},
        )
    return repository, transaction


def resolve_requested_llm_evidence(
    transaction: Transaction,
    *,
    bucket_id: str,
    settings: Settings,
    ports: LLMClassificationPorts,
    read_evidence: bool,
) -> ResolvedEvidence | None:
    """Resolve linked evidence only when the caller opted into reading it."""
    if not read_evidence:
        return None
    return resolve_llm_evidence(transaction, bucket_id=bucket_id, settings=settings, ports=ports)


def evidence_text_and_reference(evidence: ResolvedEvidence | None) -> tuple[str | None, str | None]:
    """Project optional evidence into the two fields consumed by suggestions."""
    if evidence is None:
        return None, None
    return evidence.text, evidence.reference


def effective_ledger_date(transaction: Transaction, on_date: date | None) -> date:
    """Return the explicit date or the transaction's value/booked date."""
    return on_date or transaction.raw.value_date or transaction.raw.booked_date


def suggest_llm_classification(
    *,
    bucket_id: str,
    transaction_id: str,
    operation: PinnedAuthorityOperation,
    classifier: LLMClassifier | None = None,
    vision_classifier: VisionClassifier | None = None,
    transaction_repository: TransactionCatalogueCoCommitWriterProtocol,
    read_evidence: bool = False,
    settings: Settings,
    ports: LLMClassificationPorts,
    reviewed_transaction: Transaction | None = None,
) -> LLMClassificationSuggestion:
    """Run the LLM classifier for one transaction and return a suggestion.

    Loads the transaction, runs the injected classifier (default-resolved with
    the category-enabled prompt spec), and returns the typed suggestion.
    **Persists nothing** — this is the suggest step of the
    suggest / review / confirm / reject loop.

    Args:
        bucket_id: Active profile bucket id.
        transaction_id: Stable id of the transaction to classify.
        operation: Generation-pinned authority operation for the prompt's
            dated category vocabulary and profile hints.
        classifier: Injected classifier (dependency injection for tests). The
            agent's text-extraction reader is the default, so an injected
            classifier is the only non-default case.
        vision_classifier: Injected vision classifier used when the evidence is
            a scan-only PDF or image; default-resolved otherwise.
        transaction_repository: Injected catalogue repository.
        read_evidence: When True, resolve the transaction's linked evidence and
            read it: a text-layer PDF on the text-extraction selection, a
            scan-only PDF or image on the vision-transcription selection. A
            selected lane that reads off the host needs the per-call consent.
            Off by default.
        settings: Injected settings; defaults to ``load_settings()``.
        ports: Injected evidence-reading and classifier execution ports.
        reviewed_transaction: Immutable caller-captured row used instead of
            reloading the catalogue before provider work; its id must match.

    Returns:
        A :class:`~application.ledger.llm_classification_ports.LLMClassificationSuggestion`.

    Raises:
        TransactionNotFoundError: When the transaction id is unknown.
        LLMClassifierError: When the classifier fails (e.g. provider CLI
            unavailable, hallucinated out-of-allow-list value).
    """
    _, transaction = load_llm_transaction(
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        transaction_repository=transaction_repository,
        reviewed_transaction=reviewed_transaction,
    )
    resolved_settings = settings
    resolved_classifier = classifier
    evidence = resolve_requested_llm_evidence(
        transaction,
        bucket_id=bucket_id,
        settings=resolved_settings,
        ports=ports,
        read_evidence=read_evidence,
    )
    response, provenance = classify_with_evidence(
        transaction,
        evidence,
        text_classifier=resolved_classifier,
        spec=prompt_spec_with_every_spending_category(
            year=transaction.raw.booked_date.year,
            operation=operation,
        ),
        vision_classifier=vision_classifier,
        settings=resolved_settings,
        ports=ports,
    )
    _logger.info(
        "llm suggest: decided_by=%s classification=%s confidence=%s",
        provenance,
        response.classification.value,
        response.confidence,
    )
    return LLMClassificationSuggestion(
        transaction_id=transaction_id,
        provenance=provenance,
        classification=response.classification,
        category=response.category,
        confidence=response.confidence,
        reason=response.reason,
        evidence_id=evidence.reference if evidence is not None else None,
        multiple_components=response.multiple_components,
    )


def _validate_llm_application_business_pct(
    suggestion: LLMClassificationSuggestion,
    business_pct: Decimal | None,
) -> None:
    """Enforce the operator-owned business percentage coupling."""
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


def _validate_active_llm_transaction(catalogue: TransactionCatalogue, transaction_id: str) -> Transaction:
    """Refuse missing or immutable rows before the classification write."""
    current = catalogue.get(transaction_id)
    if current is None:
        raise TransactionNotFoundError(
            translated_message="application.ledger.errors.transaction_not_found",
            context={"transaction_id": transaction_id},
        )
    if current.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        raise TransactionValidationError(
            "only active ledger transactions can be classified; archived, stashed, and split-parent rows are immutable",
            context={
                "transaction_id": transaction_id,
                "lifecycle_state": current.lifecycle_state.value,
            },
        )
    return current


def _llm_category_id(suggestion: LLMClassificationSuggestion) -> str | None:
    """Carry a spending category only on a business-bearing classification."""
    if suggestion.classification not in BUSINESS_BEARING_STATES:
        return None
    return suggestion.category.value if suggestion.category is not None else None


def apply_llm_classification(
    suggestion: LLMClassificationSuggestion,
    *,
    bucket_id: str,
    business_pct: Decimal | None = None,
    actor: str = "operator",
    source_command: str,
    transaction_repository: TransactionCatalogueCoCommitWriterProtocol,
    bucket_event_repository: BucketEventHistoryCoCommitWriterProtocol,
    occurred_at: datetime | None = None,
    expected_current: Transaction | None = None,
) -> ManualLedgerTransactionResult:
    """Persist an accepted LLM suggestion with ``llm:`` provenance.

    Writes the decision through :func:`~domain.transactions.service.set_classification`,
    stamping ``classified_by`` with the suggestion's ``provenance`` (the
    classifier's ``decided_by``, e.g. ``llm:<model>``) and recording the
    model's ``confidence`` and ``reason``. Persists the catalogue and emits a
    :attr:`~domain.buckets.event.BucketEventType.LEDGER_TRANSACTION_CLASSIFIED`
    event atomically.

    The MVP persists only the non-regulated ``business_classification`` and
    optional expense ``category``. It never sets a regulated tax value.

    A ``MIXED`` suggestion requires an explicit ``business_pct`` (the LLM does
    not produce one); apply refuses instructively when it is absent. The
    expense ``category`` is recorded only for ``BUSINESS`` / ``MIXED``
    classifications.

    Args:
        suggestion: The accepted
            :class:`~application.ledger.llm_classification_ports.LLMClassificationSuggestion`.
        bucket_id: Active profile bucket id.
        business_pct: Required when ``suggestion.classification`` is ``MIXED``.
        actor: Operator identity for the audit event.
        source_command: Source-command label for the audit event.
        transaction_repository: Injected catalogue repository.
        bucket_event_repository: Injected audit-event repository.
        occurred_at: Override clock for deterministic tests.
        expected_current: Immutable transaction reviewed before provider work.
            Its exact row is compared atomically with the classification write.

    Returns:
        A :class:`~application.ledger.models.ManualLedgerTransactionResult`
        reflecting the persisted decision.

    Raises:
        TransactionNotFoundError: When the transaction id is unknown.
        TransactionValidationError: When the transaction is not ACTIVE or a
            ``MIXED`` suggestion is applied without a ``business_pct``.
    """
    _validate_llm_application_business_pct(suggestion, business_pct)
    classification = suggestion.classification
    occurred = coerce_utc_aware(occurred_at or now())
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    event_repository = bucket_event_repository
    catalogue = repository.load()
    current = _validate_active_llm_transaction(catalogue, suggestion.transaction_id)
    if expected_current is not None and expected_current.transaction_id != suggestion.transaction_id:
        raise TransactionValidationError(
            "reviewed transaction does not match the classification target",
            context={"transaction_id": suggestion.transaction_id},
        )
    category_id = _llm_category_id(suggestion)
    updated_catalogue = set_classification(
        catalogue,
        suggestion.transaction_id,
        classification=classification,
        business_pct=business_pct,
        category_id=category_id,
        classified_by=suggestion.provenance,
        # Accepting a proposal is the decision of whoever accepted it.
        origin=written_classification_origin(
            by_automation=actor_label_is_automation(actor), classified_by=suggestion.provenance
        ),
        reason=suggestion.reason,
        confidence=suggestion.confidence,
    )
    updated_transaction = updated_catalogue.get(suggestion.transaction_id)
    if updated_transaction is None:
        raise TransactionValidationError(
            "classification write dropped the transaction it was applied to",
            context={"transaction_id": suggestion.transaction_id},
        )
    event = build_ledger_bucket_event(
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
            "provider": _bounded_transport_label(_transport_from_provenance(suggestion.provenance)),
            "confidence": format(suggestion.confidence, "f"),
            "mutation_kind": "llm_classification",
        },
    )
    save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=event_repository,
        catalogue=updated_catalogue,
        events=(event,),
        expected_current=current if expected_current is None else expected_current,
        replacement=updated_transaction,
    )
    _logger.info(
        "llm apply: classified_by=%s classification=%s",
        suggestion.provenance,
        classification.value,
    )
    return build_manual_ledger_result(bucket_id, updated_transaction, (event.event_id,))


# ── stage-2 saturation: grounded rich tax metadata ────────────────


def derive_iva_substrate(
    iva_category: IvaCategory,
    *,
    gross: Decimal,
    on_date: date,
    operation: PinnedAuthorityOperation,
) -> tuple[Decimal | None, Decimal | None, Decimal | None, bool, str]:
    """Derive ``(iva_rate, taxable_base, iva_amount, derivable, note)`` for a category.

    Resolves the registry rate for ``iva_category`` via
    :func:`~domain.iva.saturation.resolve_category_rate` and, when derivable, splits
    the absolute ``gross`` at that rate with
    :func:`~domain.iva.saturation.split_gross_at_rate`. The model never supplies these
    numbers; they trace to the registry rate and a deterministic inverse split.

    Returns the derived rate/base/amount (or ``None`` for each when the
    category has no simple derivable Spanish domestic rate), the
    ``derivable`` flag, and an operator-facing ``note`` explaining a
    non-derivable category.
    """
    resolution = resolve_category_rate(iva_category, on_date=on_date, operation=operation)
    if not resolution.derivable or resolution.rate is None:
        return None, None, None, False, resolution.reason
    taxable_base, iva_amount = split_gross_at_rate(abs(gross), resolution.rate)
    return resolution.rate, taxable_base, iva_amount, True, ""


def _saturation_iva_values(
    response: LLMClassificationResponse,
    *,
    gross: Decimal,
    on_date: date,
    operation: PinnedAuthorityOperation,
) -> tuple[Decimal | None, Decimal | None, Decimal | None, bool, str]:
    """Derive the optional saturation substrate from the model's IVA category."""
    if response.iva_category is None:
        return None, None, None, False, ""
    return derive_iva_substrate(response.iva_category, gross=gross, on_date=on_date, operation=operation)


def _iva_category_label(response: LLMClassificationResponse) -> str:
    """Return the audit-log label for an optional IVA category."""
    if response.iva_category is None:
        return ""
    return response.iva_category.value


def saturate_llm_classification(
    *,
    bucket_id: str,
    transaction_id: str,
    operation: PinnedAuthorityOperation,
    classifier: LLMClassifier | None = None,
    vision_classifier: VisionClassifier | None = None,
    transaction_repository: TransactionCatalogueCoCommitWriterProtocol,
    on_date: date | None = None,
    read_evidence: bool = False,
    settings: Settings,
    ports: LLMClassificationPorts,
    reviewed_transaction: Transaction | None = None,
) -> LLMSaturatedSuggestion:
    """Run the saturating LLM classifier for one transaction and return a suggestion.

    Loads the transaction, runs the injected classifier (default-resolved with
    the saturation prompt spec), then DERIVES the regulated tax substrate from
    the model's selected :class:`~domain.iva.schema.IvaCategory` using the registry
    rate and a deterministic inverse split. **Persists nothing** — this is the
    suggest step; rejecting a suggestion is simply not applying it.

    Args:
        bucket_id: Active profile bucket id.
        transaction_id: Stable id of the transaction to classify.
        operation: Generation-pinned authority operation for the prompt's
            dated category and IVA projections.
        classifier: Injected classifier (dependency injection for tests). The
            agent's text-extraction reader is the default; an injected
            classifier overrides it, with the saturation prompt spec.
        vision_classifier: Injected vision classifier used when the evidence is
            a scan-only PDF or image; default-resolved otherwise.
        transaction_repository: Injected catalogue repository.
        on_date: Effective date used to resolve the registry rate; defaults to
            the transaction's value date (or booked date).
        read_evidence: When True, resolve the transaction's linked evidence, extract
            its text on-host, and inject it into the prompt. Off by default.
        settings: Injected settings; defaults to ``load_settings()``.
        ports: Injected evidence-reading and classifier execution ports.
        reviewed_transaction: Immutable caller-captured row used instead of
            reloading the catalogue before provider work; its id must match.

    Returns:
        A :class:`~application.ledger.llm_classification_ports.LLMSaturatedSuggestion`
        carrying the model's selections and the system-derived euro substrate.

    Raises:
        TransactionNotFoundError: When the transaction id is unknown.
        LLMClassifierError: When the classifier fails (provider CLI
            unavailable, hallucinated out-of-allow-list value).
    """
    _, transaction = load_llm_transaction(
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        transaction_repository=transaction_repository,
        reviewed_transaction=reviewed_transaction,
    )
    resolved_settings = settings
    resolved_classifier = classifier
    evidence = resolve_requested_llm_evidence(
        transaction,
        bucket_id=bucket_id,
        settings=resolved_settings,
        ports=ports,
        read_evidence=read_evidence,
    )
    response, provenance = classify_with_evidence(
        transaction,
        evidence,
        text_classifier=resolved_classifier,
        spec=prompt_spec_with_saturation_fields(
            year=transaction.raw.booked_date.year,
            operation=operation,
        ),
        vision_classifier=vision_classifier,
        settings=resolved_settings,
        ports=ports,
    )
    evidence_text, evidence_reference = evidence_text_and_reference(evidence)
    effective_date = effective_ledger_date(transaction, on_date)
    iva_rate, taxable_base, iva_amount, rate_derivable, derivation_note = _saturation_iva_values(
        response,
        gross=transaction.raw.amount,
        on_date=effective_date,
        operation=operation,
    )
    _logger.info(
        "llm saturate: provider=%s classification=%s iva_category=%s derivable=%s",
        provenance,
        response.classification.value,
        _iva_category_label(response),
        rate_derivable,
    )
    return LLMSaturatedSuggestion(
        transaction_id=transaction_id,
        provenance=provenance,
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
        multiple_components=response.multiple_components,
    )


def apply_saturated_llm_classification(
    suggestion: LLMSaturatedSuggestion,
    *,
    bucket_id: str,
    business_pct: Decimal | None = None,
    actor: str = "operator",
    source_command: str,
    ports: LedgerActionPorts,
    occurred_at: datetime | None = None,
    expected_current: Transaction | None = None,
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
        suggestion: The accepted
            :class:`~application.ledger.llm_classification_ports.LLMSaturatedSuggestion`.
        bucket_id: Active profile bucket id.
        business_pct: Operator override for the MIXED business percentage;
            falls back to the model's proposed ``business_pct``.
        actor: Operator identity for the audit event.
        source_command: Source-command label recording the operator's verb.
        ports: Injected ledger action ports for the catalogue and audit-event
            repositories.
        occurred_at: Override clock for deterministic tests.
        expected_current: Immutable transaction reviewed before provider work.

    Returns:
        A :class:`~application.ledger.models.ManualLedgerTransactionResult`
        reflecting the persisted state.

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
    category_carrying = classification in BUSINESS_BEARING_STATES
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
    # regulated-field persistence (aeat-architecture-boundaries).
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
        ports=ports,
        occurred_at=occurred_at,
        expected_current=expected_current,
    )
    _logger.info(
        "llm saturate apply: classified_by=%s iva_category=%s derived=%s",
        suggestion.provenance,
        suggestion.iva_category.value if suggestion.iva_category is not None else "",
        suggestion.rate_derivable,
    )
    return result


# ── operator-initiated derivation (no LLM) ────────────────────────


def derive_operator_iva_substrate(
    *,
    bucket_id: str,
    transaction_id: str,
    iva_category: IvaCategory,
    on_date: date | None = None,
    actor: str = "operator",
    source_command: str,
    ports: LedgerActionPorts,
    occurred_at: datetime | None = None,
    expected_current: Transaction | None = None,
) -> OperatorIvaDerivationResult:
    """Derive and persist the IVA substrate for an OPERATOR-chosen category.

    The same grounded derivation the saturating LLM path uses
    (:func:`~domain.iva.saturation.resolve_category_rate` +
    :func:`~domain.iva.saturation.split_gross_at_rate`), but initiated by the operator
    rather than the model — the fallback for when the model declines (returns
    ``unknown``) or the operator simply knows the category. Given a transaction
    already classified BUSINESS or MIXED and the selected
    :class:`~domain.iva.schema.IvaCategory`, it resolves the registry rate, splits
    the gross into taxable base and IVA amount, and persists them through the
    manual write with ``derived:`` provenance. Only the IVA substrate is
    touched; the business classification stays as-is. A non-derivable category
    persists nothing and returns an explanatory note.

    ``expected_current`` pins the operator's reviewed transaction through the
    existing manual writer's comparison and atomic replacement.

    Returns:
        The
        :class:`~application.ledger.llm_classification_ports.OperatorIvaDerivationResult`
        recording the persisted IVA substrate, or an explanatory note when the
        category is non-derivable.

    Raises:
        TransactionNotFoundError: When the transaction id is unknown.
        TransactionValidationError: When the transaction is not classified
            BUSINESS or MIXED (IVA applies only to business activity).
    """
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=ports.transaction_repository)
    transaction = repository.load().get(transaction_id)
    if transaction is None:
        raise TransactionNotFoundError(
            translated_message="application.ledger.errors.transaction_not_found",
            context={"transaction_id": transaction_id},
        )
    if transaction.business_classification not in BUSINESS_BEARING_STATES:
        raise TransactionValidationError(
            "IVA derivation applies only to a business transaction; classify it as "
            "BUSINESS or MIXED first, then derive the IVA substrate",
            context={"transaction_id": transaction_id},
        )
    effective_date = on_date or transaction.raw.value_date or transaction.raw.booked_date
    iva_rate, taxable_base, iva_amount, derivable, note = derive_iva_substrate(
        iva_category,
        gross=transaction.raw.amount,
        on_date=effective_date,
        operation=ports.operation,
    )
    if not derivable:
        return OperatorIvaDerivationResult(
            transaction_id=transaction_id,
            iva_category=iva_category,
            derivable=False,
            note=note,
        )
    patch = ManualLedgerTransactionPatch.model_validate(
        {
            "iva_category": iva_category,
            "iva_rate": iva_rate,
            "taxable_base": taxable_base,
            "iva_amount": iva_amount,
        }
    )
    result = update_manual_transaction_fields(
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        patch=patch,
        actor=actor,
        source_command=source_command,
        classified_by_override="derived:iva-category",
        ports=ports,
        occurred_at=occurred_at,
        expected_current=expected_current,
    )
    _logger.info(
        "operator iva derive: iva_category=%s",
        iva_category.value,
    )
    return OperatorIvaDerivationResult(
        transaction_id=transaction_id,
        iva_category=iva_category,
        derivable=True,
        iva_rate=iva_rate,
        taxable_base=taxable_base,
        iva_amount=iva_amount,
        result=result,
    )


# ── stage-3b: evidence-driven N-way split ─────────────────────────


def apply_evidence_classification(
    suggestion: LLMSplitSuggestion,
    *,
    bucket_id: str,
    actor: str = "operator",
    source_command: str,
    ports: LedgerActionPorts,
    occurred_at: datetime | None = None,
    expected_current: Transaction | None = None,
) -> ManualLedgerTransactionResult:
    """Apply a no-split (single-child) evidence suggestion in place on the parent.

    The auto-split router uses one model call — the split proposer — to decide
    whether to split. When the proposer returns a single child (the "no split
    warranted" verdict), that child already carries the model-selected expense and
    IVA categories and the registry-DERIVED ``taxable_base`` / ``iva_rate`` /
    ``iva_amount`` for the whole gross. This stamps them on the parent through the
    single-writer :func:`update_manual_transaction_fields` with the ``llm:<model>``
    provenance — the same values :func:`apply_evidence_split` hands its children,
    but applied in place to one existing row instead of redistributed across new
    ones. The parent's own evidence link is preserved verbatim by that write and is
    never re-set here. The model emits no euro amount or regulated number
    (``llm-selects-system-derives-tax-numbers``).

    Args:
        suggestion: A no-split
            :class:`~application.ledger.llm_classification_ports.LLMSplitSuggestion`
            (exactly one child).
        bucket_id: Active profile bucket id.
        actor: Operator identity for the audit event.
        source_command: Source-command label recording the operator's verb.
        ports: Injected ledger action ports for the catalogue and audit-event
            repositories.
        occurred_at: Override clock for deterministic tests.
        expected_current: Immutable parent reviewed before provider work.

    Returns:
        The :class:`~application.ledger.models.ManualLedgerTransactionResult`
        for the in-place classification.

    Raises:
        TransactionValidationError: When the suggestion recommends a split (use
            :func:`apply_evidence_split`).
        TransactionNotFoundError: When the transaction id is unknown.
    """
    if suggestion.recommends_split:
        raise TransactionValidationError(
            "this proposal recommends a split; apply it with apply_evidence_split, not in place",
            context={"transaction_id": suggestion.transaction_id, "child_count": len(suggestion.children)},
        )
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=ports.transaction_repository)
    parent = repository.load().get(suggestion.transaction_id)
    if parent is None:
        raise TransactionNotFoundError(
            translated_message="application.ledger.errors.transaction_not_found",
            context={"transaction_id": suggestion.transaction_id},
        )
    child = suggestion.children[0]
    # In-place classification on the PARENT: the parent already carries its own
    # evidence, which the manual-write replacement preserves verbatim. Evidence
    # is therefore never re-set through this generic-classification patch —
    # evidence mutation is reserved for `aeat app ledger attach`.
    patch_fields: dict[str, object] = {"business_classification": BusinessClassification.BUSINESS}
    if child.category is not None:
        patch_fields["category_id"] = child.category.value
    if child.iva_category is not None:
        patch_fields["iva_category"] = child.iva_category
    if child.rate_derivable:
        patch_fields["taxable_base"] = child.taxable_base
        patch_fields["iva_rate"] = child.iva_rate
        patch_fields["iva_amount"] = child.iva_amount
    patch = ManualLedgerTransactionPatch.model_validate(patch_fields)
    result = update_manual_transaction_fields(
        bucket_id=bucket_id,
        transaction_id=parent.transaction_id,
        patch=patch,
        actor=actor,
        source_command=source_command,
        classified_by_override=suggestion.provenance,
        ports=ports,
        occurred_at=occurred_at,
        expected_current=expected_current,
    )
    _logger.info(
        "llm auto-classify (no split): classified_by=%s category=%s iva_category=%s",
        suggestion.provenance,
        child.category.value if child.category is not None else "",
        child.iva_category.value if child.iva_category is not None else "",
    )
    return result


# ── reject: the fourth decision terminal (audit-trailed) ──────────


def reject_llm_suggestion(
    suggestion: LLMClassificationSuggestion | LLMSaturatedSuggestion | LLMSplitSuggestion,
    *,
    bucket_id: str,
    reason: str = "",
    actor: str = "operator",
    source_command: str,
    transaction_repository: TransactionCatalogueCoCommitWriterProtocol,
    bucket_event_repository: BucketEventHistoryCoCommitWriterProtocol,
    occurred_at: datetime | None = None,
) -> LLMSuggestionRejectionResult:
    """Record an explicit, audit-trailed rejection of an LLM suggestion.

    This is the fourth decision terminal of the suggest -> review -> decide loop
    (after approve = apply and update = manual override). It captures *what* the
    model proposed and the operator's reason in a
    ``LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED`` bucket event, and **mutates
    no transaction fields** — the current transaction's classification, numbers,
    and lifecycle are untouched, including changes made since this proposal was
    reviewed. The audit event and freshly loaded catalogue revision are committed
    conditionally together, so a concurrent catalogue write refuses the decline.
    No regulated number is written; the model emitted none and reject writes none.

    Args:
        suggestion: The captured proposal being rejected — a stage-1
            classification, a saturated suggestion, or an evidence-driven split.
        bucket_id: Active profile bucket id.
        reason: The operator's free-text reason for rejecting (optional).
        actor: Operator identity for the audit event.
        source_command: Source-command label recording the operator's verb.
        transaction_repository: Injected catalogue repository.
        bucket_event_repository: Injected audit-event repository.
        occurred_at: Override clock for deterministic tests.

    Returns:
        An
        :class:`~application.ledger.llm_classification_ports.LLMSuggestionRejectionResult`
        naming the recorded event.

    Raises:
        TransactionNotFoundError: When the transaction id is unknown.
        TransactionValidationError: When the transaction is not active.
    """
    repository = resolve_revision_guarded_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    catalogue, catalogue_revision = repository.load_revisioned()
    transaction = catalogue.get(suggestion.transaction_id)
    if transaction is None:
        raise TransactionNotFoundError(
            translated_message="application.ledger.errors.transaction_not_found",
            context={"transaction_id": suggestion.transaction_id},
        )
    if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        raise TransactionValidationError(
            "only active ledger transactions can carry an LLM rejection record",
            context={
                "transaction_id": suggestion.transaction_id,
                "lifecycle_state": transaction.lifecycle_state.value,
            },
        )
    occurred = coerce_utc_aware(occurred_at or now())
    if isinstance(suggestion, LLMSplitSuggestion):
        suggestion_kind = "split"
        payload: dict[str, str] = {
            "suggestion_kind": suggestion_kind,
            "child_count": str(len(suggestion.children)),
            "model_reason": suggestion.reason,
        }
    else:
        suggestion_kind = "classification"
        payload = {
            "suggestion_kind": suggestion_kind,
            "classification": suggestion.classification.value,
            "category": suggestion.category.value if suggestion.category is not None else "",
            "confidence": format(suggestion.confidence, "f"),
            "model_reason": suggestion.reason,
        }
        if isinstance(suggestion, LLMSaturatedSuggestion) and suggestion.iva_category is not None:
            payload["iva_category"] = suggestion.iva_category.value
    payload["provider"] = _transport_from_provenance(suggestion.provenance)
    payload["provenance"] = suggestion.provenance
    payload["operator_reason"] = reason
    payload["source_command"] = source_command
    payload["mutation_kind"] = "llm_suggestion_rejected"

    event = build_ledger_bucket_event(
        bucket_id=bucket_id,
        event_type=BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED,
        occurred_at=occurred,
        actor=actor,
        object_type=BucketEventObjectType.LEDGER_TRANSACTION,
        object_id=suggestion.transaction_id,
        payload=payload,
    )
    # Persist the event through the transaction repository's secure-write batch
    # (the unchanged catalogue rides along as a no-op), exactly as the apply path
    # does — the caller-composed event repository stays bound to the active
    # bucket store in the CLI flow.
    _event_repo_arg = bucket_event_repository
    save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=_event_repo_arg,
        catalogue=catalogue,
        events=(event,),
        expected_catalogue_revision=catalogue_revision,
    )
    _logger.info(
        "llm reject: kind=%s provenance=%s",
        suggestion_kind,
        suggestion.provenance,
    )
    return LLMSuggestionRejectionResult(
        bucket_id=bucket_id,
        transaction_id=suggestion.transaction_id,
        bucket_event_id=event.event_id,
        suggestion_kind=suggestion_kind,
        provenance=suggestion.provenance,
        operator_reason=reason,
    )
