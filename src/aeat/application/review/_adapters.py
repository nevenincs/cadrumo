"""Read-only source adapters for the unified review queue.

Each adapter loads pending items from one on-disk source and emits a
tuple of typed :class:`ReviewItem` records. Adapters are pure and
stateless; they tolerate missing source files by returning an empty
tuple. Severity is derived per source via a first-match-wins
predicate table (see ADR D5).
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import cast

from pydantic import ValidationError

from ...core.config import Settings
from ...core.i18n import Translatable
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
from ..sync import (
    DivergenceClassification,
    DivergenceRecord,
    JsonFileDivergenceRepository,
    ResolutionState,
)
from ._enums import ReviewSeverity
from ._errors import ReviewSourceLoadError
from ._models import (
    DivergenceReviewItem,
    FindingReviewItem,
    InvoiceReviewItem,
    TransactionReviewItem,
)

_LOGGER = get_logger(__name__)

_SUMMARY_MAX = 80

# Quad-lingual contract: every Translatable carries es / en / ca / hu.
# The labels here are sourced from
# .vault/reference/2026-05-01-quadlingual-i18n-legal-glossary.md.
_LANGS: tuple[str, ...] = ("es", "en", "ca", "hu")


def _t(es: str, en: str, ca: str, hu: str) -> Translatable:
    """Build a quad-lingual :class:`Translatable` from positional strings.

    Local mirror of ``aeat.entrypoints.cli._i18n.t``; pulled in here so
    that domain-side adapters do not import the CLI surface (kept the
    layered hexagonal direction intact).
    """

    return {"es": es, "en": en, "ca": ca, "hu": hu}


_DIRECTION_LABELS: dict[TransactionDirection, Translatable] = {
    TransactionDirection.INCOMING: _t("ingreso", "incoming", "ingrés", "bevetel"),
    TransactionDirection.OUTGOING: _t("gasto", "outgoing", "despesa", "kiadas"),
    TransactionDirection.INTERNAL_TRANSFER: _t(
        "traspaso interno",
        "internal transfer",
        "traspàs intern",
        "belso atutalas",
    ),
}
_CLASSIFICATION_LABELS: dict[BusinessClassification, Translatable] = {
    BusinessClassification.BUSINESS: _t("negocio", "business", "negoci", "uzleti"),
    BusinessClassification.PERSONAL: _t("personal", "personal", "personal", "szemelyes"),
    BusinessClassification.MIXED: _t("mixto", "mixed", "mixt", "vegyes"),
    BusinessClassification.NOT_YET_PROCESSED: _t(
        "sin procesar",
        "not yet processed",
        "sense processar",
        "feldolgozatlan",
    ),
    BusinessClassification.PROCESSED_UNCLASSIFIED: _t(
        "procesada sin clasificar",
        "processed unclassified",
        "processada sense classificar",
        "feldolgozva, osztalyozatlan",
    ),
    BusinessClassification.SKIPPED_BY_RULE: _t(
        "omitida por regla",
        "skipped by rule",
        "omesa per regla",
        "szabaly altal kihagyva",
    ),
    BusinessClassification.FAILED_VALIDATION: _t(
        "validación fallida",
        "failed validation",
        "validació fallida",
        "ervenytelen",
    ),
}
_INVOICE_REASON_LABELS: dict[str, Translatable] = {
    "unmatched": _t("sin emparejar", "unmatched", "sense aparellar", "parositatlan"),
    "overdue": _t("vencida", "overdue", "vençuda", "lejart"),
    "payment-pending": _t("pago pendiente", "payment pending", "pagament pendent", "fizetes fuggoben"),
    "partially-paid": _t("parcialmente pagada", "partially paid", "parcialment pagada", "reszben fizetve"),
}


def _per_lang_summary(template: Translatable, **fields: str | Translatable) -> Translatable:
    """Build a quad-lingual summary by formatting *template* per language.

    ``fields`` may carry either bare strings (interpolated identically
    into every language) or :class:`Translatable` values (per-language
    interpolation). Every ``Translatable`` field must carry the four
    contract languages; missing slots fall through to the field's
    Spanish slot to keep the output legible.
    """

    out: dict[str, str] = {}
    for lang in _LANGS:
        slot = template.get(lang)  # type: ignore[misc]
        if slot is None:
            continue
        per_lang_fields: dict[str, str] = {}
        for name, value in fields.items():
            if isinstance(value, dict):
                per_lang_fields[name] = str(value.get(lang) or value.get("es") or "")  # type: ignore[misc]
            else:
                per_lang_fields[name] = str(value)
        out[lang] = slot.format(**per_lang_fields)
    return cast(Translatable, out)


# ── transactions ──────────────────────────────────────────────────


def transactions_pending(
    settings: Settings,
    *,
    catalogue: TransactionCatalogue | None = None,
) -> tuple[TransactionReviewItem, ...]:
    """Return one :class:`TransactionReviewItem` per pending-review transaction.

    Skips fully-classified rows (BUSINESS / PERSONAL / MIXED) and rows
    explicitly skipped by rule (``SKIPPED_BY_RULE``) — those have a
    final disposition and do not want Kent's attention.
    """
    if catalogue is None:
        catalogue = _load_transactions(settings)
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
    threshold: Decimal,
    catalogue: TransactionCatalogue | None = None,
) -> tuple[TransactionReviewItem, ...]:
    """Return transactions whose decision confidence sits below a threshold (#236).

    Surfaces every transaction whose ``classification_confidence`` is
    non-None and strictly less than the threshold, regardless of
    classification state. A rule engine that tagged a
    ``PROCESSED_UNCLASSIFIED`` row with confidence 0.4 is just as
    interesting to Kent as a ``BUSINESS`` classification accepted at
    confidence 0.4 — both warrant his attention. Transactions with
    ``None`` confidence are excluded because they have no claim to
    filter against.
    """
    if catalogue is None:
        catalogue = _load_transactions(settings)
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
    """First-match-wins severity per the post-#237 BusinessClassification states.

    Returns ``None`` when the state has a final disposition that does
    not warrant Kent's attention (classified or rule-excluded).
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


def _load_transactions(settings: Settings) -> TransactionCatalogue | None:
    from ...domain.transactions._repository import TransactionCatalogueRepository

    store_dir = settings.aeat_financial_txs_dir.resolve()
    repository = TransactionCatalogueRepository(store_dir=store_dir)
    if not repository.envelope_path.exists():
        return None
    try:
        return repository.load()
    except (ValidationError, OSError, ValueError) as exc:
        raise ReviewSourceLoadError(
            f"failed to load transactions catalogue at {repository.envelope_path}: {exc}"
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
    amount = format(raw.amount.normalize(), "f") if not raw.amount.is_zero() else "0"
    summary = _per_lang_summary(
        _t(
            "[{state}] {direction} {amount} {currency}: {description}",
            "[{state}] {direction} {amount} {currency}: {description}",
            "[{state}] {direction} {amount} {currency}: {description}",
            "[{state}] {direction} {amount} {currency}: {description}",
        ),
        state=_CLASSIFICATION_LABELS[transaction.business_classification],
        direction=_DIRECTION_LABELS[transaction.direction],
        amount=amount,
        currency=raw.currency,
        description=description,
    )
    return TransactionReviewItem(
        item_id=transaction.transaction_id,
        modelo=None,
        severity=severity,
        summary=summary,
        drill_command=f"aeat financial txs classify {transaction.transaction_id} --as ...",
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
    from ...domain.invoices._repository import InvoiceCatalogueRepository

    store_dir = settings.aeat_invoices_dir.resolve()
    repository = InvoiceCatalogueRepository(store_dir=store_dir)
    if not repository.envelope_path.exists():
        return None
    try:
        return repository.load()
    except (ValidationError, OSError, ValueError) as exc:
        raise ReviewSourceLoadError(f"failed to load invoices catalogue at {repository.envelope_path}: {exc}") from exc


def _classify_invoice(invoice: Invoice) -> tuple[ReviewSeverity, str] | None:
    """First-match-wins severity + reason per ADR D5 invoices table."""
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
    grand_total = format(invoice.grand_total.normalize(), "f") if not invoice.grand_total.is_zero() else "0"
    reason_label = _INVOICE_REASON_LABELS.get(
        reason,
        _t(reason, reason, reason, reason),
    )
    summary = _per_lang_summary(
        _t(
            "[{reason}] {kind} {number} {total} {currency} ← {counterparty}",
            "[{reason}] {kind} {number} {total} {currency} ← {counterparty}",
            "[{reason}] {kind} {number} {total} {currency} ← {counterparty}",
            "[{reason}] {kind} {number} {total} {currency} ← {counterparty}",
        ),
        reason=reason_label,
        kind=invoice.kind.value,
        number=invoice.invoice_number,
        total=grand_total,
        currency=invoice.currency,
        counterparty=invoice.counterparty_name,
    )
    since = datetime.combine(invoice.issued_at, time.min, tzinfo=UTC)
    return InvoiceReviewItem(
        item_id=invoice.invoice_id,
        modelo=None,
        severity=severity,
        summary=summary,
        drill_command=f"aeat financial invoices show {invoice.invoice_id}",
        since=since,
        source=invoice,
    )


# ── divergences ───────────────────────────────────────────────────


def divergences_pending(
    settings: Settings,
    *,
    records: tuple[DivergenceRecord, ...] | None = None,
) -> tuple[DivergenceReviewItem, ...]:
    """Return :class:`DivergenceReviewItem`s for PENDING divergence records."""
    if records is None:
        repo = JsonFileDivergenceRepository(settings.aeat_sync_divergence_file_dir)
        try:
            records = repo.list()
        except (ValidationError, OSError, ValueError) as exc:
            raise ReviewSourceLoadError(
                f"failed to list divergences at {settings.aeat_sync_divergence_file_dir}: {exc}"
            ) from exc
    items: list[DivergenceReviewItem] = []
    for record in records:
        if record.resolution_state is not ResolutionState.PENDING:
            continue
        items.append(_to_divergence_item(record))
    return tuple(items)


def _classify_divergence(record: DivergenceRecord) -> ReviewSeverity:
    """First-match-wins severity per ADR D5 divergences table."""
    if record.classification in {
        DivergenceClassification.BREAKING,
        DivergenceClassification.SUSPICIOUS,
    }:
        return ReviewSeverity.CRITICAL
    return ReviewSeverity.NORMAL


def _to_divergence_item(record: DivergenceRecord) -> DivergenceReviewItem:
    classification_label = _t(
        record.classification.value,
        record.classification.value,
        record.classification.value,
        record.classification.value,
    )
    summary = _per_lang_summary(
        _t(
            "[{classification}] {kind}",
            "[{classification}] {kind}",
            "[{classification}] {kind}",
            "[{classification}] {kind}",
        ),
        classification=classification_label,
        kind=record.payload.kind.value,
    )
    return DivergenceReviewItem(
        item_id=record.record_id,
        modelo=str(record.modelo) if record.modelo is not None else None,
        severity=_classify_divergence(record),
        summary=summary,
        drill_command=f"aeat sync show-divergence {record.record_id}",
        since=record.detected_at,
        source=record,
    )


# ── filing drafts ─────────────────────────────────────────────────


def drafts_pending(
    settings: Settings,
    *,
    drafts: tuple[tuple[Path, FilingDraft], ...] | None = None,
) -> tuple[FindingReviewItem, ...]:
    """Return :class:`FindingReviewItem`s for findings + unready drafts."""
    if drafts is None:
        drafts = _load_drafts(settings)
    items: list[FindingReviewItem] = []
    seen: set[tuple[str, str, str]] = set()
    for path, draft in drafts:
        path_str = str(path)
        if draft.findings:
            for finding in draft.findings:
                dedup_key = (draft.draft_id, finding.code, finding.casilla_id or "-")
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                items.append(
                    _to_finding_item(
                        draft=draft,
                        path_str=path_str,
                        finding=finding,
                    )
                )
            continue
        if draft.status in {FilingDraftStatus.DRAFT, FilingDraftStatus.VALIDATED}:
            items.append(
                _to_placeholder_item(
                    draft=draft,
                    path_str=path_str,
                )
            )
        elif draft.status is FilingDraftStatus.APPROVAL_STALE:
            items.append(
                _to_stale_approval_item(
                    draft=draft,
                    path_str=path_str,
                )
            )
    return tuple(items)


def _load_drafts(settings: Settings) -> tuple[tuple[Path, FilingDraft], ...]:
    """Iterate every persisted draft via :class:`FilingDraftRepository`.

    Drafts are ciphertext-at-rest only; the helper returns the canonical
    envelope path alongside the typed payload so callers can echo the
    on-disk location back to the operator without ever touching
    plaintext.
    """
    from ...domain.filing import FilingDraftRepository

    root = settings.aeat_drafts_dir.resolve()
    if not root.exists():
        return ()
    repository = FilingDraftRepository(store_dir=root)
    out: list[tuple[Path, FilingDraft]] = []
    for draft in repository.iter_drafts():
        out.append((repository.envelope_path_for(draft.draft_id), draft))
    return tuple(out)


def _classify_finding(severity: FilingFindingSeverity) -> ReviewSeverity:
    """Map FilingFindingSeverity to ReviewSeverity per ADR D5 findings table."""
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
    fallback = _first_translation(finding.message) or finding.code
    summary_prefix = f"[casilla {casilla}] " if casilla != "-" else ""
    summary: Translatable = {}
    for lang in _LANGS:
        per_lang = finding.message.get(lang)  # type: ignore[misc]
        if not per_lang:
            per_lang = finding.message.get("es") or finding.message.get("en") or fallback
        summary[lang] = summary_prefix + str(per_lang)  # type: ignore[literal-required]
    return FindingReviewItem(
        item_id=f"{draft.draft_id}:{finding.code}:{casilla}",
        modelo=draft.modelo,
        severity=_classify_finding(finding.severity),
        summary=summary,
        drill_command=f"aeat filing show {path_str} --findings-only",
        since=draft.updated_at,
        source=finding,
        draft_id=draft.draft_id,
        draft_path=path_str,
    )


def _to_placeholder_item(*, draft: FilingDraft, path_str: str) -> FindingReviewItem:
    summary = _per_lang_summary(
        _t(
            "borrador no listo para enviar (estado={status})",
            "draft not ready to submit (status={status})",
            "esborrany no preparat per enviar (estat={status})",
            "piszkozat nem all keszen kuldesre (allapot={status})",
        ),
        status=draft.status.value,
    )
    return FindingReviewItem(
        item_id=f"{draft.draft_id}:_status:{draft.status.value}",
        modelo=draft.modelo,
        severity=ReviewSeverity.NORMAL,
        summary=summary,
        drill_command=f"aeat filing show {path_str}",
        since=draft.updated_at,
        source=None,
        draft_id=draft.draft_id,
        draft_path=path_str,
    )


def _to_stale_approval_item(*, draft: FilingDraft, path_str: str) -> FindingReviewItem:
    """Emit a high-severity item for drafts whose stored approval is stale (#230)."""
    summary = _t(
        "aprobación caducada — requiere nueva revisión (estado=APPROVAL_STALE)",
        "approval stale — re-review required (status=APPROVAL_STALE)",
        "aprovació caducada — cal una nova revisió (estat=APPROVAL_STALE)",
        "jovahagyas lejart — ujboli felulvizsgalat szukseges (allapot=APPROVAL_STALE)",
    )
    return FindingReviewItem(
        item_id=f"{draft.draft_id}:_status:APPROVAL_STALE",
        modelo=draft.modelo,
        severity=ReviewSeverity.HIGH,
        summary=summary,
        drill_command=f"aeat review show {path_str}",
        since=draft.updated_at,
        source=None,
        draft_id=draft.draft_id,
        draft_path=path_str,
    )


def _first_translation(message: Translatable) -> str | None:
    """Return the first non-empty slot in the AEAT-canonical-first order."""
    for lang in _LANGS:
        value = message.get(lang)  # type: ignore[misc]
        if value:
            return value
    return None
