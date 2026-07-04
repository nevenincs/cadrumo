"""On-host invoice-PDF field extraction into a typed draft.

Given an ``EvidenceInput`` already resolved from secure storage (see
:mod:`._evidence_input`), :func:`extract_invoice_fields` runs the in-tree
on-host text-layer extractor (:func:`._evidence_textlayer.extract_evidence_text`)
and applies grounded heuristics -- the shared Spanish tax-id validator
(:func:`aeat.core.identity.validate_spanish_tax_id`), the shared day-first date
parser (:func:`aeat.core.parsing.parse_date`), and the shared European decimal
separator normaliser (:func:`aeat.core.decimal.normalize_decimal_separators`) --
to recover a supplier NIF/NIE/CIF, invoice number, invoice date, taxable base,
IVA rate, IVA amount, and grand total.

This is the extraction PRIMITIVE only: it returns an :class:`InvoiceDraft` the
operator reviews and confirms. It never persists an :class:`aeat.domain.invoices.Invoice`
and never guesses a value it cannot ground in the extracted text -- every field
it cannot recover is left ``None`` rather than fabricated
(``no-silent-under-declaration`` in spirit: an unconfident field is absent, not
invented).

Everything here runs on-host and in-memory only. The evidence bytes and the
extracted text never touch disk and are never sent to a cloud provider or an
LLM (``sensitive-financial-data-secure-storage-only``,
``2026-06-10-llm-evidence-classification-adr``). This module makes no network
call and performs no filesystem write.

:func:`extract_invoice_draft_from_evidence` is the CLI-facing wiring layer: it
resolves an already-stored ``purchase_invoice_evidence`` record or a linked
``attachment_id`` to its in-memory bytes (through
:func:`._evidence_input.resolve_purchase_invoice_evidence_input` /
:func:`._evidence_input.resolve_attachment_evidence_input`) and runs
:func:`extract_invoice_fields` over them, so ``aeat app ledger evidence extract``
needs only a bucket id plus one of the two reference ids.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG
from ...core.config import Settings
from ...core.decimal import normalize_decimal_separators
from ...core.identity import IdentityError, validate_spanish_tax_id
from ...core.parsing import parse_date
from ._evidence import PurchaseInvoiceEvidenceInputError, PurchaseInvoiceEvidenceService
from ._evidence_input import (
    EvidenceInput,
    resolve_attachment_evidence_input,
    resolve_purchase_invoice_evidence_input,
)
from ._evidence_textlayer import extract_evidence_text

__all__ = ["InvoiceDraft", "extract_invoice_draft_from_evidence", "extract_invoice_fields"]

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


class InvoiceDraft(BaseModel):
    """Best-effort invoice fields extracted from an on-host PDF text layer.

    Every field is optional: a field the extractor cannot ground in the
    document's text is left ``None`` rather than guessed. The operator reviews
    this draft and supplies or corrects fields before any
    :class:`aeat.domain.invoices.Invoice` is minted from it -- this model is
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
    raw_text_length: int = 0


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
    (:func:`._evidence_input.resolve_purchase_invoice_evidence_input` /
    :func:`._evidence_input.resolve_attachment_evidence_input`) and runs the
    on-host extractor over them. Exactly one of *evidence_id* /
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
        review. Never itself persisted as an :class:`aeat.domain.invoices.Invoice`.

    Raises:
        PurchaseInvoiceEvidenceInputError: When neither or both of
            *evidence_id* / *attachment_id* are supplied, when the resolved
            evidence is not a PDF, or when the PDF has no usable text layer
            (scan-only / XFA) -- the caller should fall back to the on-host
            vision reader in that case.
        PurchaseInvoiceEvidenceNotFoundError: When *evidence_id* names no
            record in *bucket_id*.
    """
    from ...adapters.persistence.storage import AttachmentStore, secure_object_repository_for_bucket
    from ...core.config import load_settings as _load_settings

    if (evidence_id is None) == (attachment_id is None):
        raise PurchaseInvoiceEvidenceInputError(
            "exactly one of evidence_id or attachment_id must be supplied",
            suggestion="aeat app ledger evidence list",
        )

    resolved_settings = settings or _load_settings()
    store = AttachmentStore(objects=secure_object_repository_for_bucket(bucket_id, resolved_settings))
    if evidence_id is not None:
        record = PurchaseInvoiceEvidenceService(settings=resolved_settings).view(
            bucket_id=bucket_id,
            evidence_id=evidence_id,
        )
        evidence_input = resolve_purchase_invoice_evidence_input(record, store=store)
    else:
        assert attachment_id is not None  # narrowed by the exactly-one guard above
        evidence_input = resolve_attachment_evidence_input(attachment_id, store=store)
    return extract_invoice_fields(evidence_input)
