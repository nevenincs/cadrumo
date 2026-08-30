"""Read-only source adapters for the unified review queue.

Each adapter loads pending items from one on-disk source and emits a
tuple of typed :class:`ReviewItem` records. Adapters are pure and
stateless; they tolerate missing source files by returning an empty
tuple. Severity is derived per source via a first-match-wins predicate table.

The transaction adapter loads a :class:`TransactionCatalogue` via
:class:`TransactionCatalogueRepository`; the invoice adapter loads an
:class:`InvoiceCatalogue` via :class:`InvoiceCatalogueRepository`. Draft
findings are sourced from the :class:`ModeloDraft` store via the review imports.
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from ...core.config import Settings
from ...core.errors import BaseSeverity, CadrumoError
from ...core.i18n import Translatable as tr
from ...core.logging import get_logger
from ...domain.filing import ModeloDraft, ModeloValidationFinding
from ...domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    PaymentStatus,
)
from ...domain.submission import ModeloDraftStatus
from ...domain.transactions.enums import BusinessClassification, is_classified
from ...domain.transactions.models import Transaction, TransactionCatalogue
from .enums import ReviewSeverity
from .errors import ReviewSourceLoadError
from .models import (
    FindingReviewItem,
    InvoiceReviewItem,
    TransactionReviewItem,
)

_LOGGER = get_logger(__name__)

_SUMMARY_MAX = 80


# ── transactions ──────────────────────────────────────────────────


def transactions_pending(
    settings: Settings,
    *,
    bucket_id: str,
    catalogue: TransactionCatalogue | None = None,
) -> tuple[TransactionReviewItem, ...]:
    """Return one :class:`TransactionReviewItem` per pending-review transaction.

    ``catalogue`` is an optional :class:`TransactionCatalogue` override; the repository is
    loaded when ``None``.

    Skips fully-classified rows (BUSINESS / PERSONAL / MIXED), rows
    explicitly skipped by rule (``SKIPPED_BY_RULE``), and rows the
    operator reviewed and deliberately excluded (``REVIEWED_EXCLUDED``)
    — those have a final disposition and do not want the operator's
    attention.
    """
    if catalogue is None:
        catalogue = _load_transactions(settings, bucket_id=bucket_id)
        if catalogue is None:
            return ()
    items: list[TransactionReviewItem] = []
    for transaction in catalogue.values():
        severity = _classify_transaction(transaction.business_classification)
        if severity is None:
            continue
        items.append(_to_transaction_item(transaction, severity=severity))
    return tuple(items)


def transactions_low_confidence(
    settings: Settings,
    *,
    bucket_id: str,
    threshold: Decimal,
    catalogue: TransactionCatalogue | None = None,
) -> tuple[TransactionReviewItem, ...]:
    """Return transactions whose decision confidence sits below a threshold.

    Args:
        settings: Active application settings.
        bucket_id: Stable bucket identifier for the ledger to inspect.
        threshold: Minimum acceptable confidence; transactions strictly below
            this value are included.
        catalogue: Optional :class:`TransactionCatalogue` override; when ``None``
            the catalogue is loaded from the encrypted store.

    Surfaces every transaction whose ``classification_confidence`` is
    non-None and strictly less than the threshold, regardless of
    classification state. Transactions with ``None`` confidence are excluded
    because they have no claim to filter against.

    Each element in the returned tuple is a :class:`TransactionReviewItem`.
    """
    if catalogue is None:
        catalogue = _load_transactions(settings, bucket_id=bucket_id)
        if catalogue is None:
            return ()
    items: list[TransactionReviewItem] = []
    for transaction in catalogue.values():
        confidence = transaction.classification_confidence
        if confidence is None or confidence >= threshold:
            continue
        items.append(_to_transaction_item(transaction, severity=ReviewSeverity.NORMAL))
    return tuple(items)


def _classify_transaction(state: BusinessClassification) -> ReviewSeverity | None:
    """First-match-wins severity per the BusinessClassification states.

    Returns ``None`` when the state has a final disposition that does
    not warrant the operator's attention (classified, rule-excluded, or
    reviewed-and-excluded).
    """
    if is_classified(state):
        return None
    if state is BusinessClassification.SKIPPED_BY_RULE:
        return None
    if state is BusinessClassification.REVIEWED_EXCLUDED:
        return None
    if state is BusinessClassification.FAILED_VALIDATION:
        return ReviewSeverity.CRITICAL
    if state is BusinessClassification.PROCESSED_UNCLASSIFIED:
        return ReviewSeverity.HIGH
    if state is BusinessClassification.NOT_YET_PROCESSED:
        return ReviewSeverity.NORMAL
    return ReviewSeverity.NORMAL


def _load_transactions(settings: Settings, *, bucket_id: str) -> TransactionCatalogue | None:
    from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository

    del settings
    repository = TransactionCatalogueRepository(bucket_id=bucket_id)
    if not repository.exists():
        _LOGGER.debug("transactions catalogue secure object absent")
        return None
    try:
        return repository.load()
    except (ValidationError, OSError, ValueError) as exc:
        raise ReviewSourceLoadError(
            message="failed to load transactions catalogue from secure backend",
            translated_message="review.adapters.errors.transactions_load_failed",
            context=_load_failure_context(exc),
        ) from exc


def _to_transaction_item(
    transaction: Transaction,
    *,
    severity: ReviewSeverity,
) -> TransactionReviewItem:
    raw = transaction.raw
    effective_date = raw.value_date or raw.booked_date
    since = transaction.classified_at or datetime.combine(effective_date, time.min, tzinfo=UTC)
    description = raw.description.strip()
    if len(description) > _SUMMARY_MAX:
        description = description[: _SUMMARY_MAX - 1] + "…"
    del raw  # description + amount captured above; nothing else needed
    summary = tr("review.transaction.summary")
    return TransactionReviewItem(
        item_id=transaction.transaction_id,
        modelo=None,
        severity=severity,
        summary=summary,
        drill_command=f"aeat app ledger review {transaction.transaction_id}",
        since=since,
        source=transaction,
    )


# ── invoices ──────────────────────────────────────────────────────


def invoices_pending(
    settings: Settings,
    *,
    bucket_id: str,
    catalogue: InvoiceCatalogue | None = None,
) -> tuple[InvoiceReviewItem, ...]:
    """Return :class:`InvoiceReviewItem` records for unmatched / disputed / pending invoices.

    Args:
        settings: Active application settings.
        bucket_id: Stable bucket identifier for the invoice catalogue to inspect.
        catalogue: Optional :class:`InvoiceCatalogue` override; the repository is
            loaded when ``None``.
    """
    if catalogue is None:
        catalogue = _load_invoices(settings, bucket_id=bucket_id)
        if catalogue is None:
            return ()
    items: list[InvoiceReviewItem] = []
    for invoice in catalogue.values():
        result = _classify_invoice(invoice)
        if result is None:
            continue
        severity, reason = result
        items.append(_to_invoice_item(invoice, severity=severity, reason=reason))
    return tuple(items)


def _load_invoices(settings: Settings, *, bucket_id: str) -> InvoiceCatalogue | None:
    from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository

    del settings
    repository = InvoiceCatalogueRepository(bucket_id=bucket_id)
    if not repository.exists():
        _LOGGER.debug("invoices catalogue secure object absent")
        return None
    try:
        return repository.load()
    except (ValidationError, OSError, ValueError) as exc:
        raise ReviewSourceLoadError(
            message="failed to load invoices catalogue from secure backend",
            translated_message="review.adapters.errors.invoices_load_failed",
            context=_load_failure_context(exc),
        ) from exc


def _classify_invoice(invoice: Invoice) -> tuple[ReviewSeverity, str] | None:
    """First-match-wins severity + reason for invoices."""
    if invoice.linked_transaction_ids == ():
        return ReviewSeverity.HIGH, "unmatched"
    if invoice.payment_status is PaymentStatus.OVERDUE:
        return ReviewSeverity.HIGH, "overdue"
    if invoice.payment_status is PaymentStatus.PENDING:
        return ReviewSeverity.NORMAL, "payment-pending"
    if invoice.payment_status is PaymentStatus.PARTIALLY_PAID:
        return ReviewSeverity.NORMAL, "partially-paid"
    return None


def _to_invoice_item(invoice: Invoice, *, severity: ReviewSeverity, reason: str) -> InvoiceReviewItem:
    del reason  # severity already encodes the disposition for the queue line
    summary = tr("review.invoice.summary")
    since = datetime.combine(invoice.issued_at, time.min, tzinfo=UTC)
    return InvoiceReviewItem(
        item_id=invoice.invoice_id,
        modelo=None,
        severity=severity,
        summary=summary,
        drill_command=f"aeat app review view {invoice.invoice_id}",
        since=since,
        source=invoice,
    )


# ── filing drafts ─────────────────────────────────────────────────


def drafts_pending(
    settings: Settings,
    *,
    bucket_id: str,
    drafts: tuple[tuple[Path, ModeloDraft], ...] | None = None,
) -> tuple[FindingReviewItem, ...]:
    """Return :class:`FindingReviewItem` records for findings + unready drafts.

    Args:
        settings: Active application settings.
        bucket_id: Stable bucket identifier for the draft repository to inspect.
        drafts: Optional pre-loaded sequence of ``(path, draft)`` pairs where
            each draft is a :class:`ModeloDraft`; when ``None`` drafts are
            loaded from that bucket's secure storage.

    A draft whose ``profile_tax_id`` does not match the active
    profile's tax id is not the active profile's data and is skipped.
    Callers see only drafts owned by the active profile.
    """
    if drafts is None:
        drafts = _load_drafts(settings, bucket_id=bucket_id)
    active_tax_id = _resolve_review_active_tax_id(settings)
    if active_tax_id is None:
        return ()
    items: list[FindingReviewItem] = []
    seen: set[tuple[str, str, str]] = set()
    for path, draft in drafts:
        if (draft.profile_tax_id or "") != active_tax_id:
            continue
        path_str = str(path)
        if draft.findings:
            items.extend(_draft_finding_review_items(draft, path_str=path_str, seen=seen))
        else:
            _append_unready_draft_review_item(draft, path_str=path_str, items=items)
    return tuple(items)


def _draft_finding_review_items(
    draft: ModeloDraft,
    *,
    path_str: str,
    seen: set[tuple[str, str, str]],
) -> tuple[FindingReviewItem, ...]:
    """Yield one ``FindingReviewItem`` per non-duplicate finding on ``draft``.

    Dedup is keyed on ``(draft_id, finding.code, finding.casilla_id)``
    so two findings against the same casilla under the same code
    surface as a single review row. The ``seen`` set is mutated in
    place so dedup spans every draft in the same ``drafts_pending``
    pass, not just one draft.
    """
    out: list[FindingReviewItem] = []
    for finding in draft.findings:
        dedup_key = (draft.draft_id, finding.code, finding.casilla_id or "-")
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        out.append(_to_finding_item(draft=draft, path_str=path_str, finding=finding))
    return tuple(out)


def _append_unready_draft_review_item(
    draft: ModeloDraft,
    *,
    path_str: str,
    items: list[FindingReviewItem],
) -> None:
    """Append one review item for a finding-free draft that is not yet ready to file.

    DRAFT / VALIDATED drafts get a placeholder review row prompting
    the operator to complete the draft. APPROVAL_STALE drafts get a
    distinct review row prompting re-approval. Any other status is
    a no-op — those drafts are not in the review queue's purview.
    """
    if draft.status in {ModeloDraftStatus.BORRADOR, ModeloDraftStatus.VALIDADO}:
        items.append(_to_placeholder_item(draft=draft, path_str=path_str))
    elif draft.status is ModeloDraftStatus.APROBACION_CADUCADA:
        items.append(_to_stale_approval_item(draft=draft, path_str=path_str))


def _resolve_review_active_tax_id(settings: Settings) -> str | None:
    """Return the active profile's tax id, or ``None`` when unknown."""
    del settings
    try:
        from ..user_profile.projections import fact_value
        from ..workflow.persistence import workflow_state_repository
    except ImportError:
        _LOGGER.debug("review adapters could not import workflow status helpers", exc_info=True)
        return None
    try:
        state = workflow_state_repository().load()
        record = state.active_profile_record()
    except (CadrumoError, AttributeError):
        _LOGGER.debug("review adapters could not resolve active workflow status", exc_info=True)
        return None
    return fact_value(record, "identity.tax_id") or None


