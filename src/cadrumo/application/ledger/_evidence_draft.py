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
on-host LOCAL vision reader (:mod:`~llm._evidence_draft_vision`)
-- the same rasterise-then-read-with-Ollama transport
:class:`~llm._vision_classifier.LocalVisionLLMClassifier` already
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
(``aeat-architecture-boundaries``). A confirm keyed on the same
evidence/attachment reference and the same resolved fields is a guarded no-op
that returns the existing invoice rather than raising or duplicating
(``aeat-cli-contract``); a same-reference confirm
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
    :mod:`~llm._evidence_draft_vision`
        On-host vision fallback for scan-only PDFs and image attachments.
    :func:`~application.invoices.create_catalogue_invoice`
        Sole sanctioned writer for the resulting catalogue invoice.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from ...adapters.inbound.einvoice import EInvoiceXmlParseError, parse_einvoice_document
from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.storage import AttachmentStore, secure_object_repository_for_bucket
from ...application.invoices import build_catalogue_invoice, create_catalogue_invoice, resolve_iva_rate_slot
from ...core import (
    STRICT_FROZEN_CONFIG,
    STRUCTURED_DOCUMENT_SHAPES,
    ImageMediaType,
    MissingOptionalExtraError,
    ServiceCapability,
    detect_image_media_type,
)
from ...core.config import Settings
from ...core.config import load_settings as _load_settings
from ...core.decimal import coerce_finite_european_decimal
from ...core.external_constants import DEFAULT_CURRENCY, XML_MIME_TYPE
from ...core.identity import IdentityError, tax_id_identity_token, validate_spanish_tax_id
from ...core.parsing import parse_date, parse_iso8601_date
from ...domain.attachments import link_attachment_invoice, normalize_media_type
from ...domain.invoices import Invoice, InvoiceCatalogueRepositoryProtocol, InvoiceClass, InvoiceLine
from ...domain.iva import InvoiceKind, IvaCategory
from ...llm import (
    LLMPdfRasterisationError,
    LLMProviderError,
    MultimodalImageInput,
    rasterise_pdf_pages_to_base64_png,
)
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
    "InvoiceDraftLine",
    "InvoiceDraftRateBreakdown",
    "PrintedTotalDiscrepancy",
    "confirm_invoice_draft_from_evidence",
    "extract_invoice_draft_from_evidence",
    "extract_invoice_fields",
    "printed_total_discrepancy",
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


class InvoiceDraftLine(BaseModel):
    """One line item recovered from a structured invoice document.

    Only a structured reader can populate this: a regex or vision reader
    recovers printed totals, not the document's own line decomposition. The
    rate is carried as a bare percentage :class:`~decimal.Decimal` (``21``, not
    ``0.21``) because the draft is pre-confirm operator-facing data; mapping it
    onto the closed ``IvaRate`` slot enum happens at the parse boundary, which
    refuses loudly rather than rounding to the nearest slot.

    Attributes:
        description: Line description as printed, or ``None``.
        quantity: Billed quantity, or ``None`` when the document omits it.
        unit_price: Price per unit before tax, or ``None``.
        taxable_base: Line taxable base before IVA.
        iva_rate: Line IVA percentage as a whole-number Decimal.
        iva_amount: Line IVA cuota, or ``None`` when the document states only
            the rate and lets the total carry the cuota.
        recargo_rate: Recargo de equivalencia percentage, or ``None``.
        recargo_amount: Recargo de equivalencia cuota, or ``None``.
    """

    model_config = STRICT_FROZEN_CONFIG

    description: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    taxable_base: Decimal | None = None
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None
    recargo_rate: Decimal | None = None
    recargo_amount: Decimal | None = None


