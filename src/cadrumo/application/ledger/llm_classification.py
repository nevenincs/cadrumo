"""LLM-assisted ledger classification: suggest / apply / provider availability.

Wires the existing :class:`~domain.transactions.LLMClassifier` engine into
the operator suggest -> review -> confirm / override / reject loop without
rebuilding the classifier. The contract is deliberately thin:

* :func:`suggest_llm_classification` loads one transaction, runs the
  (injected, default-resolved) classifier with the category-enabled prompt
  spec, and returns a typed
  :class:`~llm.suggestions.LLMClassificationSuggestion`
  **without persisting anything**. Rejecting a suggestion is simply not
  applying it.
* :func:`apply_llm_classification` persists an accepted suggestion through the
  established classification write (:func:`~domain.transactions.set_classification`),
  stamping ``classified_by`` with the classifier's ``decided_by`` (``llm:<model>``
  provenance, distinct from manual / ``rule:``) and recording the model's
  ``confidence`` and ``reason``. The accepted decision is appended to the
  profile audit trail through a
  :class:`~adapters.persistence.profile.buckets.BucketEventHistoryRepository` as a
  ``ledger.transaction.classified`` event.

Hallucination containment stays inside the engine: the classifier's
``classify`` runs the allow-list-guarded
:func:`~domain.transactions.parse_response`, so an out-of-allow-list
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
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.storage import AttachmentStore, secure_object_repository_for_bucket
from ...core import PDF_CONTAINER_SHAPES, ImageMediaType, detect_image_media_type, provenance_stamp_transport
from ...core.config import Settings, load_settings
from ...core.logging import get_logger
from ...core.time import coerce_utc_aware, now
from ...domain.buckets import (
    BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH,
    BucketEventHistoryRepositoryProtocol,
    BucketEventObjectType,
    BucketEventType,
)
from ...domain.categories.spending_category import SpendingCategory
from ...domain.iva import IvaCategory, resolve_category_rate, split_gross_at_rate
from ...domain.transactions.enums import BUSINESS_BEARING_STATES, BusinessClassification, TransactionLifecycleState
from ...domain.transactions.errors import TransactionNotFoundError, TransactionValidationError
from ...domain.transactions.llm import (
    LLMClassificationResponse,
    LLMClassifier,
    LLMSplitProposer,
    LLMSplitResponse,
    PromptSpec,
    prompt_spec_with_every_spending_category,
    prompt_spec_with_saturation_fields,
)
from ...domain.transactions.models import Transaction
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ...domain.transactions.service import set_classification
from ...llm.models import MultimodalImageInput
from ...llm.providers.local import rasterise_pdf_pages_to_base64_png
from ...llm.suggestions import (
    LLMClassificationSuggestion,
    LLMSaturatedSuggestion,
    LLMSplitApplyResult,
    LLMSplitChildSuggestion,
    LLMSplitSuggestion,
    LLMSuggestionRejectionResult,
    OperatorIvaDerivationResult,
)
from ...llm.text_classifier import LocalTextLLMClassifier
from ...llm.vision_classifier import LocalVisionLLMClassifier
from .actions_common import (
    build_ledger_bucket_event,
    build_manual_ledger_result,
    resolve_transaction_repository,
    save_transaction_catalogue_and_events,
)
from .actions_manual import update_manual_transaction_fields
from .actions_split_merge import split_transaction_with_classified_children
from .evidence import PurchaseInvoiceEvidenceInputError, PurchaseInvoiceEvidenceService
from .evidence_advisory import printed_iva_advisory
from .evidence_input import (
    EvidenceInput,
    resolve_attachment_evidence_input,
    resolve_purchase_invoice_evidence_input,
)
from .evidence_reference import (
    find_bytes_bearing_evidence_record,
    refuse_reference_without_document_bytes,
)
from .evidence_split import derive_child_amounts
from .evidence_textlayer import extract_evidence_text
from .models import ManualLedgerTransactionPatch, ManualLedgerTransactionResult, SplitChildCommand
from .preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict

_logger = get_logger(__name__)


# The CLI binary each subprocess provider shells out to. Used by


@dataclass(frozen=True)
class ResolvedEvidence:
    """A transaction's linked evidence resolved for an on-host read.

    Exactly one read mode is populated: ``text`` for a text-layer PDF (inlined into
    the prompt and fed to the cloud subprocess classifier, consent-gated) or
    ``images`` for a scan-only PDF / image (read in memory by the LOCAL vision
    model, on-host, gestor-allowed). The ``images`` are transient
    FINANCIAL-derived bytes and MUST never be persisted or logged
    (``sensitive-financial-data-secure-storage-only``).
    """

    reference: str
    text: str | None
    images: tuple[MultimodalImageInput, ...]

    @property
    def is_images(self) -> bool:
        """Whether this evidence routes to the on-host vision reader."""
        return bool(self.images)


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


def _bytes_bearing_evidence_input(
    evidence_id: str | None,
    attachment_ids: tuple[str, ...],
    *,
    store: AttachmentStore,
    settings: Settings,
    bucket_id: str,
) -> tuple[EvidenceInput, str]:
    """Resolve the document bytes to read, and the reference they came from.

    Only the evidence-record id space carries document bytes; the same field
    may legitimately hold a catalogue-invoice id, which does not (see
    ``_evidence_reference``). A reference that cannot supply bytes therefore
    falls through to the row's own attachments rather than refusing a row
    that does hold a readable document.
    """
    record = (
        find_bytes_bearing_evidence_record(
            evidence_id,
            evidence_records=PurchaseInvoiceEvidenceService(settings=settings).list_all(bucket_id=bucket_id),
        )
        if evidence_id is not None
        else None
    )
    if record is not None:
        return resolve_purchase_invoice_evidence_input(record, store=store), record.evidence_id
    if attachment_ids:
        reference = attachment_ids[0]
        return resolve_attachment_evidence_input(reference, store=store), reference
    assert evidence_id is not None  # narrowed by the caller's no-evidence early return
    raise refuse_reference_without_document_bytes(evidence_id)


def _resolve_evidence(
    transaction: Transaction,
    *,
    bucket_id: str,
    settings: Settings,
) -> ResolvedEvidence | None:
    """Resolve a transaction's linked evidence to an on-host read, or ``None``.

    Returns ``None`` when the transaction has no linked evidence. A text-layer PDF
    yields ``text`` and routes to the cloud subprocess classifier, so it is gated by
    the cloud-upload consent posture (default-off, gestor-barred, per-invocation). A
    scan-only PDF or an image yields base64 ``images`` and is read in memory by the
    LOCAL Ollama vision model -- fully on-host, needing no cloud consent and
    permitted for gestor deployments. Bytes are read from secure storage into memory
    only; nothing is written to disk
    (``sensitive-financial-data-secure-storage-only``).

    Raises:
        PurchaseInvoiceEvidenceInputError: When a text-layer read would transmit to a
            cloud model but the per-invocation consent gate is not satisfied.
    """
    evidence_id = transaction.purchase_invoice_evidence_id
    attachment_ids = transaction.attachment_ids
    if evidence_id is None and not attachment_ids:
        return None
    store = AttachmentStore(objects=secure_object_repository_for_bucket(bucket_id, settings))
    evidence_input, reference = _bytes_bearing_evidence_input(
        evidence_id,
        attachment_ids,
        store=store,
        settings=settings,
        bucket_id=bucket_id,
    )
    if evidence_input.document_shape in PDF_CONTAINER_SHAPES:
        try:
            text = extract_evidence_text(evidence_input)
        except PurchaseInvoiceEvidenceInputError:
            text = ""  # scan-only / no usable text layer -> on-host vision path
        if text:
            return ResolvedEvidence(reference=reference, text=text, images=())
        images = tuple(
            MultimodalImageInput.from_base64(page, ImageMediaType.PNG)
            for page in rasterise_pdf_pages_to_base64_png(evidence_input.data)
        )
    else:
        # An attachment is whatever format the operator supplied, so the type is
        # detected from the bytes and an unsupported one refuses here rather than
        # travelling to a provider under a guessed label.
        images = (
            MultimodalImageInput.from_base64(
                base64.b64encode(evidence_input.data).decode("ascii"),
                detect_image_media_type(evidence_input.data),
            ),
        )
    # The on-host vision read is the only path that reaches here. Gate it on the
    # profile's llm_vision capability — opting out disables scanned/image reading
    # entirely (a typed refusal, never a silent skip).
    from ...core import ServiceCapability
    from ..user_profile.capabilities import resolve_active_capability

    if not resolve_active_capability(ServiceCapability.LLM_VISION, settings=settings).enabled:
        raise PurchaseInvoiceEvidenceInputError(
            "on-host LLM vision reading is disabled for this profile; enable it to read scanned or image evidence",
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.EVIDENCE_VISION_CAPABILITY_ENABLED,
                facts={"llm_vision_enabled": False},
            ),
        )
    return ResolvedEvidence(reference=reference, text=None, images=images)


# Raised when a transaction must be read by a cloud subprocess provider (text-layer
# evidence, or no readable image evidence) but no ``--llm`` provider was supplied.
# The on-host vision path needs no provider, so this names that distinction.
_TEXT_PATH_NEEDS_PROVIDER = (
    "classifying this transaction needs a cloud provider: pass --llm with claude, antigravity, or codex. "
    "(--read-evidence reads a scanned or image invoice on-host with no provider, but this transaction has "
    "no readable image evidence to route there.)"
)


def _run_on_host_or_refuse[T](run: Callable[[], T], *, settings: Settings) -> T:
    """Run an on-host reader, preserving a typed unavailable-reader verdict.

    Transport-neutral: it guards the VISION read and, since the local text
    reader was wired, the TEXT read too. Named for the runtime it protects
    rather than for one of its callers, because the previous name would have
    become a quiet lie the moment the second caller arrived.

    The local adapter only guards HTTP *status* errors; a connection-refused or a
    model-missing failure escaped every CLI ``except`` clause as a raw
    ``httpx.ConnectError`` / ``LLMProviderError`` traceback. This converts both into
    an application evidence-input refusal when the probe confirms that the
    reader is unavailable. The provisioning verdict remains unmodified for
    later live-surface resolution. A call failure followed by an available probe
    is not misclassified as an unavailable-reader precondition.
    """
    import httpx

    from ...domain.transactions.llm import LLMClassifierError
    from ...llm.errors import LLMProviderError

    try:
        return run()
    except (httpx.HTTPError, LLMProviderError) as exc:
        from ..provisioning import probe_ollama_vision

        status = probe_ollama_vision(settings)
        if status.precondition_verdict is not None:
            raise PurchaseInvoiceEvidenceInputError(
                LedgerPreconditionCondition.EVIDENCE_READER_AVAILABLE.value,
                precondition_verdict=status.precondition_verdict,
            ) from exc
        raise LLMClassifierError("ledger.evidence.reader.operation_failed") from exc


def _record_injected_classifier_run[T](run: Callable[[], T], *, provider: str) -> T:
    """Run an INJECTED classifier call, recording local run-timing telemetry.

    Renamed from ``_record_subprocess_run`` when the cloud subprocess transport
    was deleted: no production path spawns a process any more, and the only
    callers left supply their own classifier. The name described a transport
    that no longer exists, which is the kind of stale prose this campaign kept
    tripping over.

    Wraps the injected classifier's call (classifiers stay pure and
    time-unaware, per hexagonal layering -- the domain layer must not import the
    storage-touching recorder). Records duration and outcome via
    :class:`~adapters.outbound.llm.LLMRunTelemetryRecorder`, mirroring the
    recording :class:`~llm.LLMClient.complete` performs
    for the on-host vision transport. A run-telemetry write failure never masks
    the real classification result or a real classifier error.
    """
    import time

    from ...adapters.outbound.llm import LLMRunRecord, LLMRunTelemetryRecorder
    from ...llm.errors import LLMCacheError

    started_at = now()
    clock_start = time.monotonic()
    recorder = LLMRunTelemetryRecorder()

    def _write(*, succeeded: bool, error_kind: str) -> None:
        try:
            recorder.record(
                LLMRunRecord(
                    run_id=uuid4().hex,
                    caller="cadrumo.application.ledger.llm_classification",
                    duration_ms=max(0, round((time.monotonic() - clock_start) * 1000)),
                    succeeded=succeeded,
                    error_kind=error_kind,
                    started_at=started_at,
                    provider=provider,
                ),
            )
        except LLMCacheError:
            _logger.debug("llm run-telemetry write failed; continuing without it", exc_info=True)

    try:
        result = run()
    except Exception as exc:
        _write(succeeded=False, error_kind=type(exc).__name__)
        raise
    _write(succeeded=True, error_kind="")
    return result


def classify_with_evidence(
    transaction: Transaction,
    evidence: ResolvedEvidence | None,
    *,
    text_classifier: LLMClassifier | None,
    spec: PromptSpec,
    vision_classifier: LocalVisionLLMClassifier | None,
    vision_model: str | None,
    settings: Settings,
) -> tuple[LLMClassificationResponse, str]:
    """Classify, routing scan/image evidence to the on-host vision classifier.

    Returns ``(response, provenance)``. Image evidence is read by the local vision
    model (``llm:local-vision:<model>`` provenance) and needs no ``text_classifier``;
    text or no evidence runs the cloud subprocess ``text_classifier``
    (``llm:<provider>:<model>`` provenance), which must be present. ``vision_model``
    overrides the settings default vision model for this read.

    Raises:
        TransactionValidationError: When the text path is taken but no
            ``text_classifier`` was resolved (no ``--llm`` provider supplied).
        PurchaseInvoiceEvidenceInputError: When the on-host reader is unavailable;
            the error carries the provisioning probe's exact precondition verdict.
        LLMClassifierError: When the reader call fails after its preconditions are
            confirmed satisfied.
    """
    if evidence is not None and evidence.is_images:
        # The vision path shells out through LLMClient.complete, which records
        # its own run-timing telemetry -- do not double-record here.
        vision = vision_classifier or LocalVisionLLMClassifier(spec=spec, settings=settings, model=vision_model)
        images = evidence.images
        response = _run_on_host_or_refuse(
            lambda: vision.classify(transaction, evidence_images=images),
            settings=settings,
        )
        return response, vision.decided_by
    text = evidence.text if evidence is not None else None
    if text_classifier is None:
        # The LOCAL text reader, wired here for the first time. Before it
        # existed this branch refused unless the operator supplied a cloud
        # provider, which is what made a text-layer PDF the one document class
        # whose contents left the host -- the more machine-readable document
        # taking the less private route, decided by nothing but how it happened
        # to be produced. Text-layer evidence now takes the same on-host path
        # scanned evidence already took.
        local_text = LocalTextLLMClassifier(spec=spec, settings=settings)
        return _run_on_host_or_refuse(
            lambda: local_text.classify(transaction, evidence_text=text),
            settings=settings,
        ), local_text.decided_by
    return _record_injected_classifier_run(
        lambda: text_classifier.classify(transaction, evidence_text=text),
        provider=text_classifier.decided_by,
    ), text_classifier.decided_by


def _split_with_evidence(
    transaction: Transaction,
    evidence: ResolvedEvidence | None,
    *,
    proposer: LLMSplitProposer | None,
    spec: PromptSpec,
    vision_classifier: LocalVisionLLMClassifier | None,
    vision_model: str | None,
    settings: Settings,
) -> tuple[LLMSplitResponse, str]:
    """Propose a split, routing scan/image evidence to the on-host vision classifier.

    ``vision_model`` overrides the settings default vision model for this read.

    Raises:
        TransactionValidationError: When the text path is taken but no ``proposer``
            was resolved (no ``--llm`` provider supplied).
    """
    if evidence is not None and evidence.is_images:
        # The vision path shells out through LLMClient.complete, which records
        # its own run-timing telemetry -- do not double-record here.
        vision = vision_classifier or LocalVisionLLMClassifier(spec=spec, settings=settings, model=vision_model)
        images = evidence.images
        response = _run_on_host_or_refuse(
            lambda: vision.propose_split(transaction, evidence_images=images),
            settings=settings,
        )
        return response, vision.decided_by
    if proposer is None:
        raise TransactionValidationError(
            _TEXT_PATH_NEEDS_PROVIDER,
            context={"transaction_id": transaction.transaction_id},
        )
    text = evidence.text if evidence is not None else None
    return _record_injected_classifier_run(
        lambda: proposer.propose_split(transaction, evidence_text=text),
        provider=proposer.decided_by,
    ), proposer.decided_by


def suggest_llm_classification(
    *,
    bucket_id: str,
    transaction_id: str,
    classifier: LLMClassifier | None = None,
    vision_classifier: LocalVisionLLMClassifier | None = None,
    vision_model: str | None = None,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    read_evidence: bool = False,
    settings: Settings | None = None,
) -> LLMClassificationSuggestion:
    """Run the LLM classifier for one transaction and return a suggestion.

    Loads the transaction, runs the injected classifier (default-resolved with
    the category-enabled prompt spec), and returns the typed suggestion.
    **Persists nothing** — this is the suggest step of the
    suggest / review / confirm / reject loop.

    Args:
        bucket_id: Active profile bucket id.
        transaction_id: Stable id of the transaction to classify.
        classifier: Injected classifier (dependency injection for tests). With
            the cloud transports deleted the on-host reader is the default, so
            an injected classifier is the only non-default case.
        vision_classifier: Injected on-host vision classifier used when the
            evidence is a scan-only PDF or image; default-resolved otherwise.
        vision_model: Overrides the settings default local vision model (e.g.
            ``qwen2.5vl:7b``) for an image/scan read; ``None`` uses the default.
        transaction_repository: Injected catalogue repository.
        read_evidence: When True, resolve the transaction's linked evidence and read
            it on-host — a text-layer PDF is inlined and sent to the cloud
            classifier (consent-gated), a scan-only PDF or image is read by the
            local vision model (no consent needed). Off by default.
        settings: Injected settings; defaults to ``load_settings()``.

    Returns:
        A :class:`~llm.suggestions.LLMClassificationSuggestion`.

    Raises:
        TransactionNotFoundError: When the transaction id is unknown.
        LLMClassifierError: When the classifier fails (e.g. provider CLI
            unavailable, hallucinated out-of-allow-list value).
    """
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    transaction = repository.load().get(transaction_id)
    if transaction is None:
        raise TransactionNotFoundError(
            translated_message="application.ledger.errors.transaction_not_found",
            context={"transaction_id": transaction_id},
        )
    resolved_settings = settings if settings is not None else load_settings()
    resolved_classifier = classifier
    evidence = (
        _resolve_evidence(
            transaction,
            bucket_id=bucket_id,
            settings=resolved_settings,
        )
        if read_evidence
        else None
    )
    response, provenance = classify_with_evidence(
        transaction,
        evidence,
        text_classifier=resolved_classifier,
        spec=prompt_spec_with_every_spending_category(year=transaction.raw.booked_date.year),
        vision_classifier=vision_classifier,
        vision_model=vision_model,
        settings=resolved_settings,
    )
    _logger.info(
        "llm suggest: transaction=%s decided_by=%s classification=%s confidence=%s",
        transaction_id,
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


def apply_llm_classification(
    suggestion: LLMClassificationSuggestion,
    *,
    bucket_id: str,
    business_pct: Decimal | None = None,
    actor: str = "operator",
    source_command: str,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
) -> ManualLedgerTransactionResult:
    """Persist an accepted LLM suggestion with ``llm:`` provenance.

    Writes the decision through :func:`~domain.transactions.set_classification`,
    stamping ``classified_by`` with the suggestion's ``provenance`` (the
    classifier's ``decided_by``, e.g. ``llm:<model>``) and recording the
    model's ``confidence`` and ``reason``. Persists the catalogue and emits a
    :attr:`~domain.buckets.BucketEventType.LEDGER_TRANSACTION_CLASSIFIED`
    event atomically.

    The MVP persists only the non-regulated ``business_classification`` and
    optional expense ``category``. It never sets a regulated tax value.

    A ``MIXED`` suggestion requires an explicit ``business_pct`` (the LLM does
    not produce one); apply refuses instructively when it is absent. The
    expense ``category`` is recorded only for ``BUSINESS`` / ``MIXED``
    classifications.

    Args:
        suggestion: The accepted
            :class:`~llm.suggestions.LLMClassificationSuggestion`.
        bucket_id: Active profile bucket id.
        business_pct: Required when ``suggestion.classification`` is ``MIXED``.
        actor: Operator identity for the audit event.
        source_command: Source-command label for the audit event.
        transaction_repository: Injected catalogue repository.
        bucket_event_repository: Injected audit-event repository.
        occurred_at: Override clock for deterministic tests.

    Returns:
        A :class:`~application.ledger.models.ManualLedgerTransactionResult`
        reflecting the persisted decision.

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
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    _event_repo_arg = bucket_event_repository or BucketEventHistoryRepository()
    assert isinstance(_event_repo_arg, BucketEventHistoryRepository), (
        "apply_llm_classification requires a concrete BucketEventHistoryRepository "
        "(to_secure_object_write is not on the protocol)"
    )
    event_repository = _event_repo_arg
    catalogue = repository.load()
    current = catalogue.get(suggestion.transaction_id)
    if current is None:
        raise TransactionNotFoundError(
            translated_message="application.ledger.errors.transaction_not_found",
            context={"transaction_id": suggestion.transaction_id},
        )
    if current.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        raise TransactionValidationError(
            "only active ledger transactions can be classified; archived, stashed, and split-parent rows are immutable",
            context={
                "transaction_id": suggestion.transaction_id,
                "lifecycle_state": current.lifecycle_state.value,
            },
        )
    category_id: str | None = None
    if classification in BUSINESS_BEARING_STATES:
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
    )
    _logger.info(
        "llm apply: transaction=%s classified_by=%s classification=%s",
        suggestion.transaction_id,
        suggestion.provenance,
        classification.value,
    )
    return build_manual_ledger_result(bucket_id, updated_transaction, (event.event_id,))