def _load_drafts(settings: Settings, *, bucket_id: str) -> tuple[tuple[Path, ModeloDraft], ...]:
    """Iterate every persisted draft via :class:`ModeloDraftRepository`.

    Drafts are ciphertext-at-rest only. The helper returns the secure
    backend's logical path marker alongside the typed payload so callers
    can identify the draft without consulting a plaintext draft
    directory.
    """
    from ...adapters.persistence.profile.filing_drafts import ModeloDraftRepository

    del settings
    repository = ModeloDraftRepository(bucket_id=bucket_id)
    out: list[tuple[Path, ModeloDraft]] = []
    try:
        for draft in repository.iter_drafts():
            out.append((repository.envelope_path_for(draft.draft_id), draft))
    except (CadrumoError, ValidationError, OSError, ValueError) as exc:
        raise ReviewSourceLoadError(
            message="failed to load filing drafts from secure backend",
            translated_message="review.adapters.errors.drafts_load_failed",
            context=_load_failure_context(exc),
        ) from exc
    return tuple(out)


def _load_failure_context(exc: BaseException) -> dict[str, str]:
    """Return non-sensitive load-failure context for operator error envelopes."""
    return {"error_type": type(exc).__name__}


def _classify_finding(severity: BaseSeverity) -> ReviewSeverity:
    """Map BaseSeverity to ReviewSeverity for findings."""
    if severity is BaseSeverity.ERROR:
        return ReviewSeverity.CRITICAL
    if severity is BaseSeverity.WARNING:
        return ReviewSeverity.HIGH
    return ReviewSeverity.INFO