class InvoiceDraftRateBreakdown(BaseModel):
    """Per-rate tax subtotal as the document itself declares it.

    This is the field that makes the multi-rate silent collapse detectable. A
    draft carrying only the flat ``taxable_base`` / ``iva_rate`` /
    ``iva_amount`` triple structurally cannot represent an invoice charging
    two rates: the two bases sum into one figure and one of the rates is simply
    lost, producing an invoice whose printed total no longer reconciles with
    its declared cuota.

    Attributes:
        iva_rate: The rate this subtotal is charged at, as a whole-number
            percentage Decimal.
        taxable_base: Base charged at this rate.
        iva_amount: Cuota charged at this rate.
        recargo_rate: Recargo de equivalencia percentage for this rate.
        recargo_amount: Recargo de equivalencia cuota for this rate.
    """

    model_config = STRICT_FROZEN_CONFIG

    iva_rate: Decimal | None = None
    taxable_base: Decimal | None = None
    iva_amount: Decimal | None = None
    recargo_rate: Decimal | None = None
    recargo_amount: Decimal | None = None


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
        supplier_name: The issuing party's stated name, or ``None``.
        customer_tax_id: The receiving party's tax identifier, or ``None``.
            Populated only by a structured reader, which is the only one that
            can tell the two parties apart; a text or vision reader recovers a
            single identifier and cannot say whose it is.
        customer_name: The receiving party's stated name, or ``None``.
        invoice_number: Invoice number recovered from a labelled line, or
            ``None``.
        invoice_series: The series half of the invoice's identity, stated
            separately by Facturae as ``InvoiceSeriesCode``, or ``None``. Kept
            beside the number rather than concatenated into it: composing the
            printed reference from the two is always possible, while splitting a
            composed string back into them is not.
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
    supplier_name: str | None = None
    customer_tax_id: str | None = None
    customer_name: str | None = None
    invoice_number: str | None = None
    invoice_series: str | None = None
    invoice_date: str | None = None
    taxable_base: Decimal | None = None
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None
    grand_total: Decimal | None = None
    currency: str | None = None
    recargo_amount: Decimal | None = None
    lines: tuple[InvoiceDraftLine, ...] = ()
    iva_breakdown: tuple[InvoiceDraftRateBreakdown, ...] = ()
    iva_category: str | None = None
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
    """Return the labelled amount captured from the text layer, or ``None``.

    Shares the finite European-decimal authority with the vision adapter, so
    the two extraction paths cannot read the same invoice differently: an
    already dot-decimal amount keeps its scale and a non-finite token is
    refused rather than becoming a filing figure.
    """
    match = pattern.search(text)
    if match is None:
        return None
    return coerce_finite_european_decimal(match.group(1))


def _find_iva_rate(text: str) -> Decimal | None:
    """Return the IVA rate captured from the text layer, or ``None``.

    Routes through the same finite European-decimal authority as
    :func:`_parse_labelled_amount` above. This previously hand-rolled the
    comma-to-dot swap, which agreed with the authority only because
    :data:`_IVA_RATE_RE` caps its capture at two digits and a two-digit
    fraction -- no thousands separator or non-finite token could reach it. That
    made the regex load-bearing for the parse's correctness, silently: widening
    the pattern would have diverged two extractors eight lines apart, and a
    wrong IVA rate surfaces on a filed form rather than at the parse.
    """
    match = _IVA_RATE_RE.search(text)
    if match is None:
        return None
    return coerce_finite_european_decimal(match.group(1))


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

    # Routing order, and the order is itself a control rather than an
    # optimisation: a document carrying a STRUCTURED record is read exactly and
    # reaches no model at all, which makes prompt injection categorically
    # impossible for that document rather than merely mitigated. The decision is
    # made on DocumentShape -- derived from the bytes -- because the stored MIME
    # type answers "pdf" for a ZUGFeRD invoice and a photograph alike, which is
    # how the most machine-readable document in the corpus ended up on the least
    # exact path.
    if evidence_input.document_shape in STRUCTURED_DOCUMENT_SHAPES:
        try:
            return _extract_invoice_fields_from_structured_record(evidence_input)
        except EInvoiceXmlParseError:
            # A malformed structured record refuses rather than yielding a
            # partial one; fall through so a document whose embedded payload is
            # broken can still be read by the text or vision path.
            pass
    _refuse_an_unrecognised_xml_document(evidence_input)
    if evidence_input.media_kind is MediaKind.PDF:
        try:
            return extract_invoice_fields(evidence_input)
        except PurchaseInvoiceEvidenceInputError:
            # No usable text layer (scan-only / XFA) -> on-host vision fallback below.
            pass
    return _extract_invoice_fields_via_vision(evidence_input, settings=resolved_settings)


