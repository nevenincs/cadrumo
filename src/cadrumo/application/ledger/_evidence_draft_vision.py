"""On-host vision fallback for invoice-field extraction from a scan-only PDF or image.

:func:`~application.ledger.extract_invoice_fields` reads a PDF's embedded text
layer. A scan-only or image-only invoice has no text layer at all, so that
primitive raises. This module supplies the on-host fallback: rasterise the PDF
(or use an image directly) into in-memory base64 PNG pages
(:func:`~adapters.outbound.llm.rasterise_pdf_pages_to_base64_png`) and read them
with the same LOCAL Ollama vision model the classification path already uses
(:class:`~application.ledger._vision_classifier.LocalVisionLLMClassifier`), fully on-host
(``sensitive-financial-data-secure-storage-only``). Nothing is written to disk and
nothing leaves the machine; this needs no cloud consent gate.

The vision model's role here is strictly *transcription*, never *derivation*: the
prompt instructs it to copy each field's printed value verbatim (or emit ``null``
when a field is not visibly printed) and forbids it from computing, inferring, or
estimating any figure. Every field the model returns is re-validated through the
exact same grounded heuristics the text-layer path uses --
:func:`~core.identity.validate_spanish_tax_id`,
:func:`~core.parsing.parse_date`, and :class:`~decimal.Decimal` parsing via
:func:`~core.decimal.normalize_decimal_separators` -- so a malformed or
hallucinated value is rejected (left ``None``) rather than trusted. This mirrors the
document-printed-value semantics
:func:`~application.ledger.extract_invoice_fields` already has for text-layer PDFs:
both paths recover what is *printed on the
document*, never a registry-derived or model-computed tax figure
(``evidence-read-never-emits-regulated-numbers`` in spirit -- the persisted
:class:`~domain.invoices.Invoice` this draft eventually confirms into still goes
through the operator review step before anything is minted).

Gated by :attr:`~core.ServiceCapability.LLM_VISION`: an operator who has opted
out of on-host vision reading gets a typed refusal naming the capability toggle,
never a silent empty draft.

See Also:
    :class:`~application.ledger.InvoiceDraft`
        Typed draft this vision path returns after grounded re-validation.
    :func:`~application.ledger.extract_invoice_fields`
        Text-layer extraction primitive this module complements for scan-only
        or image-only evidence.
    :func:`~application.ledger.extract_invoice_draft_from_evidence`
        Orchestration layer that falls back to this on-host reader.
    :class:`~application.ledger._vision_classifier.LocalVisionLLMClassifier`
        Sibling local Ollama vision transport used for classification and
        split suggestions.
"""

from __future__ import annotations

import asyncio
import base64
import re
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, Field

from ...adapters.outbound.llm import LLMClient, LLMProvider, LLMRequest, MultimodalImageInput
from ...core import STRICT_FROZEN_CONFIG
from ...core.config import Settings, load_settings
from ...core.decimal import normalize_decimal_separators
from ...core.hashing import sha256_hex
from ...core.identity import IdentityError, validate_spanish_tax_id
from ...core.parsing import parse_date
from ._evidence import PurchaseInvoiceEvidenceInputError
from ._evidence_draft import InvoiceDraft

__all__ = [
    "LocalVisionInvoiceFieldExtractor",
    "extract_invoice_fields_from_images",
]

# One JSON object, allowing the model to wrap it in prose or a code fence; the
# first balanced-looking candidate is taken (mirrors the classification parser's
# tolerance for chatty local models).
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

_FIELD_EXTRACTION_PROMPT = """\
You are transcribing fields from a scanned Spanish invoice image. Look at the \
image and copy each field's value EXACTLY as printed. Do not calculate, infer, \
estimate, or guess any value. If a field is not visibly printed on the document, \
its value is null.

Return ONLY one JSON object with exactly these keys (no other text):
{{
  "supplier_tax_id": <string or null, the supplier's NIF/NIE/CIF exactly as printed>,
  "invoice_number": <string or null, the invoice number exactly as printed>,
  "invoice_date": <string or null, the invoice date exactly as printed, e.g. "10/03/2026">,
  "taxable_base": <string or null, the "base imponible" amount exactly as printed, e.g. "100,00">,
  "iva_rate": <string or null, the IVA percentage exactly as printed, e.g. "21">,
  "iva_amount": <string or null, the IVA cuota amount exactly as printed, e.g. "21,00">,
  "grand_total": <string or null, the invoice total amount exactly as printed, e.g. "121,00">,
  "currency": <string or null, the ISO-4217 code for the currency the amounts \
are printed in, e.g. "EUR", "USD", "GBP". Read it from the printed symbol or \
code next to the amounts. If no currency is shown anywhere, null>
}}
"""