def _to_finding_item(
    *,
    draft: ModeloDraft,
    path_str: str,
    finding: ModeloValidationFinding,
) -> FindingReviewItem:
    casilla = finding.casilla_id or "-"
    summary = tr("review.filing.finding_summary")
    severity = _classify_finding(finding.severity)
    return FindingReviewItem(
        item_id=f"{draft.draft_id}:{finding.code}:{casilla}",
        modelo=draft.modelo,
        severity=severity,
        summary=summary,
        drill_command=f"aeat app review view {draft.draft_id}:{finding.code}:{casilla}",
        since=draft.updated_at,
        source=finding,
        draft_id=draft.draft_id,
        draft_path=path_str,
    )


def _to_placeholder_item(*, draft: ModeloDraft, path_str: str) -> FindingReviewItem:
    summary = tr("review.filing.draft_placeholder_summary")
    return FindingReviewItem(
        item_id=f"{draft.draft_id}:_status:{draft.status.value}",
        modelo=draft.modelo,
        severity=ReviewSeverity.NORMAL,
        summary=summary,
        drill_command=f"aeat app review view {draft.draft_id}:_status:{draft.status.value}",
        since=draft.updated_at,
        source=None,
        draft_id=draft.draft_id,
        draft_path=path_str,
    )


def _to_stale_approval_item(*, draft: ModeloDraft, path_str: str) -> FindingReviewItem:
    """Emit a high-severity item for drafts whose stored approval is stale."""
    summary = tr("review.filing.stale_approval_summary")
    return FindingReviewItem(
        item_id=f"{draft.draft_id}:_status:APPROVAL_STALE",
        modelo=draft.modelo,
        severity=ReviewSeverity.HIGH,
        summary=summary,
        drill_command=f"aeat app review view {draft.draft_id}:_status:APPROVAL_STALE",
        since=draft.updated_at,
        source=None,
        draft_id=draft.draft_id,
        draft_path=path_str,
    )