def _refuse_an_unrecognised_xml_document(evidence: EvidenceInput) -> None:
    """Refuse an XML document whose syntax no structured reader recognises.

    XML must never reach the text-layer or vision fallbacks. Those exist for
    documents whose content is RENDERED -- a PDF's text layer, a photograph of a
    receipt -- and an XML file is neither: extracting prose from markup yields
    tag soup, and rasterising it to read with a vision model is incoherent as
    well as expensive.

    This became reachable only when ``.xml`` was admitted at the evidence gate.
    Before that a structured document could not be ingested at all, so the
    fallback chain was never handed one. Admitting the extension without closing
    the chain would route every unrecognised XML -- a SII or VERI*FACTU record,
    a TicketBAI record, any XML at all -- to the on-host vision model, whose
    capability is ON by default.

    The refusal names the syntaxes that ARE read, so an operator holding a
    document we do not support learns which ones we do rather than watching a
    model fail to read their markup.
    """
    if normalize_media_type(evidence.mime_type) != XML_MIME_TYPE:
        return
    if evidence.document_shape in STRUCTURED_DOCUMENT_SHAPES:
        # Self-contained rather than relying on call position. Today the
        # structured branch returns before reaching here, so this is
        # unreachable in the live routing -- which is precisely why it is
        # asserted: a later refactor that moves this call earlier would
        # otherwise refuse every Facturae, CII and UBL document, and the guard
        # would look correct while removing the capability it protects.
        return
    raise PurchaseInvoiceEvidenceInputError(
        "this XML document carries no invoice record in a syntax this reader knows. Recognised "
        "structured syntaxes are Facturae 3.2.x, EN16931 Cross Industry Invoice (CII) and EN16931 "
        "UBL. AEAT SII and VERI*FACTU submission records are not read as invoice evidence.",
        suggestion="aeat app ledger evidence list",
    )


def _extract_invoice_fields_from_structured_record(evidence: EvidenceInput) -> InvoiceDraft:
    """Read a structured e-invoice exactly into the line-carrying draft.

    No model, no rasterisation, no network. The per-rate breakdown and the line
    set come from the document's own record, which is the whole reason the
    draft grew them: a flat base/rate/cuota triple structurally cannot hold a
    two-rate invoice.
    """
    parsed = parse_einvoice_document(evidence.data)
    return InvoiceDraft(
        supplier_tax_id=parsed.supplier_tax_id,
        supplier_name=parsed.supplier_name,
        customer_tax_id=parsed.customer_tax_id,
        customer_name=parsed.customer_name,
        invoice_number=parsed.invoice_number,
        invoice_series=parsed.invoice_series,
        invoice_date=parsed.invoice_date,
        taxable_base=parsed.taxable_base,
        iva_amount=parsed.iva_amount,
        grand_total=parsed.grand_total,
        currency=parsed.currency,
        recargo_amount=parsed.recargo_amount,
        iva_category=parsed.iva_category,
        lines=tuple(
            InvoiceDraftLine(
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                taxable_base=line.taxable_base,
                iva_rate=line.iva_rate,
                iva_amount=line.iva_amount,
            )
            for line in parsed.lines
        ),
        iva_breakdown=tuple(
            InvoiceDraftRateBreakdown(iva_rate=rate, taxable_base=base, iva_amount=cuota)
            for rate, base, cuota in parsed.iva_breakdown
        ),
        raw_text_length=len(evidence.data),
    )


