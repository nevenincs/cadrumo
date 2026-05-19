"""Read-only source adapters for the unified review queue.

Each adapter loads pending items from one on-disk source and emits a
tuple of typed :class:`ReviewItem` records. Adapters are pure and
stateless; they tolerate missing source files by returning an empty
tuple. Severity is derived per source via a first-match-wins
predicate table.
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from ...core.config import Settings
from ...core.i18n import Translatable as tr
from ...core.logging import get_logger
from ...domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    PaymentStatus,
)
from ...domain.transactions import (
    BusinessClassification,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    is_classified,
)
from ..filing import (
    FilingDraft,
    FilingDraftStatus,
    FilingFindingSeverity,
    FilingValidationFinding,
)
from ._enums import ReviewSeverity
from ._errors import ReviewSourceLoadError
from ._models import (
    FindingReviewItem,
    InvoiceReviewItem,
    TransactionReviewItem,
)

_LOGGER = get_logger(__name__)

_SUMMARY_MAX = 80

# Multilingual contract: every tr carries es / en / ca / hu.
_LANGS: tuple[str, ...] = ("es", "en", "ca", "hu")


# ── transactions ──────────────────────────────────────────────────


def transactions_pending(
    settings: Settings,
    *,
    bucket_id: str,
    catalogue: TransactionCatalogue | None = None,
) -> tuple[TransactionReviewItem, ...]:
    """Return one :class:`TransactionReviewItem` per pending-review transaction.

    Skips fully-classified rows (BUSINESS / PERSONAL / MIXED) and rows
    explicitly skipped by rule (``SKIPPED_BY_RULE``) — those have a
    final disposition and do not want the operator's attention.
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

    Surfaces every transaction whose ``classification_confidence`` is
    non-None and strictly less than the threshold, regardless of
    classification state. A rule engine that tagged a
    ``PROCESSED_UNCLASSIFIED`` row with confidence 0.4 is just as
    interesting to the operator as a ``BUSINESS`` classification
    accepted at confidence 0.4 — both warrant attention. Transactions
    with ``None`` confidence are excluded because they have no claim
    to filter against.
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
    not warrant the operator's attention (classified or rule-excluded).
    """
    if is_classified(state):
        return None
    if state is BusinessClassification.SKIPPED_BY_RULE:
        return None
    if state is BusinessClassification.FAILED_VALIDATION:
        return ReviewSeverity.CRITICAL
    if state is BusinessClassification.PROCESSED_UNCLASSIFIED:
        return ReviewSeverity.HIGH
    if state is BusinessClassification.NOT_YET_PROCESSED:
        return ReviewSeverity.NORMAL
    return ReviewSeverity.NORMAL


def _load_transactions(settings: Settings, *, bucket_id: str) -> TransactionCatalogue | None:
    from ...domain.transactions import TransactionCatalogueRepository

    del settings
    repository = TransactionCatalogueRepository(bucket_id=bucket_id)
    if not repository.exists():
        _LOGGER.debug("transactions catalogue secure object absent")
        return None
    try:
        return repository.load()
    except (ValidationError, OSError, ValueError) as exc:
        raise ReviewSourceLoadError(f"failed to load transactions catalogue from secure backend: {exc}") from exc


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
        drill_command=f"aeat app ledger review --id {transaction.transaction_id}",
        since=since,
        source=transaction,
    )


# ── invoices ──────────────────────────────────────────────────────


def invoices_pending(
    settings: Settings,
    *,
    catalogue: InvoiceCatalogue | None = None,
) -> tuple[InvoiceReviewItem, ...]:
    """Return :class:`InvoiceReviewItem`s for unmatched / disputed / pending invoices."""
    if catalogue is None:
        catalogue = _load_invoices(settings)
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


def _load_invoices(settings: Settings) -> InvoiceCatalogue | None:
    from ...domain.invoices import InvoiceCatalogueRepository

    del settings
    repository = InvoiceCatalogueRepository()
    if not repository.exists():
        _LOGGER.debug("invoices catalogue secure object absent")
        return None
    try:
        return repository.load()
    except (ValidationError, OSError, ValueError) as exc:
        raise ReviewSourceLoadError(f"failed to load invoices catalogue from secure backend: {exc}") from exc


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
        drill_command=f"aeat app review show {invoice.invoice_id}",
        since=since,
        source=invoice,
    )


# ── filing drafts ─────────────────────────────────────────────────


def drafts_pending(
    settings: Settings,
    *,
    drafts: tuple[tuple[Path, FilingDraft], ...] | None = None,
) -> tuple[FindingReviewItem, ...]:
    """Return :class:`FindingReviewItem`s for findings + unready drafts.

    A draft whose ``profile_tax_id`` does not match the active
    profile's tax id is not the active profile's data and is skipped.
    Callers see only drafts owned by the active profile.
    """
    if drafts is None:
        drafts = _load_drafts(settings)
    active_tax_id = _resolve_active_tax_id(settings)
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
    draft: FilingDraft,
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
    draft: FilingDraft,
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
    if draft.status in {FilingDraftStatus.DRAFT, FilingDraftStatus.VALIDATED}:
        items.append(_to_placeholder_item(draft=draft, path_str=path_str))
    elif draft.status is FilingDraftStatus.APPROVAL_STALE:
        items.append(_to_stale_approval_item(draft=draft, path_str=path_str))


def _resolve_active_tax_id(settings: Settings) -> str | None:
    """Return the active profile's tax id, or ``None`` when unknown."""
    del settings
    try:
        from ..user_profile._orchestration import fact_value
        from ..workflow import workflow_state_repository
    except Exception:
        _LOGGER.debug("review adapters could not import workflow status helpers", exc_info=True)
        return None
    try:
        state = workflow_state_repository().load()
        record = state.active_profile_record()
    except Exception:
        _LOGGER.debug("review adapters could not resolve active workflow status", exc_info=True)
        return None
    return fact_value(record, "identity.tax_id") or None