# ── stage-2 saturation: grounded rich tax metadata ────────────────


def _derive_iva_substrate(
    iva_category: IvaCategory,
    *,
    gross: Decimal,
    on_date: date,
) -> tuple[Decimal | None, Decimal | None, Decimal | None, bool, str]:
    """Derive ``(iva_rate, taxable_base, iva_amount, derivable, note)`` for a category.

    Resolves the registry rate for ``iva_category`` via
    :func:`~domain.iva.resolve_category_rate` and, when derivable, splits
    the absolute ``gross`` at that rate with
    :func:`~domain.iva.split_gross_at_rate`. The model never supplies these
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
    classifier: LLMClassifier | None = None,
    vision_classifier: LocalVisionLLMClassifier | None = None,
    vision_model: str | None = None,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    on_date: date | None = None,
    read_evidence: bool = False,
    settings: Settings | None = None,
) -> LLMSaturatedSuggestion:
    """Run the saturating LLM classifier for one transaction and return a suggestion.

    Loads the transaction, runs the injected classifier (default-resolved with
    the saturation prompt spec), then DERIVES the regulated tax substrate from
    the model's selected :class:`~domain.iva.IvaCategory` using the registry
    rate and a deterministic inverse split. **Persists nothing** — this is the
    suggest step; rejecting a suggestion is simply not applying it.

    Args:
        bucket_id: Active profile bucket id.
        transaction_id: Stable id of the transaction to classify.
        classifier: Injected classifier (dependency injection for tests). With
            the cloud transports deleted the on-host reader is the default; an
            injected classifier overrides it, with the saturation prompt spec.
        vision_classifier: Injected on-host vision classifier used when the
            evidence is a scan-only PDF or image; default-resolved otherwise.
        vision_model: Overrides the settings default local vision model (e.g.
            ``qwen2.5vl:7b``) for an image/scan read; ``None`` uses the default.
        transaction_repository: Injected catalogue repository.
        on_date: Effective date used to resolve the registry rate; defaults to
            the transaction's value date (or booked date).
        read_evidence: When True, resolve the transaction's linked evidence, extract
            its text on-host, and inject it into the prompt. Off by default.
        settings: Injected settings; defaults to ``load_settings()``.

    Returns:
        A :class:`~llm.suggestions.LLMSaturatedSuggestion`
        carrying the model's selections and the system-derived euro substrate.

    Raises:
        TransactionNotFoundError: When the transaction id is unknown.
        LLMClassifierError: When the classifier fails (provider CLI
            unavailable, hallucinated out-of-allow-list value).
    """
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    transaction = repository.load().get(transaction_id)
    if transaction is None:
        raise TransactionNotFoundError(
            translated_message="application.ledger.errors.transaction_not_found",
            context={"transaction_id": transaction_id},
        )
    resolved_settings = settings if settings is not None else load_settings()
    resolved_classifier = classifier if classifier is not None else None
    evidence = (
        _resolve_evidence(
            transaction,
            bucket_id=bucket_id,
            settings=resolved_settings,
        )
        if read_evidence
        else None
    )
    response, provenance = classify_with_evidence(
        transaction,
        evidence,
        text_classifier=resolved_classifier,
        spec=prompt_spec_with_saturation_fields(year=transaction.raw.booked_date.year),
        vision_classifier=vision_classifier,
        vision_model=vision_model,
        settings=resolved_settings,
    )
    evidence_text = evidence.text if evidence is not None else None
    evidence_reference = evidence.reference if evidence is not None else None
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
        provenance,
        response.classification.value,
        response.iva_category.value if response.iva_category is not None else "",
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
        suggestion: The accepted
            :class:`~llm.suggestions.LLMSaturatedSuggestion`.
        bucket_id: Active profile bucket id.
        business_pct: Operator override for the MIXED business percentage;
            falls back to the model's proposed ``business_pct``.
        actor: Operator identity for the audit event.
        source_command: Source-command label recording the operator's verb.
        transaction_repository: Injected catalogue repository.
        bucket_event_repository: Injected audit-event repository.
        occurred_at: Override clock for deterministic tests.

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


# ── operator-initiated derivation (no LLM) ────────────────────────


def derive_operator_iva_substrate(
    *,
    bucket_id: str,
    transaction_id: str,
    iva_category: IvaCategory,
    on_date: date | None = None,
    actor: str = "operator",
    source_command: str,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
) -> OperatorIvaDerivationResult:
    """Derive and persist the IVA substrate for an OPERATOR-chosen category.

    The same grounded derivation the saturating LLM path uses
    (:func:`~domain.iva.resolve_category_rate` +
    :func:`~domain.iva.split_gross_at_rate`), but initiated by the operator
    rather than the model — the fallback for when the model declines (returns
    ``unknown``) or the operator simply knows the category. Given a transaction
    already classified BUSINESS or MIXED and the selected
    :class:`~domain.iva.IvaCategory`, it resolves the registry rate, splits
    the gross into taxable base and IVA amount, and persists them through the
    manual write with ``derived:`` provenance. Only the IVA substrate is
    touched; the business classification stays as-is. A non-derivable category
    persists nothing and returns an explanatory note.

    Returns:
        The
        :class:`~llm.suggestions.OperatorIvaDerivationResult`
        recording the persisted IVA substrate, or an explanatory note when the
        category is non-derivable.

    Raises:
        TransactionNotFoundError: When the transaction id is unknown.
        TransactionValidationError: When the transaction is not classified
            BUSINESS or MIXED (IVA applies only to business activity).
    """
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
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
    iva_rate, taxable_base, iva_amount, derivable, note = _derive_iva_substrate(
        iva_category,
        gross=transaction.raw.amount,
        on_date=effective_date,
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
        transaction_repository=transaction_repository,
        bucket_event_repository=bucket_event_repository,
        occurred_at=occurred_at,
    )
    _logger.info(
        "operator iva derive: transaction=%s iva_category=%s rate=%s base=%s amount=%s",
        transaction_id,
        iva_category.value,
        iva_rate,
        taxable_base,
        iva_amount,
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
    proposer: LLMSplitProposer | None = None,
    vision_classifier: LocalVisionLLMClassifier | None = None,
    vision_model: str | None = None,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    on_date: date | None = None,
    read_evidence: bool = True,
    settings: Settings | None = None,
) -> LLMSplitSuggestion:
    """Propose an evidence-driven N-way split for one transaction.

    Loads the transaction, runs the injected proposer (default-resolved with
    the saturation prompt spec) over the optional on-host evidence text,
    DERIVES each child's euro amount from the parent gross and the model's
    proportion (summing exactly to the parent), and DERIVES each child's
    regulated tax substrate from the registry rate for the model-selected IVA
    category. **Persists nothing** — this is the suggest step.

    Args:
        bucket_id: Active profile bucket id.
        transaction_id: Stable id of the transaction to split.
        proposer: Injected split proposer (dependency injection for tests). With
            the cloud transports deleted the on-host reader is the default, so
            an injected proposer is the only non-default case.
        vision_classifier: Injected on-host vision classifier used when the
            evidence is a scan-only PDF or image; default-resolved otherwise.
        vision_model: Overrides the settings default local vision model (e.g.
            ``qwen2.5vl:7b``) for an image/scan read; ``None`` uses the default.
        transaction_repository: Injected catalogue repository.
        on_date: Effective date used to resolve each child's registry rate;
            defaults to the transaction's value date (or booked date).
        read_evidence: When True (default for splitting), resolve the
            transaction's linked evidence, extract its text on-host, and inject it
            into the prompt.
        settings: Injected settings; defaults to ``load_settings()``.

    Returns:
        A :class:`~llm.suggestions.LLMSplitSuggestion`
        whose child amounts sum exactly to the parent.

    Raises:
        TransactionNotFoundError: When the transaction id is unknown.
        LLMClassifierError: When the proposer fails (provider CLI unavailable,
            hallucinated out-of-allow-list value, or a malformed split response).
    """
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    transaction = repository.load().get(transaction_id)
    if transaction is None:
        raise TransactionNotFoundError(
            translated_message="application.ledger.errors.transaction_not_found",
            context={"transaction_id": transaction_id},
        )
    resolved_settings = settings if settings is not None else load_settings()
    resolved_proposer = proposer if proposer is not None else None
    evidence = (
        _resolve_evidence(
            transaction,
            bucket_id=bucket_id,
            settings=resolved_settings,
        )
        if read_evidence
        else None
    )
    response, provenance = _split_with_evidence(
        transaction,
        evidence,
        proposer=resolved_proposer,
        spec=prompt_spec_with_saturation_fields(year=transaction.raw.booked_date.year),
        vision_classifier=vision_classifier,
        vision_model=vision_model,
        settings=resolved_settings,
    )
    evidence_reference = evidence.reference if evidence is not None else None
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
        provenance,
        len(children),
    )
    return LLMSplitSuggestion(
        transaction_id=transaction_id,
        provenance=provenance,
        reason=response.reason,
        parent_amount=transaction.raw.amount,
        children=tuple(children),
        evidence_id=evidence_reference,
    )


def _split_child_patch_fields(child: LLMSplitChildSuggestion, *, evidence_link: dict[str, object]) -> dict[str, object]:
    """Build the classification patch fields for one evidence-split child.

    Assembles the ``BUSINESS`` classification, the inherited evidence link, and
    the model-selected category / IVA substrate (the euro figures only when the
    category was registry-derivable). Shared by the atomic split writer's
    per-child classification so the split and no-split paths stamp identical
    fields.
    """
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
    return patch_fields


def apply_evidence_split(
    suggestion: LLMSplitSuggestion,
    *,
    bucket_id: str,
    actor: str = "operator",
    source_command: str,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
) -> LLMSplitApplyResult:
    """Apply a reviewed evidence-driven split through the single-writer split path.

    Delegates the whole mutation to the established single writer rather than
    re-implementing it: :func:`split_transaction_with_classified_children`
    redistributes the parent into children whose magnitudes sum exactly to the
    parent and stamps each child's model-selected expense and IVA category, the
    registry-DERIVED regulated numbers, the parent's inherited evidence link, and
    the ``llm:<model>`` provenance. This function only translates the reviewed
    suggestion into that writer's arguments; it performs no write of its own and
    no follow-up per-child field patch.

    Because the writer persists the parent transition, every classified child, and
    all bucket events in one transaction, a child can never come to rest split but
    unclassified or missing its evidence link. The writer enforces
    children-sum-to-parent, the non-negative-magnitude invariant, and
    ``gross == taxable_base + iva_amount`` per child. The LLM never supplies a
    persisted euro amount or regulated number.

    Args:
        suggestion: The accepted
            :class:`~llm.suggestions.LLMSplitSuggestion`.
        bucket_id: Active profile bucket id.
        actor: Operator identity for the audit events.
        source_command: Source-command label recording the operator's verb.
        transaction_repository: Injected catalogue repository.
        bucket_event_repository: Injected audit-event repository.
        occurred_at: Override clock for deterministic tests.

    Returns:
        An :class:`~llm.suggestions.LLMSplitApplyResult`
        naming the split group and its children.

    Raises:
        TransactionNotFoundError: When the parent transaction id is unknown.
        TransactionValidationError: When the split invariants are violated.
    """
    if not suggestion.recommends_split:
        # A single-child suggestion is the no-split verdict; applying it as a
        # one-way split is degenerate. The CLI routes this to single-transaction
        # classification instead — never here.
        raise TransactionValidationError(
            "this proposal is a no-split verdict (one line); classify the transaction instead of splitting it",
            context={"transaction_id": suggestion.transaction_id, "child_count": len(suggestion.children)},
        )
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    parent = repository.load().get(suggestion.transaction_id)
    if parent is None:
        raise TransactionNotFoundError(
            translated_message="application.ledger.errors.transaction_not_found",
            context={"transaction_id": suggestion.transaction_id},
        )

    commands = tuple(
        SplitChildCommand(amount=child.amount, description=child.description) for child in suggestion.children
    )

    # Every split child inherits the parent's validated evidence link.
    evidence_link: dict[str, object] = {}
    if parent.purchase_invoice_evidence_id is not None:
        evidence_link["purchase_invoice_evidence_id"] = parent.purchase_invoice_evidence_id
    elif parent.attachment_ids:
        evidence_link["attachment_ids"] = parent.attachment_ids

    child_classifications = tuple(
        ManualLedgerTransactionPatch.model_validate(_split_child_patch_fields(child, evidence_link=evidence_link))
        for child in suggestion.children
    )

    # One atomic transaction: parent transition + every classified,
    # evidence-bearing child + all events persist together, or nothing does.
    # No generic field patch re-enters evidence after the split.
    split_result = split_transaction_with_classified_children(
        bucket_id=bucket_id,
        transaction_id=suggestion.transaction_id,
        children=commands,
        child_classifications=child_classifications,
        classified_by=suggestion.provenance,
        actor=actor,
        source_command=source_command,
        reason=suggestion.reason,
        transaction_repository=repository,
        bucket_event_repository=bucket_event_repository,
        occurred_at=occurred_at,
    )
    classified = len(split_result.child_transactions)

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


def apply_evidence_classification(
    suggestion: LLMSplitSuggestion,
    *,
    bucket_id: str,
    actor: str = "operator",
    source_command: str,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
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
            :class:`~llm.suggestions.LLMSplitSuggestion`
            (exactly one child).
        bucket_id: Active profile bucket id.
        actor: Operator identity for the audit event.
        source_command: Source-command label recording the operator's verb.
        transaction_repository: Injected catalogue repository.
        bucket_event_repository: Injected audit-event repository.
        occurred_at: Override clock for deterministic tests.

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
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
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
        transaction_repository=repository,
        bucket_event_repository=bucket_event_repository,
        occurred_at=occurred_at,
    )
    _logger.info(
        "llm auto-classify (no split): transaction=%s classified_by=%s category=%s iva_category=%s",
        parent.transaction_id,
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
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    occurred_at: datetime | None = None,
) -> LLMSuggestionRejectionResult:
    """Record an explicit, audit-trailed rejection of an LLM suggestion.

    This is the fourth decision terminal of the suggest -> review -> decide loop
    (after approve = apply and update = manual override). It captures *what* the
    model proposed and the operator's reason in a
    ``LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED`` bucket event, and **mutates
    nothing** — the transaction's classification, numbers, and lifecycle are
    untouched, so its review status stays ``pending`` (it is still unclassified).
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
        :class:`~llm.suggestions.LLMSuggestionRejectionResult`
        naming the recorded event.

    Raises:
        TransactionNotFoundError: When the transaction id is unknown.
        TransactionValidationError: When the transaction is not active.
    """
    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    catalogue = repository.load()
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
    # does — a bare BucketEventHistoryRepository().save() does not bind to the
    # active bucket store in the CLI flow.
    _event_repo_arg = bucket_event_repository or BucketEventHistoryRepository()
    assert isinstance(_event_repo_arg, BucketEventHistoryRepository), (
        "reject_llm_suggestion requires a concrete BucketEventHistoryRepository "
        "(to_secure_object_write is not on the protocol)"
    )
    save_transaction_catalogue_and_events(
        transaction_repository=repository,
        event_repository=_event_repo_arg,
        catalogue=catalogue,
        events=(event,),
    )
    _logger.info(
        "llm reject: transaction=%s kind=%s provenance=%s",
        suggestion.transaction_id,
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


__all__ = [
    "ResolvedEvidence",
    "apply_evidence_classification",
    "apply_evidence_split",
    "apply_llm_classification",
    "apply_saturated_llm_classification",
    "classify_with_evidence",
    "derive_operator_iva_substrate",
    "reject_llm_suggestion",
    "saturate_llm_classification",
    "suggest_evidence_split",
    "suggest_llm_classification",
]