def _extract_invoice_fields_via_vision(evidence: EvidenceInput, *, settings: Settings) -> InvoiceDraft:
    """Rasterise/encode *evidence* and read it with the on-host local vision model.

    Gated by :attr:`~core.ServiceCapability.LLM_VISION` -- an operator who has
    opted out gets a typed refusal naming the capability toggle, never a silent
    empty draft. A missing/unreachable local Ollama runtime, or an unrasterisable
    PDF, is converted to the same instructive refusal the classification vision
    path uses (:func:`~application.provisioning.probe_ollama_vision`). An absent
    ``llm`` extra is reported separately, with its install hint, so a dependency
    gap is never remediated as a daemon-reachability problem.
    """
    import httpx

    if not resolve_active_capability(ServiceCapability.LLM_VISION, settings=settings).enabled:
        raise PurchaseInvoiceEvidenceInputError(
            "on-host LLM vision reading is disabled for this profile; enable it to read a scan-only "
            "PDF or image evidence",
            suggestion="aeat config profile capabilities set llm_vision on",
        )

    try:
        from ...llm import extract_invoice_fields_from_images

        if evidence.media_kind is MediaKind.PDF:
            images = tuple(
                MultimodalImageInput.from_base64(page, ImageMediaType.PNG)
                for page in rasterise_pdf_pages_to_base64_png(evidence.data)
            )
        else:
            import base64

            # An attachment is whatever format the operator supplied, so the type is
            # detected from the bytes; an unsupported one refuses here rather than
            # travelling to a provider under a guessed label.
            images = (
                MultimodalImageInput.from_base64(
                    base64.b64encode(evidence.data).decode("ascii"),
                    detect_image_media_type(evidence.data),
                ),
            )
        return extract_invoice_fields_from_images(images, settings=settings)
    except MissingOptionalExtraError as exc:
        # Ordered ahead of the runtime-failure branch deliberately. A missing
        # `llm` extra is a dependency problem, not a reachability problem: the
        # branch below probes the Ollama runtime and answers "ensure the local
        # Ollama vision model is reachable", which is the wrong remedy and
        # sends the operator to restart a daemon that was never the fault.
        raise PurchaseInvoiceEvidenceInputError(
            f"on-host vision reading is unavailable: {exc}",
            suggestion=exc.install_hint,
        ) from exc
    except (httpx.HTTPError, LLMProviderError, LLMPdfRasterisationError) as exc:
        status = probe_ollama_vision(settings)
        fix = status.remediation or "ensure the local Ollama vision model is reachable"
        detail = status.detail if not status.available else str(exc)
        raise PurchaseInvoiceEvidenceInputError(
            f"on-host vision reading failed: {detail}. Fix: {fix}",
            suggestion=fix,
        ) from exc


class PrintedTotalDiscrepancy(BaseModel):
    """The document's printed total disagreeing with the total actually recorded.

    The confirm path never persists a model-read or text-read figure as the
    invoice total: ``grand_total`` is DERIVED from the taxable base and the
    registry-resolved rate slot
    (:func:`~application.invoices.build_catalogue_invoice`). That derivation is
    the correct behaviour and this record does not change it -- the printed
    figure stays an advisory cross-check and never overwrites the derived value,
    exactly as the evidence-reading discipline requires.

    What this record adds is the other half of that same discipline: when the
    two disagree, say so. A disagreement is never noise, because the derived
    total is arithmetically fixed at ``base + cuota``; anything the document
    prints beyond that is a component the record could not represent, or a
    misread of one it could:

    - A **recargo de equivalencia** invoice (LIVA art. 161) prints
      ``base + cuota + recargo``. The recargo has nowhere to go on this path,
      so the record silently understates the document by exactly that surcharge.
    - An **unread rate** resolves to :attr:`~domain.invoices.IvaRate.EXEMPT`
      (``iva_rate=None`` is the base-only slot), minting a zero-cuota invoice
      whose printed total still shows the cuota that was charged.
    - A **misread base** propagates into the derived total and diverges from the
      printed one.

    All three are silent under-declarations that the printed total detects for
    free, having already been read. Discarding it unexamined is what let them
    through.

    Attributes:
        printed_total: The total actually printed on the document, as recovered
            by the on-host reader.
        recorded_total: The total derived from the confirmed base and rate slot,
            i.e. what the persisted invoice carries.
        difference: ``printed_total - recorded_total``. Positive means the
            document totals MORE than the record -- the under-declaration
            direction, and the one a recargo produces.
    """

    model_config = STRICT_FROZEN_CONFIG

    printed_total: Decimal
    recorded_total: Decimal
    difference: Decimal