def _load_drafts(settings: Settings) -> tuple[tuple[Path, FilingDraft], ...]:
    """Iterate every persisted draft via :class:`FilingDraftRepository`.

    Drafts are ciphertext-at-rest only. The helper returns the secure
    backend's logical path marker alongside the typed payload so callers
    can identify the draft without consulting a plaintext draft
    directory.
    """
    from ...domain.filing import FilingDraftRepository

    del settings
    repository = FilingDraftRepository()
    out: list[tuple[Path, FilingDraft]] = []
    for draft in repository.iter_drafts():
        out.append((repository.envelope_path_for(draft.draft_id), draft))
    return tuple(out)


def _classify_finding(severity: FilingFindingSeverity) -> ReviewSeverity:
    """Map FilingFindingSeverity to ReviewSeverity for findings."""
    if severity is FilingFindingSeverity.ERROR:
        return ReviewSeverity.CRITICAL
    if severity is FilingFindingSeverity.WARNING:
        return ReviewSeverity.HIGH
    return ReviewSeverity.INFO


def _to_finding_item(
    *,
    draft: FilingDraft,
    path_str: str,
    finding: FilingValidationFinding,
) -> FindingReviewItem:
    casilla = finding.casilla_id or "-"
    _first_translation(finding.message) or finding.code
    summary = tr("review.filing.finding_summary")
    severity = _classify_finding(finding.severity)
    return FindingReviewItem(
        item_id=f"{draft.draft_id}:{finding.code}:{casilla}",
        modelo=draft.modelo,
        severity=severity,
        summary=summary,
        drill_command=f"aeat app review show {draft.draft_id}:{finding.code}:{casilla}",
        since=draft.updated_at,
        source=finding,
        draft_id=draft.draft_id,
        draft_path=path_str,
    )


def _to_placeholder_item(*, draft: FilingDraft, path_str: str) -> FindingReviewItem:
    summary = tr("review.filing.draft_placeholder_summary")
    return FindingReviewItem(
        item_id=f"{draft.draft_id}:_status:{draft.status.value}",
        modelo=draft.modelo,
        severity=ReviewSeverity.NORMAL,
        summary=summary,
        drill_command=f"aeat app review show {draft.draft_id}:_status:{draft.status.value}",
        since=draft.updated_at,
        source=None,
        draft_id=draft.draft_id,
        draft_path=path_str,
    )


def _to_stale_approval_item(*, draft: FilingDraft, path_str: str) -> FindingReviewItem:
    """Emit a high-severity item for drafts whose stored approval is stale."""
    summary = tr("review.filing.stale_approval_summary")
    return FindingReviewItem(
        item_id=f"{draft.draft_id}:_status:APPROVAL_STALE",
        modelo=draft.modelo,
        severity=ReviewSeverity.HIGH,
        summary=summary,
        drill_command=f"aeat app review show {draft.draft_id}:_status:APPROVAL_STALE",
        since=draft.updated_at,
        source=None,
        draft_id=draft.draft_id,
        draft_path=path_str,
    )


def _first_translation(message: str) -> str | None:
    """Return the first non-empty slot in the AEAT-canonical-first order."""
    return message
