"""Transport-neutral invoice-field response schema, parser and grounded re-validation.

A model asked to read an invoice returns strings. Whether it read those strings
off rasterised pixels (:mod:`._evidence_draft_vision`) or off an already-extracted
text layer (:mod:`._evidence_draft_text`) changes nothing about what must happen
next: the response has to be recovered from possibly-chatty completion text,
validated against a strict schema, and then *re-validated field by field* so a
value the model invented is dropped rather than trusted.

That second step is the whole point. The reading model is probabilistic and a
fabricated taxable base or supplier identifier would flow into a Modelo 303/390
filing looking exactly like a read one. Every field here is therefore checked
against an independent authority -- the AEAT checksum algorithm
(:func:`~core.identity.validate_spanish_tax_id`), the EU VIES structural format
table (:data:`~core.identity.NIF_IVA_FORMATS`), the date parser
(:func:`~core.parsing.parse_date`), the finite European-decimal authority
(:func:`~core.decimal.coerce_finite_european_decimal`) -- and a field that fails
its check becomes ``None``. ``None`` is safe because the confirm path treats a
missing figure as a hard refusal naming the operator override; a guessed figure
would instead be minted silently.

Nothing in this module knows about images, providers or transports, which is why
it lives here rather than beside either reader.

See Also:
    :class:`~application.ledger.InvoiceDraft`
        Typed draft every grounded reader returns.
    :func:`~core.identity.validate_spanish_tax_id`
        Spanish NIF/NIE/CIF checksum authority.
    :func:`~core.identity.nif_iva_format_for_country`
        EU intra-community NIF-IVA structural format authority.
"""

from __future__ import annotations

import re
from decimal import Decimal

from pydantic import BaseModel, Field

from ..application.ledger import InvoiceDraft, PurchaseInvoiceEvidenceInputError
from ..core import STRICT_FROZEN_CONFIG
from ..core.decimal import coerce_finite_european_decimal, european_thousands_reading_is_ambiguous
from ..core.identity import (
    IdentityError,
    nif_iva_format_for_country,
    normalise_nif_iva,
    validate_spanish_tax_id,
)
from ..core.parsing import parse_date

__all__ = [
    "ExtractedInvoiceFields",
    "ground_extracted_fields",
    "parse_invoice_extraction_response",
]

# One JSON object, allowing the model to wrap it in prose or a code fence; the
# first balanced-looking candidate is taken (mirrors the classification parser's
# tolerance for chatty local models).
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