def printed_total_discrepancy(*, draft: InvoiceDraft, invoice: Invoice) -> PrintedTotalDiscrepancy | None:
    """Return the printed-vs-recorded total disagreement, or ``None`` when they agree.

    Compares only when the reader actually recovered a total: a document whose
    total could not be read grounds no cross-check, and reporting a discrepancy
    against an absent figure would manufacture an alert out of missing data
    rather than out of conflicting data.

    Args:
        draft: The extraction the confirmation was based on.
        invoice: The invoice that was persisted (or matched on a guarded no-op).

    Returns:
        :class:`PrintedTotalDiscrepancy` when the document printed a total that
        differs from the recorded one, else ``None``.
    """
    printed = draft.grand_total
    if printed is None:
        return None
    if printed == invoice.grand_total:
        return None
    return PrintedTotalDiscrepancy(
        printed_total=printed,
        recorded_total=invoice.grand_total,
        difference=printed - invoice.grand_total,
    )


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
        total_discrepancy: Set when the document's printed total disagrees with
            the derived total now on record -- see
            :class:`PrintedTotalDiscrepancy` for why that is always worth
            surfacing. ``None`` when they agree or no total was readable. The
            field rides the RESULT rather than being recomputed by each caller
            so a consumer cannot silently omit the check.
    """

    model_config = STRICT_FROZEN_CONFIG

    invoice: Invoice
    draft: InvoiceDraft
    created: bool
    total_discrepancy: PrintedTotalDiscrepancy | None = None


def _agreed_counterparty_tax_id(*, supplied: str | None, extracted: str | None) -> str | None:
    """Resolve the counterparty tax id, refusing a supplied/extracted disagreement.

    Every other field here layers an operator value over the extracted one and
    lets the operator win silently. This one does not, because the extracted
    value is the only field on the draft that nothing else checks: the
    counterparty NAME is supplied by the operator, so a misread name is caught
    by them typing it, while a misread tax id was accepted unseen.

    That matters past tidiness. A received invoice's supplier tax id drives
    deductibility and feeds Modelo 347 per counterparty, so a wrong one reaches
    a filing a human submits. The checksum on
    :func:`~cadrumo.domain.invoices.validate_spanish_tax_id` is the PRIMARY
    defence and it is a strong one -- a transposed digit breaks the check
    character and is refused outright. What it cannot catch is a misread that
    happens to be a different VALID identifier, which belongs to a different
    real taxpayer. This closes that residue.

    Supplying the value is therefore an ASSERTION rather than an override, and
    the difference is what makes it safe: typing to CHECK is not typing to SET.
    A typo here produces a refusal, never a wrong value on a filing -- unlike
    the transcription hazard that was removed from the extract hint, where what
    the operator typed silently became the data.

    Neither value is named in the refusal. The operator already knows the one
    they typed, and the machine only has to answer whether the extractor agrees;
    printing either would put a tax identity into a pasteable artefact for no
    gain.

    Comparison is on :func:`~cadrumo.core.identity.tax_id_identity_token`, the
    canonical "are these the same identifier" form, rather than a local
    trim-and-uppercase. It deliberately asserts no checksum -- a counterparty
    may be non-resident and carry a foreign identifier -- which is exactly right
    here: this answers "same identifier?", and the separate validation gate on
    the invoice model answers "valid Spanish identifier?".

    Args:
        supplied: The operator's ``--counterparty-nif``, or ``None``.
        extracted: What the on-host extractor read, or ``None``.

    Returns:
        The value to confirm with, or ``None`` when neither side has one.

    Raises:
        PurchaseInvoiceEvidenceInputError: When both sides carry a value and
            they are not the same identifier.
    """
    if supplied is None:
        return extracted
    if extracted is None:
        # Extraction found nothing, so there is nothing to disagree with and
        # the operator's value is authoritative. This is the override case the
        # flag has always served, and it stays.
        return supplied
    if tax_id_identity_token(supplied) != tax_id_identity_token(extracted):
        raise PurchaseInvoiceEvidenceInputError(
            "cannot confirm an invoice: the counterparty_tax_id supplied does not match the one "
            "extracted from the document. Check the tax id printed on the invoice; re-run the "
            "extract to see what was read, or correct the evidence record.",
            suggestion="aeat app ledger evidence extract --evidence-id <id>",
        )
    return supplied


def _refuse_a_counterparty_that_is_the_filer(counterparty_tax_id: str) -> None:
    """Refuse an invoice recording the taxpayer as their own counterparty.

    The reader identifies a counterparty as the first checksum-valid tax id in
    the document, and the vision prompt asks for "the supplier's" identifier.
    On a RECEIVED invoice that lands on the supplier. On an ISSUED one the
    issuer IS the filer, so the same scan returns the filer's own identifier --
    checksum-valid, so every downstream identity check passes it, and bound for
    the Modelo 347 / 349 counterparty totals AEAT reconciles against what the
    counterparty declared.

    Refusing is right rather than advisory: unlike an amount that is merely
    doubtful, a self-naming counterparty is wrong under every reading this
    codebase can represent (see
    :func:`~application.invoices.counterparty_is_the_filer` for the autoconsumo
    scope note). Minting the record and warning about it would put a fabricated
    counterparty identity in the catalogue.

    The profile carries the identity to compare against, so a bucket whose
    profile is absent or carries no tax id cannot be checked. That case returns
    without refusing -- a guard that cannot run must not block a path it cannot
    judge -- which does mean the protection is only as present as the profile.
    Every real bucket carries one; setup requires the tax id.

    Args:
        counterparty_tax_id: The identifier about to be recorded.

    Raises:
        PurchaseInvoiceEvidenceInputError: When the identifier is the filer's
            own.
    """
    from ..invoices import counterparty_is_the_filer
    from ..wizard import WizardStatusError, load_active_taxpayer_profile
    from ..workflow import workflow_state_repository

    try:
        profile = load_active_taxpayer_profile(workflow_state_repository().load())
    except WizardStatusError:
        return
    if not counterparty_is_the_filer(counterparty_tax_id=counterparty_tax_id, profile=profile):
        return
    raise PurchaseInvoiceEvidenceInputError(
        "cannot confirm an invoice whose counterparty is the taxpayer themselves. The tax id read "
        "from the document is this profile's own, which usually means the document is an invoice "
        "YOU issued and the reader picked up your identifier from the letterhead instead of the "
        "customer's. Supply the other party's tax id with --counterparty-nif.",
        suggestion="aeat app ledger evidence confirm --counterparty-nif <the other party's tax id>",
    )


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


def _refuse_an_issued_document_the_filer_did_not_issue(
    *,
    kind: InvoiceKind,
    extracted_supplier_tax_id: str | None,
) -> None:
    """Refuse a document confirmed as ISSUED that someone else issued.

    The sibling guard refuses a counterparty that names the filer. This one
    catches the opposite mis-direction: a supplier's invoice TO the taxpayer,
    confirmed as issued BY them. There the counterparty is a real third party,
    so the sibling guard sees nothing wrong -- the record is internally
    coherent and simply describes the wrong direction.

    The evidence itself settles it. On a genuinely issued document the printed
    supplier IS the filer, so an extracted supplier identity that is somebody
    else is positive evidence the document was issued by that somebody else.

    Direction is not cosmetic. It decides which informativa the record feeds
    and on which side: a received invoice booked as issued moves a purchase
    into the sales column, inverts the cuota's meaning between soportado and
    repercutido, and reaches Modelo 347 as an operation the counterparty will
    have declared with the opposite sign. AEAT reconciles those two
    declarations against each other.

    Refusing rather than warning, for the same reason the sibling guard does:
    the direction is wrong under every reading, not merely doubtful.

    The guard declines to judge where it cannot. An absent extracted supplier
    means the scan found no issuer identity, which is silence rather than
    evidence, and a bucket whose profile carries no tax id gives nothing to
    compare against. Both return without refusing -- a guard that cannot run
    must not block a path it cannot judge.

    Args:
        kind: The direction the operator is confirming the document as.
        extracted_supplier_tax_id: Issuer identity recovered from the document,
            or ``None`` when the scan found none.

    Raises:
        PurchaseInvoiceEvidenceInputError: The document names an issuer who is
            not the filer, yet is being confirmed as issued by the filer.
    """
    if kind is not InvoiceKind.ISSUED or extracted_supplier_tax_id is None:
        return

    from ..invoices import counterparty_is_the_filer
    from ..wizard import WizardStatusError, load_active_taxpayer_profile
    from ..workflow import workflow_state_repository

    try:
        profile = load_active_taxpayer_profile(workflow_state_repository().load())
    except WizardStatusError:
        return
    # The loader raises rather than returning None, and that failure is already
    # handled by the except clause above, so the former None guard was unreachable.
    if counterparty_is_the_filer(counterparty_tax_id=extracted_supplier_tax_id, profile=profile):
        return
    raise PurchaseInvoiceEvidenceInputError(
        "this document names another issuer, so it cannot be confirmed as issued by you; "
        "confirm it as received, or correct the document reference",
    )


def confirm_invoice_draft_from_evidence(
    *,
    bucket_id: str,
    kind: InvoiceKind,
    counterparty_country: str,
    evidence_id: str | None = None,
    attachment_id: str | None = None,
    counterparty_tax_id: str | None = None,
    counterparty_name: str | None = None,
    invoice_number: str | None = None,
    invoice_date: date | None = None,
    taxable_base: Decimal | None = None,
    iva_rate: Decimal | None = None,
    currency: str | None = None,
    iva_amount: Decimal | None = None,
    iva_category: IvaCategory | None = None,
    operation_date: date | None = None,
    retention_rate: Decimal | None = None,
    retention_amount: Decimal | None = None,
    recargo_amount: Decimal | None = None,
    invoice_class: InvoiceClass = InvoiceClass.ORDINARIA,
    series: str | None = None,
    rectifies_invoice_number: str | None = None,
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
    (``aeat-architecture-boundaries``); this function never
    writes the catalogue itself.

    Idempotent-guarded (``aeat-cli-contract``): the
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
        iva_amount: The cuota PRINTED on the document, when it differs from
            base times rate. A printed figure is evidence and outranks a
            recomputed one, so supplying it makes the persisted line carry it
            exactly. The line invariants still apply, so a cuota the base and
            rate cannot support refuses rather than overriding them.
        iva_category: IVA treatment of the operation. Required for the renta
            income lane to ground the record.
        operation_date: Date the operation was performed, when it differs from
            the issue date, letting the record reach a declared devengo rank.
        retention_rate: RIRPF art. 95 withholding fraction, settled OUTSIDE
            the invoice total.
        retention_amount: The withheld figure. Accepted alone; required
            whenever a rate is supplied.
        recargo_amount: Recargo de equivalencia (LIVA art. 161), which rides
            INSIDE the invoice total, unlike a retención.
        invoice_class: Invoice class. A rectificativa also needs
            ``rectifies_invoice_number``.
        series: Invoice numbering series, when the issuer uses one.
        rectifies_invoice_number: Number of the invoice a rectificativa
            corrects.
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

    # WHICH party is the counterparty depends on the direction of the document,
    # so the side is selected by `kind` rather than assumed to be the supplier.
    # On an invoice the filer ISSUED, the counterparty is the customer; taking
    # the supplier there names the filer as their own counterparty, and that
    # value reaches the Modelo 347 / 349 totals AEAT reconciles against the
    # other party's own declaration. Only a structured reader distinguishes the
    # two, so the text and vision paths leave the customer side unset and fall
    # back to the single identifier they can recover.
    extracted_counterparty_tax_id = draft.supplier_tax_id
    extracted_counterparty_name = draft.supplier_name
    if kind is InvoiceKind.ISSUED and draft.customer_tax_id is not None:
        extracted_counterparty_tax_id = draft.customer_tax_id
        extracted_counterparty_name = draft.customer_name
    resolved_counterparty_tax_id = _require_confirmed_field(
        _agreed_counterparty_tax_id(supplied=counterparty_tax_id, extracted=extracted_counterparty_tax_id),
        field="counterparty_tax_id",
    )
    assert isinstance(resolved_counterparty_tax_id, str)
    _refuse_an_issued_document_the_filer_did_not_issue(
        kind=kind,
        extracted_supplier_tax_id=draft.supplier_tax_id,
    )
    _refuse_a_counterparty_that_is_the_filer(resolved_counterparty_tax_id)
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
    resolved_counterparty_name = (counterparty_name or extracted_counterparty_name or "").strip()
    if not resolved_counterparty_name:
        raise PurchaseInvoiceEvidenceInputError(
            "cannot confirm an invoice: the document states no counterparty name and no "
            "--counterparty-name override was supplied",
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
        # Guarded idempotent retry (aeat-cli-contract):
        # the confirm's resolved identity fields hash to an invoice already in the
        # catalogue -- return it unchanged rather than raising or re-writing. The
        # source evidence link is re-asserted (a no-op when already present,
        # `link_attachment_invoice` dedups) so a re-confirm never regresses the
        # provenance link even if it was never wired for this evidence before.
        link_attachment_invoice(attachment_store, attachment_id=resolved_attachment_id, invoice_id=existing.invoice_id)
        return InvoiceConfirmationResult(
            invoice=existing,
            draft=draft,
            created=False,
            # Re-asserted on the guarded no-op for the same reason the provenance
            # link is: a retry must not silently drop a discrepancy the first
            # confirm surfaced, or the alert becomes something a re-run clears.
            total_discrepancy=printed_total_discrepancy(draft=draft, invoice=existing),
        )

    # A PRINTED cuota is evidence and outranks a recomputed one. When the
    # operator states it, the line carries that exact figure rather than
    # base * rate, so a document whose printed cuota differs by a cent from the
    # arithmetic is recorded as it was issued. The line invariants still apply,
    # so a cuota the base and rate cannot support refuses rather than being
    # accepted as an override.
    confirmed_lines = None
    operator_overrode_the_amounts = taxable_base is not None or iva_rate is not None or iva_amount is not None
    if len(draft.iva_breakdown) > 1 and not operator_overrode_the_amounts:
        # A document that charges more than one rate cannot be represented by a
        # single base and cuota pair. The parsers read the per-rate split
        # exactly; collapsing it here would lose WHICH part of the base carried
        # which rate, and the totals would still agree -- which is what makes
        # the loss quiet. Modelo 303 sums cuota devengada per tier, so a
        # collapsed invoice declares into one tier what belongs in two.
        #
        # Skipped entirely when the operator overrode any amount: an explicit
        # override is a statement about the whole invoice, and silently keeping
        # a per-rate split beside it would leave two disagreeing authorities on
        # the same figures.
        confirmed_lines = tuple(
            InvoiceLine(
                description=f"{resolved_invoice_number or 'Invoice'} - IVA {entry.iva_rate}%",
                quantity=Decimal("1"),
                unit_price=entry.taxable_base,
                subtotal=entry.taxable_base,
                iva_rate=resolve_iva_rate_slot(entry.iva_rate),
                iva_amount=entry.iva_amount,
            )
            for entry in draft.iva_breakdown
        )
    elif iva_amount is not None:
        confirmed_lines = (
            InvoiceLine(
                description=resolved_invoice_number or "Invoice",
                quantity=Decimal("1"),
                unit_price=resolved_taxable_base,
                subtotal=resolved_taxable_base,
                # The SAME resolver the writer below applies to the same value,
                # so an unrepresentable percentage refuses identically whether
                # or not the document printed a cuota.
                iva_rate=resolve_iva_rate_slot(resolved_iva_rate),
                iva_amount=iva_amount,
            ),
        )
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
        iva_category=iva_category,
        operation_date=operation_date,
        retention_rate=retention_rate,
        retention_amount=retention_amount,
        recargo_amount=recargo_amount,
        invoice_class=invoice_class,
        series=series,
        rectifies_invoice_number=rectifies_invoice_number,
        lines=confirmed_lines,
        repository=repository,
    )
    # Auto-link the source evidence/attachment to the newly minted invoice, closing
    # the provenance loop: the invoice is now discoverable from the evidence
    # (`Attachment.linked_invoice_ids`) and vice versa (`Invoice.invoice_id` is what
    # was just recorded). `link_attachment_invoice` re-persists through the same
    # sanctioned `AttachmentStoreProtocol.write_manifest` path
    # (`aeat-architecture-boundaries`); it never re-implements the
    # attachment write.
    link_attachment_invoice(
        attachment_store,
        attachment_id=resolved_attachment_id,
        invoice_id=result.invoice.invoice_id,
    )
    return InvoiceConfirmationResult(
        invoice=result.invoice,
        draft=draft,
        created=True,
        total_discrepancy=printed_total_discrepancy(draft=draft, invoice=result.invoice),
    )


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
