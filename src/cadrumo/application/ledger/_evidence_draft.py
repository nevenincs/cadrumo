"""On-host invoice-PDF field extraction into a typed draft.

Given an ``EvidenceInput`` already resolved from secure storage (see
:mod:`~application.ledger._evidence_input`),
:func:`~application.ledger.extract_invoice_fields` runs the in-tree on-host
text-layer extractor
(:func:`~application.ledger._evidence_textlayer.extract_evidence_text`) and
applies grounded heuristics -- the shared Spanish tax-id validator
(:func:`~core.identity.validate_spanish_tax_id`), the shared day-first date
parser (:func:`~core.parsing.parse_date`), and the shared European decimal
separator normaliser (:func:`~core.decimal.normalize_decimal_separators`) -- to
recover a supplier NIF/NIE/CIF, invoice number, invoice date, taxable base, IVA
rate, IVA amount, and grand total.

This is the extraction PRIMITIVE only: it returns an :class:`InvoiceDraft` the
operator reviews and confirms. It never persists an
:class:`~domain.invoices.Invoice` and never guesses a value it cannot ground in
the extracted text -- every field it cannot recover is left ``None`` rather than
fabricated
(``no-silent-under-declaration`` in spirit: an unconfident field is absent, not
invented).

Everything here runs on-host and in-memory only. The evidence bytes and the
extracted text never touch disk and are never sent to a cloud provider or an
LLM. This module makes no network call and performs no filesystem write.

A scan-only PDF (no embedded text layer) or an image attachment has nothing for
:func:`~application.ledger.extract_invoice_fields` to read, so
:func:`~application.ledger.extract_invoice_draft_from_evidence` falls back to the
on-host LOCAL vision reader (:mod:`~application.ledger._evidence_draft_vision`)
-- the same rasterise-then-read-with-Ollama transport
:class:`~application.ledger._vision_classifier.LocalVisionLLMClassifier` already
uses for classification, gated by :attr:`~core.ServiceCapability.LLM_VISION` and
never a cloud call. When on-host vision reading is disabled for the profile, or
the local Ollama runtime is unreachable, the caller gets a typed, instructive
refusal -- never a silent empty draft.

:func:`~application.ledger.extract_invoice_draft_from_evidence` is the CLI-facing
wiring layer: it resolves an already-stored ``purchase_invoice_evidence`` record
or a linked ``attachment_id`` to its in-memory bytes (through the private
evidence-input resolvers
:func:`~application.ledger._evidence_input.resolve_purchase_invoice_evidence_input`
and
:func:`~application.ledger._evidence_input.resolve_attachment_evidence_input`) and
runs :func:`~application.ledger.extract_invoice_fields` over them, falling back
to the on-host vision reader for scan-only PDFs and images, so
``aeat app ledger evidence extract`` needs only a bucket id plus one of the two
reference ids.

:func:`~application.ledger.confirm_invoice_draft_from_evidence` is the
non-interactive CONFIRM step that closes the review loop: it re-runs the on-host
extraction, applies any operator-supplied field overrides (extraction is
best-effort -- every field may be corrected), and delegates the actual write to
:func:`~application.invoices.create_catalogue_invoice` -- the sole sanctioned
:class:`~domain.invoices.Invoice` writer
(``composition-service-no-parallel-write-path``). A confirm keyed on the same
evidence/attachment reference and the same resolved fields is a guarded no-op
that returns the existing invoice rather than raising or duplicating
(``single-subject-mutation-is-idempotent-guarded``); a same-reference confirm
whose resolved fields genuinely differ from the already-stored invoice mints a
second, distinct invoice record (a different content-derived
:attr:`~domain.invoices.Invoice.invoice_id`) rather than silently
overwriting one filer's data with another's.

Confirming also auto-links the source evidence to the resulting invoice:
:func:`~domain.attachments.link_attachment_invoice` appends the invoice's id
to the backing :class:`~domain.attachments.Attachment`'s
:attr:`~domain.attachments.Attachment.linked_invoice_ids`, closing the
provenance loop in both directions (the invoice is discoverable from the
evidence, and the evidence is the invoice's traceable source). The link is
re-asserted on a guarded no-op confirm too, so a re-confirm never regresses a
provenance link that was never wired for older evidence, and the append itself
is idempotent (dedup on the linked-ids tuple).

See Also:
    :class:`~application.ledger.InvoiceDraft`
        Public draft record returned before an invoice is persisted.
    :func:`~application.ledger.extract_invoice_fields`
        Text-layer extraction primitive used before any evidence reference
        resolution or confirm write.
    :func:`~application.ledger.extract_invoice_draft_from_evidence`
        CLI-facing resolver that loads stored evidence bytes and chooses the
        text-layer or on-host vision path.
    :func:`~application.ledger.confirm_invoice_draft_from_evidence`
        Non-interactive confirm step that re-extracts, applies overrides, and
        delegates the catalogue write.
    :mod:`~application.ledger._evidence_draft_vision`
        On-host vision fallback for scan-only PDFs and image attachments.
    :func:`~application.invoices.create_catalogue_invoice`
        Sole sanctioned writer for the resulting catalogue invoice.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel

from ...adapters.outbound.llm import (
    LLMPdfRasterisationError,
    LLMProviderError,
    rasterise_pdf_pages_to_base64_png,
)
from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.storage import AttachmentStore, secure_object_repository_for_bucket
from ...application.invoices import build_catalogue_invoice, create_catalogue_invoice
from ...core import STRICT_FROZEN_CONFIG, ServiceCapability
from ...core.config import Settings
from ...core.config import load_settings as _load_settings
from ...core.decimal import normalize_decimal_separators
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.identity import IdentityError, validate_spanish_tax_id
from ...core.parsing import parse_date, parse_iso8601_date
from ...domain.attachments import link_attachment_invoice
from ...domain.invoices import Invoice, InvoiceCatalogueRepositoryProtocol
from ...domain.iva import InvoiceKind
from ..provisioning import probe_ollama_vision
from ..user_profile import resolve_active_capability
from ._evidence import MediaKind, PurchaseInvoiceEvidenceInputError, PurchaseInvoiceEvidenceService
from ._evidence_input import (
    EvidenceInput,
    resolve_attachment_evidence_input,
    resolve_purchase_invoice_evidence_input,
)
from ._evidence_reference import (
    EvidenceReferenceOutcome,
    classify_evidence_reference,
    find_bytes_bearing_evidence_record,
    refuse_reference_without_document_bytes,
    refuse_unresolved_evidence_reference,
)
from ._evidence_textlayer import extract_evidence_text

__all__ = [
    "InvoiceConfirmationResult",
    "InvoiceDraft",
    "confirm_invoice_draft_from_evidence",
    "extract_invoice_draft_from_evidence",
    "extract_invoice_fields",
]

# A Spanish NIF / NIE / CIF token: 8 digits + letter, or a leading letter
# (K/L/M for NIF, X/Y/Z for NIE, A-H/J/N/P-S/U/V/W for CIF) + 7 digits + a
# trailing letter or digit control character. Matched case-insensitively and
# tolerant of embedded spaces/dashes, which the validator itself strips.
_TAX_ID_RE = re.compile(
    r"\b([A-Za-z][ -]?\d[ -]?\d[ -]?\d[ -]?\d[ -]?\d[ -]?\d[ -]?\d[ -]?[A-Za-z0-9]|\d{8}[A-Za-z])\b",
)

# A Spanish day-first date: DD-MM-YYYY or DD/MM/YYYY.
_DATE_RE = re.compile(r"\b(\d{2}[-/]\d{2}[-/]\d{4})\b")

# Labels that precede an invoice number in Spanish invoice layouts.
_INVOICE_NUMBER_LABEL_RE = re.compile(
    r"(?:n[uú]mero\s+de\s+factura|n[uº°]\.?\s*factura|factura\s+n[uº°]\.?|invoice\s*(?:no\.?|number|#))"
    r"\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9/_.-]{1,29})",
    re.IGNORECASE,
)

# Labels that precede the taxable base ("base imponible").
_BASE_LABEL_RE = re.compile(
    r"base\s+imponible\s*[:\-]?\s*(\d{1,3}(?:\.\d{3})*,\d{2})",
    re.IGNORECASE,
)

# Labels that precede the IVA cuota amount.
_IVA_AMOUNT_LABEL_RE = re.compile(
    r"(?:cuota\s+(?:de\s+)?iva|iva\s+repercutido|iva)\s*[:\-]?\s*(\d{1,3}(?:\.\d{3})*,\d{2})",
    re.IGNORECASE,
)

# Labels that precede the invoice grand total.
_TOTAL_LABEL_RE = re.compile(
    r"(?:total\s+factura|importe\s+total|total\s+a\s+pagar|total)\s*[:\-]?\s*(\d{1,3}(?:\.\d{3})*,\d{2})",
    re.IGNORECASE,
)

# An IVA rate percentage, e.g. "IVA 21%" or "IVA (21%)".
_IVA_RATE_RE = re.compile(r"\biva\b[^%\n]{0,12}?(\d{1,2}(?:[.,]\d{1,2})?)\s*%", re.IGNORECASE)

# An explicit ISO-4217 code printed beside an amount. Only the alphabetic code
# is matched, never a symbol: "$" is ambiguous across USD/CAD/AUD/MXN and "kr"
# across the Nordic currencies, so a symbol cannot ground a currency fact.
_CURRENCY_CODE_RE = re.compile(
    r"(?<![A-Za-z])(EUR|USD|GBP|CHF|SEK|NOK|DKK|PLN|CZK|JPY|CAD|AUD)(?![A-Za-z])",
    re.IGNORECASE,
)


class InvoiceDraft(BaseModel):
    """Best-effort invoice fields extracted from an on-host PDF text layer.

    Every field is optional: a field the extractor cannot ground in the
    document's text is left ``None`` rather than guessed. The operator reviews
    this draft and supplies or corrects fields before any
    :class:`~domain.invoices.Invoice` is minted from it -- this model is
    never itself persisted as a filing-grade record.

    Attributes:
        supplier_tax_id: Canonical Spanish NIF / NIE / CIF recovered from the
            text, or ``None`` when no valid tax identifier was found.
        invoice_number: Invoice number recovered from a labelled line, or
            ``None``.
        invoice_date: Day-first invoice date recovered from the text, or
            ``None``.
        taxable_base: Labelled "base imponible" amount, or ``None``.
        iva_rate: IVA percentage recovered from a "IVA NN%" label, expressed
            as a whole-number :class:`~decimal.Decimal` (e.g. ``21``), or
            ``None``.
        iva_amount: Labelled IVA cuota amount, or ``None``.
        grand_total: Labelled invoice total amount, or ``None``.
        currency: ISO-4217 code for the currency the amounts are printed in,
            or ``None`` when the document shows no currency marker. Left
            ``None`` rather than defaulted to euro: a foreign-currency
            invoice silently read as euro would carry its face value into a
            filing unconverted, so an absent marker must stay absent and be
            resolved by the operator.
        raw_text_length: Length of the on-host extracted text, kept as an
            honest signal of how much source material the heuristics had to
            work with (zero means the PDF carried no usable text layer for
            this evidence and the operator should route to the on-host vision
            reader instead).
    """

    model_config = STRICT_FROZEN_CONFIG

    supplier_tax_id: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    taxable_base: Decimal | None = None
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None
    grand_total: Decimal | None = None
    currency: str | None = None
    raw_text_length: int = 0


def _find_currency(text: str) -> str | None:
    """Return the single ISO-4217 code printed in *text*, or ``None``.

    Grounds a currency only when the document is unambiguous: exactly one
    distinct code appears. A document showing two codes (an invoice quoting a
    foreign total beside its euro equivalent) cannot be resolved from the text
    alone, so the heuristic declines rather than picking the first match and
    silently mis-denominating a filing amount. An absent code stays ``None``
    for the operator to resolve; it is never defaulted to euro.
    """
    found = {match.group(1).upper() for match in _CURRENCY_CODE_RE.finditer(text)}
    if len(found) != 1:
        return None
    return found.pop()


def _find_supplier_tax_id(text: str) -> str | None:
    """Return the first substring in *text* that validates as a Spanish tax id.

    Scans every candidate match in document order and returns the first one
    that passes the AEAT checksum algorithm, so a false-positive token (an
    invoice number or a phone number that happens to match the coarse shape)
    is silently skipped rather than fabricating a wrong identifier.
    """
    for match in _TAX_ID_RE.finditer(text):
        candidate = match.group(1)
        try:
            return validate_spanish_tax_id(candidate)
        except IdentityError:
            continue
    return None


def _find_invoice_number(text: str) -> str | None:
    match = _INVOICE_NUMBER_LABEL_RE.search(text)
    if match is None:
        return None
    return match.group(1).strip()


def _find_invoice_date(text: str) -> str | None:
    for match in _DATE_RE.finditer(text):
        parsed = parse_date(match.group(1), fmt="ddmmyyyy", on_error="none")
        if parsed is not None:
            return parsed.isoformat()
    return None


def _parse_labelled_amount(pattern: re.Pattern[str], text: str) -> Decimal | None:
    match = pattern.search(text)
    if match is None:
        return None
    normalized = normalize_decimal_separators(match.group(1), strip_thousands=True)
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def _find_iva_rate(text: str) -> Decimal | None:
    match = _IVA_RATE_RE.search(text)
    if match is None:
        return None
    normalized = match.group(1).replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def extract_invoice_fields(evidence: EvidenceInput) -> InvoiceDraft:
    """Return a best-effort :class:`InvoiceDraft` extracted from *evidence*.

    Runs the on-host pdfplumber text-layer extractor over the evidence's
    in-memory bytes and applies grounded regex heuristics scoped to Spanish
    invoice layouts. A field the heuristics cannot ground in the extracted
    text is left ``None``; nothing is fabricated.

    Args:
        evidence: Resolved in-memory evidence bytes (already read from secure
            storage by the caller).

    Returns:
        :class:`InvoiceDraft` carrying every field the heuristics could
        ground, with ``raw_text_length`` recording how much text the on-host
        extractor recovered.

    Raises:
        PurchaseInvoiceEvidenceInputError: When the evidence is not a PDF, or
            the PDF has no usable text layer (scan-only / XFA) -- the caller
            should fall back to the on-host vision reader in that case.
    """
    text = extract_evidence_text(evidence)
    return InvoiceDraft(
        supplier_tax_id=_find_supplier_tax_id(text),
        invoice_number=_find_invoice_number(text),
        invoice_date=_find_invoice_date(text),
        taxable_base=_parse_labelled_amount(_BASE_LABEL_RE, text),
        iva_rate=_find_iva_rate(text),
        iva_amount=_parse_labelled_amount(_IVA_AMOUNT_LABEL_RE, text),
        grand_total=_parse_labelled_amount(_TOTAL_LABEL_RE, text),
        currency=_find_currency(text),
        raw_text_length=len(text),
    )


def extract_invoice_draft_from_evidence(
    *,
    bucket_id: str,
    evidence_id: str | None = None,
    attachment_id: str | None = None,
    settings: Settings | None = None,
) -> InvoiceDraft:
    """Resolve one stored evidence reference to bytes and extract its :class:`InvoiceDraft`.

    The CLI-facing wiring layer over :func:`extract_invoice_fields`: given
    either a ``purchase_invoice_evidence`` id (looked up through
    :class:`PurchaseInvoiceEvidenceService`) or a linked ``attachment_id``,
    reads the evidence's bytes from secure storage into memory
    (the private evidence-input resolvers
    :func:`~application.ledger._evidence_input.resolve_purchase_invoice_evidence_input`
    and
    :func:`~application.ledger._evidence_input.resolve_attachment_evidence_input`)
    and runs the on-host extractor over them. Exactly one of *evidence_id* /
    *attachment_id* must be supplied.

    Nothing is written to disk and nothing leaves the host: the resolved
    bytes and the extracted text stay in process memory for the duration of
    this call (``sensitive-financial-data-secure-storage-only``).

    Args:
        bucket_id: Active ledger bucket the evidence or attachment belongs to.
        evidence_id: A ``purchase_invoice_evidence`` record id, or ``None``.
        attachment_id: A linked attachment id, or ``None``.
        settings: Resolved ``Settings``. When ``None``, ``load_settings()`` is
            used so test overrides via ``override_settings()`` are honoured.

    Returns:
        :class:`InvoiceDraft`: The best-effort extracted fields, for operator
        review. Never itself persisted as an :class:`~domain.invoices.Invoice`.

    Raises:
        PurchaseInvoiceEvidenceInputError: When neither or both of
            *evidence_id* / *attachment_id* are supplied, when *evidence_id*
            resolves outside the bytes-bearing evidence-record id space (a
            catalogue-invoice id carries fiscal totals, not a document), when the
            resolved evidence's media type is unsupported, or when a scan-only
            PDF / image falls back to the on-host vision reader and that reader
            is disabled for the profile or the local Ollama runtime is
            unreachable.
    """
    if (evidence_id is None) == (attachment_id is None):
        raise PurchaseInvoiceEvidenceInputError(
            "exactly one of evidence_id or attachment_id must be supplied",
            suggestion="aeat app ledger evidence list",
        )

    resolved_settings = settings or _load_settings()
    store = AttachmentStore(objects=secure_object_repository_for_bucket(bucket_id, resolved_settings))
    if evidence_id is not None:
        # Both id spaces are consulted so the refusal can be precise: only the
        # evidence-record space carries document bytes, but a catalogue-invoice id is
        # a legitimate reference that simply has no document behind it, and must not
        # be reported as a missing record.
        reference = classify_evidence_reference(
            evidence_id,
            bucket_id=bucket_id,
            evidence_records=PurchaseInvoiceEvidenceService(settings=resolved_settings).list_all(bucket_id=bucket_id),
            invoices=InvoiceCatalogueRepository(bucket_id=bucket_id).load(),
        )
        if reference.outcome is EvidenceReferenceOutcome.UNRESOLVED:
            raise refuse_unresolved_evidence_reference(evidence_id)
        if reference.record is None:
            raise refuse_reference_without_document_bytes(evidence_id)
        evidence_input = resolve_purchase_invoice_evidence_input(reference.record, store=store)
    else:
        assert attachment_id is not None  # narrowed by the exactly-one guard above
        evidence_input = resolve_attachment_evidence_input(attachment_id, store=store)

    if evidence_input.media_kind is MediaKind.PDF:
        try:
            return extract_invoice_fields(evidence_input)
        except PurchaseInvoiceEvidenceInputError:
            # No usable text layer (scan-only / XFA) -> on-host vision fallback below.
            pass
    return _extract_invoice_fields_via_vision(evidence_input, settings=resolved_settings)


def _extract_invoice_fields_via_vision(evidence: EvidenceInput, *, settings: Settings) -> InvoiceDraft:
    """Rasterise/encode *evidence* and read it with the on-host local vision model.

    Gated by :attr:`~core.ServiceCapability.LLM_VISION` -- an operator who has
    opted out gets a typed refusal naming the capability toggle, never a silent
    empty draft. A missing/unreachable local Ollama runtime, or an unrasterisable
    PDF, is converted to the same instructive refusal the classification vision
    path uses (:func:`~application.provisioning.probe_ollama_vision`).
    """
    import httpx

    if not resolve_active_capability(ServiceCapability.LLM_VISION, settings=settings).enabled:
        raise PurchaseInvoiceEvidenceInputError(
            "on-host LLM vision reading is disabled for this profile; enable it to read a scan-only "
            "PDF or image evidence",
            suggestion="aeat config profile capabilities set llm_vision on",
        )

    try:
        from ._evidence_draft_vision import extract_invoice_fields_from_images

        if evidence.media_kind is MediaKind.PDF:
            images = rasterise_pdf_pages_to_base64_png(evidence.data)
        else:
            import base64

            images = (base64.b64encode(evidence.data).decode("ascii"),)
        return extract_invoice_fields_from_images(images, settings=settings)
    except (httpx.HTTPError, LLMProviderError, LLMPdfRasterisationError) as exc:
        status = probe_ollama_vision(settings)
        fix = status.remediation or "ensure the local Ollama vision model is reachable"
        detail = status.detail if not status.available else str(exc)
        raise PurchaseInvoiceEvidenceInputError(
            f"on-host vision reading failed: {detail}. Fix: {fix}",
            suggestion=fix,
        ) from exc


class InvoiceConfirmationResult(BaseModel):
    """Outcome of confirming a reviewed :class:`InvoiceDraft` into an :class:`Invoice`.

    Attributes:
        invoice: The persisted (or already-existing, on a guarded no-op)
            :class:`~domain.invoices.Invoice`.
        draft: The re-run on-host extraction the confirmation was based on
            (before overrides were applied), kept so the operator can see what
            was actually read from the document versus what they overrode.
        created: ``True`` when this call minted a new catalogue row;
            ``False`` when an invoice with the identical derived identity
            already existed and this call returned it unchanged (the guarded
            idempotent-retry no-op).
    """

    model_config = STRICT_FROZEN_CONFIG

    invoice: Invoice
    draft: InvoiceDraft
    created: bool


def _require_confirmed_field(value: Decimal | str | None, *, field: str) -> Decimal | str:
    if value is None:
        raise PurchaseInvoiceEvidenceInputError(
            f"cannot confirm an invoice: {field} could not be extracted and no --{field.replace('_', '-')} "
            "override was supplied",
            suggestion=(
                "aeat app ledger evidence extract --evidence-id <id>  # review the draft, then re-run confirm "
                f"with an explicit --{field.replace('_', '-')} override"
            ),
        )
    return value


def confirm_invoice_draft_from_evidence(
    *,
    bucket_id: str,
    kind: InvoiceKind,
    counterparty_country: str = "ES",
    evidence_id: str | None = None,
    attachment_id: str | None = None,
    counterparty_tax_id: str | None = None,
    counterparty_name: str | None = None,
    invoice_number: str | None = None,
    invoice_date: date | None = None,
    taxable_base: Decimal | None = None,
    iva_rate: Decimal | None = None,
    currency: str | None = None,
    notes: str = "",
    settings: Settings | None = None,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
) -> InvoiceConfirmationResult:
    """Re-extract one evidence reference and confirm it into a real :class:`Invoice`.

    Re-runs :func:`extract_invoice_draft_from_evidence` on-host (bytes and text
    stay in memory only), then layers any operator-supplied override on top of
    each extracted field -- extraction is best-effort, so every field may be
    corrected before the record is minted. The resulting identity fields are
    handed to :func:`~application.invoices.create_catalogue_invoice`, the
    single sanctioned :class:`Invoice` writer
    (``composition-service-no-parallel-write-path``); this function never
    writes the catalogue itself.

    Idempotent-guarded (``single-subject-mutation-is-idempotent-guarded``): the
    persisted :attr:`~domain.invoices.Invoice.invoice_id` is a stable hash of
    ``(kind, invoice_number, issued_at, counterparty_tax_id, currency,
    grand_total)`` — a confirm carrying identical resolved fields to an
    already-persisted invoice returns that invoice unchanged
    (``created=False``, no new bucket write); a confirm whose resolved fields
    genuinely differ mints a distinct invoice record rather than overwriting.

    Args:
        bucket_id: Active ledger bucket the evidence belongs to.
        kind: Invoice direction (``issued`` or ``received``) — extraction
            cannot infer this; the operator must state it.
        counterparty_country: ISO 3166-1 alpha-2 counterparty country code.
            Defaults to ``"ES"``; override for a non-Spanish counterparty.
        evidence_id: A ``purchase_invoice_evidence`` record id, or ``None``.
        attachment_id: A linked attachment id, or ``None``. Exactly one of
            *evidence_id* / *attachment_id* must be supplied.
        counterparty_tax_id: Override for the extracted supplier tax id.
        counterparty_name: Override (there is no extraction heuristic for the
            counterparty's display name yet, so this is normally required).
        invoice_number: Override for the extracted invoice number.
        invoice_date: Override for the extracted invoice date.
        taxable_base: Override for the extracted taxable base.
        iva_rate: Override for the extracted IVA rate (``None`` resolves to
            the EXEMPT slot, matching :func:`build_catalogue_invoice`).
        currency: ISO-4217 currency code overriding the extracted one.
            When omitted, the currency printed on the document is used,
            falling back to euro only when the document shows none.
        notes: Free-text operator notes carried onto the invoice.
        settings: Resolved ``Settings``; ``load_settings()`` when ``None``.
        invoice_repository: Optional injected
            :class:`InvoiceCatalogueRepositoryProtocol` (testing seam).

    Returns:
        :class:`InvoiceConfirmationResult`: The persisted (or pre-existing)
        invoice, the re-run draft it was checked against, and whether this
        call minted a new record.

    Raises:
        PurchaseInvoiceEvidenceInputError: When neither or both of
            *evidence_id* / *attachment_id* are supplied, when *evidence_id*
            resolves outside the bytes-bearing evidence-record id space, when the
            resolved evidence has no usable text layer, or when a required field
            is ``None`` after overrides (extraction found nothing and the
            operator supplied no override).
        InvoiceValidationError: When the resolved fields fail invoice-model
            validation (e.g. an invalid counterparty tax id or IVA rate).
    """
    resolved_settings = settings or _load_settings()
    draft = extract_invoice_draft_from_evidence(
        bucket_id=bucket_id,
        evidence_id=evidence_id,
        attachment_id=attachment_id,
        settings=resolved_settings,
    )
    resolved_attachment_id = _resolve_evidence_attachment_id(
        bucket_id=bucket_id,
        evidence_id=evidence_id,
        attachment_id=attachment_id,
        settings=resolved_settings,
    )

    resolved_counterparty_tax_id = _require_confirmed_field(
        counterparty_tax_id if counterparty_tax_id is not None else draft.supplier_tax_id,
        field="counterparty_tax_id",
    )
    assert isinstance(resolved_counterparty_tax_id, str)
    resolved_invoice_number = _require_confirmed_field(
        invoice_number if invoice_number is not None else draft.invoice_number,
        field="invoice_number",
    )
    assert isinstance(resolved_invoice_number, str)
    resolved_invoice_date = _resolve_confirmed_invoice_date(invoice_date, draft)
    resolved_taxable_base = _require_confirmed_field(
        taxable_base if taxable_base is not None else draft.taxable_base,
        field="taxable_base",
    )
    assert isinstance(resolved_taxable_base, Decimal)
    resolved_iva_rate = iva_rate if iva_rate is not None else draft.iva_rate
    # Same override-on-extraction layering as every other field: an explicit
    # operator value wins, else the currency actually printed on the document,
    # else euro. Preferring the extracted code over the euro default is what
    # stops a foreign-currency invoice being minted at its face value in euro.
    resolved_currency = (currency or draft.currency or DEFAULT_CURRENCY).strip().upper()
    resolved_counterparty_name = (counterparty_name or "").strip()
    if not resolved_counterparty_name:
        raise PurchaseInvoiceEvidenceInputError(
            "cannot confirm an invoice: counterparty_name has no extraction heuristic yet and "
            "no --counterparty-name override was supplied",
            suggestion="aeat app ledger evidence extract --evidence-id <id>",
        )

    repository = invoice_repository or InvoiceCatalogueRepository(bucket_id=bucket_id)
    candidate = build_catalogue_invoice(
        bucket_id=bucket_id,
        kind=kind,
        counterparty_name=resolved_counterparty_name,
        counterparty_tax_id=resolved_counterparty_tax_id,
        counterparty_country=counterparty_country,
        invoice_number=resolved_invoice_number,
        issued_at=resolved_invoice_date,
        taxable_base=resolved_taxable_base,
        iva_rate=resolved_iva_rate,
        currency=resolved_currency,
        notes=notes,
    )
    attachment_store = AttachmentStore(objects=secure_object_repository_for_bucket(bucket_id, resolved_settings))
    catalogue = repository.load()
    existing = catalogue.get(candidate.invoice_id)
    if existing is not None:
        # Guarded idempotent retry (single-subject-mutation-is-idempotent-guarded):
        # the confirm's resolved identity fields hash to an invoice already in the
        # catalogue -- return it unchanged rather than raising or re-writing. The
        # source evidence link is re-asserted (a no-op when already present,
        # `link_attachment_invoice` dedups) so a re-confirm never regresses the
        # provenance link even if it was never wired for this evidence before.
        link_attachment_invoice(attachment_store, attachment_id=resolved_attachment_id, invoice_id=existing.invoice_id)
        return InvoiceConfirmationResult(invoice=existing, draft=draft, created=False)

    result = create_catalogue_invoice(
        bucket_id=bucket_id,
        kind=kind,
        counterparty_name=resolved_counterparty_name,
        counterparty_tax_id=resolved_counterparty_tax_id,
        counterparty_country=counterparty_country,
        invoice_number=resolved_invoice_number,
        issued_at=resolved_invoice_date,
        taxable_base=resolved_taxable_base,
        iva_rate=resolved_iva_rate,
        currency=resolved_currency,
        notes=notes,
        repository=repository,
    )
    # Auto-link the source evidence/attachment to the newly minted invoice, closing
    # the provenance loop: the invoice is now discoverable from the evidence
    # (`Attachment.linked_invoice_ids`) and vice versa (`Invoice.invoice_id` is what
    # was just recorded). `link_attachment_invoice` re-persists through the same
    # sanctioned `AttachmentStoreProtocol.write_manifest` path
    # (`composition-service-no-parallel-write-path`); it never re-implements the
    # attachment write.
    link_attachment_invoice(
        attachment_store,
        attachment_id=resolved_attachment_id,
        invoice_id=result.invoice.invoice_id,
    )
    return InvoiceConfirmationResult(invoice=result.invoice, draft=draft, created=True)


def _resolve_confirmed_invoice_date(invoice_date: date | None, draft: InvoiceDraft) -> date:
    if invoice_date is not None:
        return invoice_date
    if draft.invoice_date is not None:
        parsed = parse_iso8601_date(draft.invoice_date)
        if parsed is not None:
            return parsed
    raise PurchaseInvoiceEvidenceInputError(
        "cannot confirm an invoice: invoice_date could not be extracted and no --invoice-date override was supplied",
        suggestion="aeat app ledger evidence extract --evidence-id <id>",
    )


def _resolve_evidence_attachment_id(
    *,
    bucket_id: str,
    evidence_id: str | None,
    attachment_id: str | None,
    settings: Settings,
) -> str:
    """Return the in-store ``attachment_id`` backing one evidence reference.

    Mirrors the exactly-one-of resolution
    :func:`~application.ledger.extract_invoice_draft_from_evidence` already
    enforces (that call already ran, so the invariant holds here too): when
    *attachment_id* is supplied directly it is returned unchanged; when
    *evidence_id* is supplied, the linked ``purchase_invoice_evidence`` record's own
    :attr:`~._evidence.PurchaseInvoiceEvidence.attachment_id` is looked up, which is
    a required field and so always names an in-store byte home.

    Resolves the reference through the same
    :func:`~application.ledger._evidence_reference.find_bytes_bearing_evidence_record`
    the extraction path used, so the confirm step cannot decide the id belongs to a
    different space than the extraction did.
    """
    if attachment_id is not None:
        return attachment_id
    assert evidence_id is not None  # narrowed by the caller's exactly-one guard
    record = find_bytes_bearing_evidence_record(
        evidence_id,
        evidence_records=PurchaseInvoiceEvidenceService(settings=settings).list_all(bucket_id=bucket_id),
    )
    if record is None:
        raise refuse_reference_without_document_bytes(evidence_id)
    return record.attachment_id