class _VisionExtractedFields(BaseModel):
    """Raw string fields the vision model transcribed, before grounded re-validation.

    Every field is an optional string: the model is instructed to transcribe the
    printed value verbatim (never compute or infer it) and this schema accepts
    whatever string it returns. Grounded re-validation into typed values (a
    checksum-valid tax id, a parsed date, a parsed Decimal) happens in
    :func:`_ground_extracted_fields`, never here -- a malformed or hallucinated
    string must be rejected downstream, not coerced at the schema boundary.
    """

    model_config = STRICT_FROZEN_CONFIG

    supplier_tax_id: str | None = Field(default=None)
    invoice_number: str | None = Field(default=None)
    invoice_date: str | None = Field(default=None)
    taxable_base: str | None = Field(default=None)
    iva_rate: str | None = Field(default=None)
    iva_amount: str | None = Field(default=None)
    grand_total: str | None = Field(default=None)
    currency: str | None = Field(default=None)


def _extract_json_object(text: str) -> str | None:
    match = _JSON_OBJECT_RE.search(text)
    return match.group(0) if match else None


def parse_vision_extraction_response(text: str) -> _VisionExtractedFields:
    """Parse the vision model's raw completion text into :class:`_VisionExtractedFields`.

    Args:
        text: Raw completion text from the local vision model.

    Returns:
        :class:`_VisionExtractedFields`: The parsed (but not yet grounded) fields.

    Raises:
        PurchaseInvoiceEvidenceInputError: When no JSON object is present or the
            object fails schema validation.
    """
    payload = _extract_json_object(text)
    if payload is None:
        raise PurchaseInvoiceEvidenceInputError(
            f"on-host vision model returned no parsable JSON object: {text[:200]!r}",
            suggestion="aeat app ledger evidence extract --evidence-id <id>",
        )
    try:
        return _VisionExtractedFields.model_validate_json(payload)
    except ValueError as exc:
        raise PurchaseInvoiceEvidenceInputError(
            f"on-host vision model response failed schema validation: {str(exc)[:200]}",
            suggestion="aeat app ledger evidence extract --evidence-id <id>",
        ) from exc


def _grounded_tax_id(raw: str | None) -> str | None:
    if raw is None:
        return None
    try:
        return validate_spanish_tax_id(raw)
    except IdentityError:
        return None


def _grounded_invoice_number(raw: str | None) -> str | None:
    if raw is None:
        return None
    trimmed = raw.strip()
    return trimmed or None


def _grounded_date(raw: str | None) -> str | None:
    """Parse *raw* as a day-first (``DD-MM-YYYY`` / ``DD/MM/YYYY``) or ISO-8601 date.

    A vision model transcribing a printed Spanish invoice date returns the
    day-first form the document actually shows (mirroring the text-layer
    heuristic's ``_DATE_RE``); ISO-8601 is tried second in case the model
    normalises the printed value itself. Only these two real, registered
    :data:`~core.parsing._DateFmt` members are ever passed -- an invented
    format string silently degrades to one of the two delegates
    (:func:`~core.parsing._parse_date` has no third branch), which would
    make a "fallback" attempt a silent no-op duplicate.
    """
    if raw is None:
        return None
    cleaned = raw.strip()
    for fmt in ("ddmmyyyy", "iso8601"):
        parsed = parse_date(cleaned, fmt=fmt, on_error="none")
        if parsed is not None:
            return parsed.isoformat()
    return None