class ExtractedInvoiceFields(BaseModel):
    """Raw string fields the reading model transcribed, before grounded re-validation.

    Every field is an optional string: the model is instructed to transcribe the
    printed value verbatim (never compute or infer it) and this schema accepts
    whatever string it returns. Grounded re-validation into typed values (a
    checksum-valid tax id, a parsed date, a parsed Decimal) happens in
    :func:`ground_extracted_fields`, never here -- a malformed or hallucinated
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


def parse_invoice_extraction_response(text: str) -> ExtractedInvoiceFields:
    """Parse a reading model's raw completion text into :class:`ExtractedInvoiceFields`.

    Args:
        text: Raw completion text from the reading model.

    Returns:
        :class:`ExtractedInvoiceFields`: The parsed (but not yet grounded) fields.

    Raises:
        PurchaseInvoiceEvidenceInputError: When no JSON object is present or the
            object fails schema validation.
    """
    payload = _extract_json_object(text)
    if payload is None:
        raise PurchaseInvoiceEvidenceInputError(
            f"invoice reading model returned no parsable JSON object: {text[:200]!r}",
            suggestion="aeat app ledger evidence extract --evidence-id <id>",
        )
    try:
        return ExtractedInvoiceFields.model_validate_json(payload)
    except ValueError as exc:
        raise PurchaseInvoiceEvidenceInputError(
            f"invoice reading model response failed schema validation: {str(exc)[:200]}",
            suggestion="aeat app ledger evidence extract --evidence-id <id>",
        ) from exc


def _grounded_intra_community_tax_id(normalised: str) -> str | None:
    """Return *normalised* if it matches its own country's published NIF-IVA pattern.

    The country is read off the number's own two-character VAT prefix, because
    that is the only country signal a transcribed identifier carries -- unlike
    :func:`~domain.invoices.validate_iva_number`, which validates against a
    country declared independently on the invoice record and can therefore fall
    back to a permissive generic body check for a non-EU counterparty. That
    fallback is unavailable here and would be circular if borrowed: with the
    country derived from the string, "prefix plus alphanumeric body" accepts any
    two letters followed by anything, which is precisely the fabricate-anything
    outcome grounded re-validation exists to prevent.

    So the rule is strictly closed: a prefix naming no Member State (or Northern
    Ireland), or a body that does not match that State's VIES structure, drops to
    ``None``.
    """
    if len(normalised) < 2:
        return None
    spec = nif_iva_format_for_country(normalised[:2])
    if spec is None or not spec.pattern.match(normalised):
        return None
    return normalised


def _grounded_tax_id(raw: str | None) -> str | None:
    """Ground a transcribed supplier identifier as a Spanish or EU intra-community id.

    Spanish identifiers keep the full AEAT checksum test: a CIF whose control
    character does not compute is a misread (or an invention) and must still be
    dropped. Only once that test has *rejected* the value is it offered to the
    EU structural authority, so nothing about Spanish validation is weakened --
    a Spanish-shaped number carries no EU VAT prefix and fails there too.

    Routing every identifier through the Spanish validator alone silently
    discarded a *correct* read of a valid foreign VAT number, which is the entire
    Modelo 349 / intra-EU reverse-charge population: a supplier invoicing from
    Ireland or Germany reached the operator with no identifier at all.
    """
    if raw is None:
        return None
    try:
        return validate_spanish_tax_id(raw)
    except IdentityError:
        return _grounded_intra_community_tax_id(normalise_nif_iva(raw))


def _grounded_invoice_number(raw: str | None) -> str | None:
    if raw is None:
        return None
    trimmed = raw.strip()
    return trimmed or None


def _grounded_date(raw: str | None) -> str | None:
    """Parse *raw* as a day-first (``DD-MM-YYYY`` / ``DD/MM/YYYY``) or ISO-8601 date.

    A model transcribing a printed European invoice date returns the day-first
    form the document actually shows (mirroring the text-layer heuristic's
    ``_DATE_RE``); ISO-8601 is tried second in case the model normalises the
    printed value itself. Only these two real, registered
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
    """Return the model's transcribed amount as a finite Decimal, or ``None``.

    Routed through the canonical finite European-decimal authority rather than
    stripping every dot as a thousands separator. Unconditional stripping
    corrupted an already dot-decimal transcription -- ``"1234.56"`` became
    ``Decimal("123456")`` -- silently multiplying a taxable base, IVA amount or
    grand total by a hundred, and it admitted ``NaN`` and ``Infinity`` as
    amounts. The canonical helper reads a comma as the decimal separator (so
    ``"1.234,56"`` still parses as ``1234.56``) and refuses non-finite values.

    An amount whose dot could equally be a thousands separator or a decimal
    point is dropped rather than read one way. The model is instructed to
    transcribe what is printed and the schema types every field as a string so
    nothing is normalised on the way out, which is deliberate -- it means the
    convention in the returned text is the SUPPLIER'S, and a supplier writing
    Spanish prints one thousand two hundred and thirty-four euros as
    ``1.234``. Read as a decimal that is ``1.23``, a thousandfold light on a
    taxable base bound for Modelo 303/390.

    Dropping to ``None`` is the same call :func:`_grounded_currency` makes on a
    symbol it cannot resolve, for the same reason: the confirm path treats a
    missing amount as a hard refusal naming the ``--taxable-base`` override, so
    the operator is asked for the figure. A guessed one would instead be minted
    silently, and the draft review is advisory rather than a gate -- ``confirm``
    re-extracts and uses the extracted value for any field the operator did not
    explicitly override.
    """
    if raw is None:
        return None
    text = raw.strip()
    if european_thousands_reading_is_ambiguous(text):
        return None
    return coerce_finite_european_decimal(text)


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


def ground_extracted_fields(fields: ExtractedInvoiceFields, *, raw_text_length: int) -> InvoiceDraft:
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