def _grounded_decimal(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    normalized = normalize_decimal_separators(raw.strip(), strip_thousands=True)
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def _grounded_currency(raw: str | None) -> str | None:
    """Return *raw* as an ISO-4217 code, or ``None`` when it is not one.

    A currency the model transcribed as a symbol, a word, or anything other
    than a three-letter alphabetic code is dropped rather than guessed: mapping
    a bare "$" to USD would invent a fact the document may not support (it is
    also CAD, AUD, MXN), and inventing the currency of a filing amount is the
    one error the grounded-extraction discipline exists to prevent.
    """
    if raw is None:
        return None
    candidate = raw.strip().upper()
    if len(candidate) != 3 or not candidate.isalpha():
        return None
    return candidate


def _ground_extracted_fields(fields: _VisionExtractedFields, *, raw_text_length: int) -> InvoiceDraft:
    """Re-validate the model's transcribed strings into a grounded :class:`InvoiceDraft`.

    A field the model transcribed but that fails grounded validation (an invalid
    tax-id checksum, an unparsable date, a non-numeric amount) is dropped to
    ``None`` rather than trusted -- the same "never fabricate" discipline the
    text-layer heuristics apply.
    """
    return InvoiceDraft(
        supplier_tax_id=_grounded_tax_id(fields.supplier_tax_id),
        invoice_number=_grounded_invoice_number(fields.invoice_number),
        invoice_date=_grounded_date(fields.invoice_date),
        taxable_base=_grounded_decimal(fields.taxable_base),
        iva_rate=_grounded_decimal(fields.iva_rate),
        iva_amount=_grounded_decimal(fields.iva_amount),
        grand_total=_grounded_decimal(fields.grand_total),
        currency=_grounded_currency(fields.currency),
        raw_text_length=raw_text_length,
    )


class LocalVisionInvoiceFieldExtractor:
    """Read an invoice image on-host with a local Ollama vision model into an :class:`InvoiceDraft`.

    Mirrors :class:`~application.ledger._vision_classifier.LocalVisionLLMClassifier`'s transport
    (a local Ollama vision model fed in-memory base64 images) but for field
    transcription instead of category classification. Every returned field is
    re-validated through the grounded heuristics
    :func:`~application.ledger.extract_invoice_fields` uses for the text-layer path,
    so a hallucinated or malformed value never reaches the operator as a
    fabricated fact.

    Args:
        model: Local Ollama vision model identifier; defaults to
            ``Settings.cadrumo_llm_ollama_vision_model``.
        client: Injected :class:`~adapters.outbound.llm.LLMClient` (dependency
            injection for tests); default-constructed against the resolved
            settings otherwise.
        settings: Injected settings; defaults to ``load_settings()``.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        client: LLMClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        resolved_settings = settings if settings is not None else load_settings()
        self._model = model if model is not None else resolved_settings.cadrumo_llm_ollama_vision_model
        # A local vision model on consumer hardware can take minutes; give the
        # vision read its own (longer) timeout, mirroring LocalVisionLLMClassifier.
        vision_settings = resolved_settings.model_copy(
            update={"cadrumo_llm_default_timeout_s": resolved_settings.cadrumo_llm_vision_read_timeout_s},
        )
        self._client = (
            client
            if client is not None
            else LLMClient(
                settings=vision_settings,
                caller="cadrumo.application.ledger.evidence_draft_vision",
                prompt_id="ledger-invoice-vision-extract",
            )
        )

    @property
    def decided_by(self) -> str:
        """Provenance stamp for this extractor's transport (distinct from classification)."""
        return f"llm:local-vision:{self._model}"

    def extract(self, *, evidence_images: tuple[str, ...]) -> InvoiceDraft:
        """Read ``evidence_images`` with the local vision model and return a grounded draft.

        Args:
            evidence_images: In-memory base64 page/image renders of the evidence
                (from :func:`~adapters.outbound.llm.rasterise_pdf_pages_to_base64_png`
                for a scan-only PDF, or the raw image bytes base64-encoded for an
                image attachment).

        Returns:
            :class:`InvoiceDraft`: Every field the model transcribed AND that
            passed grounded re-validation; everything else is ``None``.
        """
        images = tuple(
            MultimodalImageInput(
                content_sha256=sha256_hex(base64.b64decode(encoded)),
                base64_data=encoded,
            )
            for encoded in evidence_images
        )
        request = LLMRequest(
            prompt=_FIELD_EXTRACTION_PROMPT,
            provider_override=LLMProvider.LOCAL,
            model_override=self._model,
            images=images,
        )
        response = asyncio.run(self._client.complete(request))
        parsed = parse_vision_extraction_response(response.text)
        # `raw_text_length` on the vision path reports the length of the model's
        # own transcription text, mirroring the text-layer path's semantics of
        # "how much source material did the reader have to work with" -- here
        # that is the model's read-out rather than a pdfplumber page dump.
        return _ground_extracted_fields(parsed, raw_text_length=len(response.text))


def extract_invoice_fields_from_images(
    evidence_images: tuple[str, ...],
    *,
    model: str | None = None,
    settings: Settings | None = None,
) -> InvoiceDraft:
    """Convenience wrapper: build a :class:`LocalVisionInvoiceFieldExtractor` and extract.

    Args:
        evidence_images: In-memory base64 page/image renders of the evidence.
        model: Optional vision model override.
        settings: Optional resolved settings override.

    Returns:
        :class:`InvoiceDraft`: The grounded, best-effort extracted fields.
    """
    extractor = LocalVisionInvoiceFieldExtractor(model=model, settings=settings)
    return extractor.extract(evidence_images=evidence_images)
