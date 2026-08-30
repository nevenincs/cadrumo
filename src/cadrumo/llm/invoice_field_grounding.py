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
    :class:`~application.ledger.evidence_draft.InvoiceDraft`
        Typed draft every grounded reader returns.
    :func:`~core.identity.validate_spanish_tax_id`
        Spanish NIF/NIE/CIF checksum authority.
    :func:`~core.identity.nif_iva_format_for_country`
        EU intra-community NIF-IVA structural format authority.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import cast

from pydantic import BaseModel, Field

from ..application.ledger.evidence import PurchaseInvoiceEvidenceInputError
from ..application.ledger.evidence_draft import DraftDiscrepancyFinding, FieldProvenance, InvoiceDraft
from ..core import (
    STRICT_FROZEN_CONFIG,
    ActionEvidenceProvenance,
    DraftDiscrepancyKind,
    FieldGroundingOutcome,
    FieldOrigin,
)
from ..core.decimal import coerce_finite_european_decimal, european_thousands_reading_is_ambiguous
from ..core.errors import CoreValidationError
from ..core.identity import (
    IdentityError,
    nif_iva_format_for_country,
    normalise_nif_iva,
    validate_spanish_tax_id,
)
from ..core.parsing import normalise_iso_4217_currency, parse_date
from ..domain.iva.establishment import country_code_for_printed_country_name
from .invoice_field_contract import (
    ANCHOR_KEY_SUFFIX,
    INVOICE_FIELD_CONTRACTS,
    ROLE_EVIDENCE_KEY_SUFFIX,
    InvoiceFieldForm,
    contract_for_field,
)
from .preconditions import LLMPreconditionCondition, llm_no_recovery_verdict

__all__ = [
    "ExtractedFieldAnchors",
    "ExtractedInvoiceFields",
    "ExtractedInvoiceResponse",
    "ExtractedRoleEvidence",
    "ground_extracted_fields",
    "parse_invoice_extraction_response",
]

# One JSON object, allowing the model to wrap it in prose or a code fence; the
# first balanced-looking candidate is taken (mirrors the classification parser's
# tolerance for chatty local models).
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


class _ExtractedInvoiceFieldClaims(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    supplier_tax_id: str | None = Field(default=None)
    supplier_name: str | None = Field(default=None)
    supplier_postal_code: str | None = Field(default=None)
    supplier_country: str | None = Field(default=None)
    customer_tax_id: str | None = Field(default=None)
    customer_name: str | None = Field(default=None)
    customer_postal_code: str | None = Field(default=None)
    customer_country: str | None = Field(default=None)
    invoice_number: str | None = Field(default=None)
    invoice_date: str | None = Field(default=None)
    taxable_base: str | None = Field(default=None)
    iva_rate: str | None = Field(default=None)
    iva_amount: str | None = Field(default=None)
    retencion_rate: str | None = Field(default=None)
    retencion_amount: str | None = Field(default=None)
    grand_total: str | None = Field(default=None)
    regime_legend: str | None = Field(default=None)
    currency: str | None = Field(default=None)


class ExtractedInvoiceFields(_ExtractedInvoiceFieldClaims):
    """Raw string fields the reading model transcribed, before grounded re-validation.

    Every field is an optional string: the model is instructed to transcribe the
    printed value verbatim (never compute or infer it) and this schema accepts
    whatever string it returns. Grounded re-validation into typed values (a
    checksum-valid tax id, a parsed date, a parsed Decimal) happens in
    :func:`ground_extracted_fields`, never here -- a malformed or hallucinated
    string must be rejected downstream, not coerced at the schema boundary.
    """


class ExtractedFieldAnchors(_ExtractedInvoiceFieldClaims):
    """The verbatim printed substring the model read each field from.

    Deliberately a mirror of :class:`ExtractedInvoiceFields` rather than extra
    attributes on it. The two carry different KINDS of claim: a field holds the
    value in its declared form, an anchor holds the form the document actually
    printed, and the whole anti-fabrication argument rests on being able to
    compare them. Folded into one model that comparison becomes an attribute
    naming convention; kept apart it is a type.

    Every attribute is an optional string for the same reason the value side is:
    the model returns strings, and nothing here rejects or rewrites one. An
    anchor that does not occur in the document is caught by the anchor check
    (:func:`~application.ledger.grounding_anchor.evaluate_anchor`), never by this schema, because
    that check needs the document and this schema does not have it.
    """


class ExtractedRoleEvidence(BaseModel):
    """The printed context assigning each identity value to a party role.

    A THIRD kind of claim, kept in its own model for the reason the anchors are:
    :class:`ExtractedInvoiceFields` holds *what the identifier is*,
    :class:`ExtractedFieldAnchors` holds *where on the page it was printed*, and
    this holds *what on the page says it belongs to that party*. An invoice
    prints two identifiers of identical shape, so the printed form of one is no
    evidence at all about whose it is -- which is exactly the question the
    counterparty role turns on.

    Only the identity fields appear here, and their set is
    :func:`~llm.invoice_field_contract.identity_field_names`, asserted by the
    parity gate rather than maintained twice. Every attribute is an optional
    string on the same terms as the other two halves: nothing is rejected or
    rewritten here, because the check that matters needs the document and this
    schema does not have it. A value that does not occur in the transcription is
    dropped by :func:`~application.ledger.grounding_anchor.printed_excerpt_occurs` at the
    grounding stage, so an invented role evidence cannot promote an identity.
    """

    model_config = STRICT_FROZEN_CONFIG

    supplier_tax_id: str | None = Field(default=None)
    customer_tax_id: str | None = Field(default=None)


class ExtractedInvoiceResponse(BaseModel):
    """One reading model's complete reply: every value beside its printed anchor.

    The parser's single return type. Splitting the reply into models but
    returning them as one object keeps the pairing structural -- a caller cannot
    hold values without the anchors that justify them, which is exactly the
    separation that let a value travel to a filing with nothing to point at. The
    role-evidence half is bound in the same way and for a sharper version of the
    same reason: an identity carried without it is a party name nothing on the
    document assigns.

    Attributes:
        fields: The transcribed values, before grounded re-validation.
        anchors: The printed form each value was read from.
        role_evidence: The printed context assigning each identity value to its
            party role. Defaults to an all-``None`` record, so a reply that
            offers none parses cleanly and simply evidences no role -- the
            fail-safe direction, since an unevidenced identity refuses.
    """

    model_config = STRICT_FROZEN_CONFIG

    fields: ExtractedInvoiceFields
    anchors: ExtractedFieldAnchors
    role_evidence: ExtractedRoleEvidence = Field(default_factory=ExtractedRoleEvidence)


def _extract_json_object(text: str) -> str | None:
    match = _JSON_OBJECT_RE.search(text)
    return match.group(0) if match else None


def parse_invoice_extraction_response(text: str) -> ExtractedInvoiceResponse:
    """Parse a reading model's raw completion text into values and their anchors.

    The prompt asks for one flat object carrying each field beside its
    ``<field>_anchor`` sibling, and each IDENTITY field beside its
    ``<field>_role_evidence`` sibling too, so the flat reply is split here into
    its typed halves. Splitting on the declared suffixes rather than on a second
    hand-written key list means the prompt and the parser cannot ask for and
    read different keys.

    A model that returns only the value keys parses cleanly with empty anchors
    and no role evidence: that is a reply with nothing to point at and nothing
    assigning its identities to a party, which the grounding stage records
    honestly rather than a malformed one to reject -- and an unevidenced
    identity refuses downstream, so the tolerant parse costs no safety. A key
    matching neither a declared field nor a declared anchor nor a declared
    role-evidence key IS rejected -- an unrecognised key is a model inventing
    structure, and tolerating it here would let a fabricated field ride along
    unnoticed.

    Args:
        text: Raw completion text from the reading model.

    Returns:
        :class:`ExtractedInvoiceResponse`: The parsed (but not yet grounded)
        values, the printed anchors they were read from, and the printed role
        evidence assigning each identity to a party.

    Raises:
        PurchaseInvoiceEvidenceInputError: When no JSON object is present, the
            object is not a JSON object, or either half fails schema validation.
    """
    payload = _extract_json_object(text)
    if payload is None:
        raise PurchaseInvoiceEvidenceInputError(
            precondition_verdict=llm_no_recovery_verdict(
                LLMPreconditionCondition.EVIDENCE_RESPONSE_JSON_OBJECT,
                facts={"evidence_response_json_object": False, "evidence_response_parseable": False},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            ),
        )
    try:
        raw = json.loads(payload)
    except ValueError as exc:
        raise PurchaseInvoiceEvidenceInputError(
            context={"evidence_response_error_type": type(exc).__name__},
            precondition_verdict=llm_no_recovery_verdict(
                LLMPreconditionCondition.EVIDENCE_RESPONSE_JSON_OBJECT,
                facts={
                    "evidence_response_error_type": type(exc).__name__,
                    "evidence_response_json_object": False,
                    "evidence_response_parseable": False,
                },
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            ),
        ) from exc
    if not isinstance(raw, dict):
        raise PurchaseInvoiceEvidenceInputError(
            context={"evidence_response_type": type(raw).__name__},
            precondition_verdict=llm_no_recovery_verdict(
                LLMPreconditionCondition.EVIDENCE_RESPONSE_JSON_OBJECT,
                facts={
                    "evidence_response_json_object": False,
                    "evidence_response_parseable": True,
                    "evidence_response_type": type(raw).__name__,
                },
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            ),
        )

    values: dict[str, object] = {}
    anchors: dict[str, object] = {}
    role_evidence: dict[str, object] = {}
    # CAST-RATIONALE-INVOICE-RESPONSE-KEYED: a stdlib boundary: `json.loads`
    # returns `Any`, so the `isinstance` narrow above yields a mapping of
    # unknowns and the suffix tests below would be unchecked. The cast asserts
    # only what the JSON grammar already guarantees -- an object's keys are
    # strings -- and leaves the values opaque for the strict models to validate.
    keyed = cast("dict[str, object]", raw)
    for key, value in keyed.items():
        # Role evidence is tested FIRST because the two suffixes are independent
        # strings a later edit could make overlap; ordering the more specific
        # test ahead means such an overlap misroutes nothing silently, and the
        # suffix-parity gate still catches the declaration itself.
        if key.endswith(ROLE_EVIDENCE_KEY_SUFFIX):
            role_evidence[key[: -len(ROLE_EVIDENCE_KEY_SUFFIX)]] = value
        elif key.endswith(ANCHOR_KEY_SUFFIX):
            anchors[key[: -len(ANCHOR_KEY_SUFFIX)]] = value
        else:
            values[key] = value

    try:
        return ExtractedInvoiceResponse(
            fields=ExtractedInvoiceFields.model_validate(values),
            anchors=ExtractedFieldAnchors.model_validate(anchors),
            role_evidence=ExtractedRoleEvidence.model_validate(role_evidence),
        )
    except ValueError as exc:
        raise PurchaseInvoiceEvidenceInputError(
            context={"evidence_response_validation_error_type": type(exc).__name__},
            precondition_verdict=llm_no_recovery_verdict(
                LLMPreconditionCondition.EVIDENCE_RESPONSE_SCHEMA_VALID,
                facts={
                    "evidence_response_schema_valid": False,
                    "evidence_response_validation_error_type": type(exc).__name__,
                },
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            ),
        ) from exc


def _grounded_intra_community_tax_id(normalised: str) -> str | None:
    """Return *normalised* if it matches its own country's published NIF-IVA pattern.

    The country is read off the number's own two-character IVA prefix, because
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
    a Spanish-shaped number carries no EU IVA prefix and fails there too.

    Routing every identifier through the Spanish validator alone silently
    discarded a *correct* read of a valid foreign IVA number, which is the entire
    Modelo 349 / intra-EU reverse-charge population: a supplier invoicing from
    Ireland or Germany reached the operator with no identifier at all.
    """
    if raw is None:
        return None
    try:
        return validate_spanish_tax_id(raw)
    except IdentityError:
        return _grounded_intra_community_tax_id(normalise_nif_iva(raw))


def _grounded_free_text(raw: str | None) -> str | None:
    """Return an opaque printed token trimmed of surrounding whitespace, or ``None``.

    Named for the FORM it validates rather than for a field, like every other
    validator in the two dispatch tables. It was named for the invoice number
    when that was the only free-text field declared; it now serves six -- both
    postal codes, both printed countries, the invoice number and the regime
    legend -- and a validator named after one of the six reads as a rule about
    invoice numbers that the other five are borrowing. The tables dispatch on
    :class:`~llm.invoice_field_contract.InvoiceFieldForm`, so the form is what
    the name must say.

    Deliberately the weakest validator of the set, and that is the declared
    contract rather than an omission: a free-text field is an opaque token the
    document printed, so there is no independent authority to check it against.
    A field needing one declares a different form.
    """
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
    :data:`~core.parsing._dates._DateFmt` members are ever passed -- an invented
    format string silently degrades to one of the two delegates
    (:func:`~core.parsing._dates._parse_date` has no third branch), which would
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


def _grounded_percentage(raw: str | None) -> Decimal | None:
    """Return a transcribed rate as a bare Decimal, dropping the printed unit.

    The declared form for a rate is *the bare number*
    (:attr:`~llm.invoice_field_contract.InvoiceFieldForm.PERCENTAGE_RATE`), but
    a document prints ``IVA (21%)`` and a model obeying "copy exactly as
    printed" returns ``"21%"``. Routed through :func:`_grounded_decimal` that
    lost the field outright -- measured on a corpus invoice, where the model
    that read the rate *more* literally was the one punished for it.

    A percent sign is a UNIT MARKER, not a digit, so removing it is unit
    normalisation and the number that remains is still the one the document
    printed -- copied, never computed. Nothing about anti-fabrication is
    weakened: the anchor
    (:attr:`ExtractedInvoiceFields.iva_rate`) still holds ``"21%"`` verbatim for
    a later closure check to point at, so anchor and value stay explicitly
    distinct rather than collapsing into one field that could silently
    launder a transcription error into a computed figure. Exactly one
    trailing unit is stripped; a value carrying digits
    after the sign, or any other stray character, still fails the decimal
    authority and drops to ``None``.

    Deliberately NOT applied to a monetary amount. A percent sign on an amount
    is a misread, not a unit, and tolerating it there would launder a bad
    transcription into a filing figure.
    """
    if raw is None:
        return None
    text = raw.strip()
    for unit in ("%", "percent", "pct"):
        if text.lower().endswith(unit):
            text = text[: -len(unit)].strip()
            break
    return _grounded_decimal(text)


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
    try:
        return normalise_iso_4217_currency(raw)
    except CoreValidationError:
        return None


_TEXT_GROUNDING_BY_FORM: Mapping[InvoiceFieldForm, Callable[[str | None], str | None]] = {
    InvoiceFieldForm.TAX_IDENTIFIER: _grounded_tax_id,
    InvoiceFieldForm.FREE_TEXT: _grounded_free_text,
    InvoiceFieldForm.CALENDAR_DATE: _grounded_date,
    InvoiceFieldForm.CURRENCY_CODE: _grounded_currency,
}
"""Validators for the declared forms whose grounded value stays a string."""

_NUMERIC_GROUNDING_BY_FORM: Mapping[InvoiceFieldForm, Callable[[str | None], Decimal | None]] = {
    InvoiceFieldForm.MONETARY_AMOUNT: _grounded_decimal,
    InvoiceFieldForm.PERCENTAGE_RATE: _grounded_percentage,
}
"""Validators for the declared forms whose grounded value becomes a Decimal.

Split from :data:`_TEXT_GROUNDING_BY_FORM` by RETURN TYPE, not by convenience:
one table would have to be typed as a union and every call site would need a
runtime narrow, trading a static guarantee for a dead branch. Together the two
tables must cover :class:`~llm.invoice_field_contract.InvoiceFieldForm`
exactly and disjointly, which the parity gate asserts -- so a form added to the
enum without a validator fails there rather than falling through at runtime.
"""


def _ground_text(raw: str | None, field_name: str) -> str | None:
    """Ground ``raw`` through the validator ``field_name``'s DECLARED form selects.

    Raises:
        KeyError: When the field's declared form has no string-valued validator,
            which is a declaration error the parity gate exists to catch.
    """
    return _TEXT_GROUNDING_BY_FORM[contract_for_field(field_name).form](raw)


def _ground_numeric(raw: str | None, field_name: str) -> Decimal | None:
    """Ground ``raw`` through the validator ``field_name``'s DECLARED form selects.

    Raises:
        KeyError: When the field's declared form has no numeric validator, which
            is a declaration error the parity gate exists to catch.
    """
    return _NUMERIC_GROUNDING_BY_FORM[contract_for_field(field_name).form](raw)


def _read_provenance(
    *,
    field_name: str,
    value: str | Decimal | None,
    anchor: str | None,
    role_evidence: str | None,
    origin: FieldOrigin,
) -> FieldProvenance | None:
    """Return the envelope recording how ``field_name`` was read, or ``None``.

    ``None`` when the field carries no grounded value: an envelope describes a
    value's provenance, and a field the grounder dropped has no value to
    describe. The absence is itself reviewable -- the draft's own contract says
    a missing envelope never means the value was exact.

    The outcome is always :attr:`~core.FieldGroundingOutcome.UNANCHORED`, and
    that is a deliberate under-claim rather than a placeholder. The model
    REPORTING an anchor is a claim about the document, not a check against it;
    the check belongs to :func:`~application.ledger.grounding_anchor.evaluate_anchor`, which
    needs the transcription this stage does not hold. ``UNANCHORED`` is the only
    member that is true here: ``ANCHORED`` would assert a search nobody ran,
    ``RECONCILED`` an independent identity nobody consulted, ``CONTRADICTED`` a
    disagreement nobody found, and ``AMBIGUOUS`` is refused outright by the
    envelope without two competing candidates.

    The anchor still rides along, which is the point of the record: it is the
    claim a later stage verifies. Carrying it under an unverified outcome
    matches how the anchor check itself reports a contradiction -- the printed
    form the operator needs to see survives the outcome that failed.
    """
    if value is None:
        return None
    claimed = anchor.strip() if anchor is not None else ""
    claimed_role = role_evidence.strip() if role_evidence is not None else ""
    return FieldProvenance(
        field=field_name,
        origin=origin,
        grounding=FieldGroundingOutcome.UNANCHORED,
        anchor=claimed or None,
        # Recorded as the model REPORTED it, unchecked, exactly like the anchor
        # beside it. The check needs the transcription this stage does not hold
        # and runs at the grounding stage, which drops an excerpt the document
        # does not contain rather than trusting it.
        role_evidence=claimed_role or None,
        note=(
            f"the reading model reported {claimed!r} as the printed form; not yet checked against the document"
            if claimed
            else "the reading model reported no printed form for this value"
        ),
    )


def _unverified_identity_findings(
    response: ExtractedInvoiceResponse,
    grounded: Mapping[str, str | Decimal | None],
) -> tuple[DraftDiscrepancyFinding, ...]:
    """Record every identity field the document printed and the checks rejected.

    Dropping a value to ``None`` is the right handling and stays; what must not
    also be dropped is the FACT that something was there. An identifier failing
    its control character is precisely what hides the true counterparty from a
    validating read, so an operator needs "we could not verify this" rather than
    a slot that looks like the document said nothing.

    Without this the two collapse before anything can tell them apart. The
    counterparty role resolution reads the DRAFT, so a rejected identifier
    reaches it as an absence -- and
    :func:`~application.ledger.identity_roles.resolve_counterparty_identity` deliberately
    raises no unresolved-role finding on an absence, because a factura
    simplificada legitimately has one. The distinction has to be preserved at
    the stage that performs the rejection; nothing downstream can reconstruct
    it.

    Args:
        response: The parsed reply, whose ``fields`` half still carries the
            verbatim transcribed strings.
        grounded: The re-validated values, keyed by field name.

    Returns:
        One finding per identity field transcribed non-blank and rejected.
    """
    findings: list[DraftDiscrepancyFinding] = []
    for contract in INVOICE_FIELD_CONTRACTS:
        # Keyed on the DECLARED form, like every other identity-scoped decision
        # in this module, so a fourth identity field is covered by construction.
        if not contract.carries_role_evidence:
            continue
        transcribed = getattr(response.fields, contract.field_name, None)
        if not isinstance(transcribed, str) or not transcribed.strip():
            continue
        if grounded[contract.field_name] is not None:
            continue
        findings.append(
            DraftDiscrepancyFinding(
                kind=DraftDiscrepancyKind.IDENTITY_UNVERIFIED,
                field=contract.field_name,
                detail=(
                    f"the document prints {transcribed.strip()!r} as this party's tax identifier, but it "
                    f"fails its control-character check, so it was not accepted as a verified identity"
                ),
            ),
        )
    return tuple(findings)


def ground_extracted_fields(
    response: ExtractedInvoiceResponse,
    *,
    raw_text_length: int,
    origin: FieldOrigin,
) -> InvoiceDraft:
    """Re-validate the model's transcribed strings into a grounded :class:`InvoiceDraft`.

    Each field is grounded through the validator its DECLARED form selects
    (:data:`~llm.invoice_field_contract.INVOICE_FIELD_CONTRACTS`), the same
    declaration the compiled prompt renders its per-field guidance from, so the
    two sides cannot state different expectations. A field left ungrounded here
    fails the parity gate's fully-populated round.

    A field the model transcribed but that fails grounded validation (an invalid
    tax-id checksum, an unparsable date, a non-numeric amount) is dropped to
    ``None`` rather than trusted -- the same "never fabricate" discipline the
    text-layer heuristics apply. For an IDENTITY field the rejection is also
    RECORDED, as an
    :attr:`~core.DraftDiscrepancyKind.IDENTITY_UNVERIFIED` finding: dropping the
    value is right, dropping the fact that the document printed one is not, and
    only this stage still holds that fact.

    Every field that survives grounding also gets a
    :class:`~application.ledger.evidence_draft.FieldProvenance` envelope carrying the verbatim
    anchor the model reported for it, so no value reaches the operator without
    the printed form it claims to have come from.

    Args:
        response: The parsed, not-yet-grounded reply. Left untouched: its anchor
            half carries the verbatim printed forms.
        raw_text_length: How much source material the reader had to work with.
        origin: How these values were obtained. Required rather than defaulted:
            a reader that could omit it would silently claim whichever origin was
            most convenient, and the exact-versus-probabilistic distinction is
            the one thing the record exists to keep honest.

    Returns:
        :class:`InvoiceDraft`: The grounded draft, one provenance envelope per
        field that carries a value.
    """
    fields = response.fields
    supplier_tax_id = _ground_text(fields.supplier_tax_id, "supplier_tax_id")
    supplier_name = _ground_text(fields.supplier_name, "supplier_name")
    supplier_postal_code = _ground_text(fields.supplier_postal_code, "supplier_postal_code")
    supplier_country = _ground_text(fields.supplier_country, "supplier_country")
    customer_tax_id = _ground_text(fields.customer_tax_id, "customer_tax_id")
    customer_name = _ground_text(fields.customer_name, "customer_name")
    customer_postal_code = _ground_text(fields.customer_postal_code, "customer_postal_code")
    customer_country = _ground_text(fields.customer_country, "customer_country")
    invoice_number = _ground_text(fields.invoice_number, "invoice_number")
    invoice_date = _ground_text(fields.invoice_date, "invoice_date")
    taxable_base = _ground_numeric(fields.taxable_base, "taxable_base")
    iva_rate = _ground_numeric(fields.iva_rate, "iva_rate")
    iva_amount = _ground_numeric(fields.iva_amount, "iva_amount")
    retencion_rate = _ground_numeric(fields.retencion_rate, "retencion_rate")
    retencion_amount = _ground_numeric(fields.retencion_amount, "retencion_amount")
    grand_total = _ground_numeric(fields.grand_total, "grand_total")
    regime_legend = _ground_text(fields.regime_legend, "regime_legend")
    currency = _ground_text(fields.currency, "currency")

    # Keyed by the ONE contract declaration, so a field added there without a
    # grounded value here raises rather than travelling with no provenance.
    grounded: Mapping[str, str | Decimal | None] = {
        "supplier_tax_id": supplier_tax_id,
        "supplier_name": supplier_name,
        "supplier_postal_code": supplier_postal_code,
        "supplier_country": supplier_country,
        "customer_tax_id": customer_tax_id,
        "customer_name": customer_name,
        "customer_postal_code": customer_postal_code,
        "customer_country": customer_country,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "taxable_base": taxable_base,
        "iva_rate": iva_rate,
        "iva_amount": iva_amount,
        "retencion_rate": retencion_rate,
        "retencion_amount": retencion_amount,
        "grand_total": grand_total,
        "regime_legend": regime_legend,
        "currency": currency,
    }
    envelopes = tuple(
        envelope
        for contract in INVOICE_FIELD_CONTRACTS
        if (
            envelope := _read_provenance(
                field_name=contract.field_name,
                value=grounded[contract.field_name],
                anchor=getattr(response.anchors, contract.field_name),
                # Keyed off the contract's own declaration rather than a second
                # membership test, so a field that does not name a party cannot
                # acquire role evidence by an attribute happening to exist.
                role_evidence=(
                    getattr(response.role_evidence, contract.field_name, None)
                    if contract.carries_role_evidence
                    else None
                ),
                origin=origin,
            )
        )
        is not None
    )

    return InvoiceDraft(
        supplier_tax_id=supplier_tax_id,
        supplier_name=supplier_name,
        supplier_postal_code=supplier_postal_code,
        supplier_country=supplier_country,
        # The printed name ABOVE is the evidence; the code here is a derivation
        # of it, and both are kept for the same reason the numeric fields keep
        # what the document printed beside what it parsed to. The resolver is
        # the one the structured e-invoice lane already uses, so a name and a
        # machine-readable country element resolve through a single vocabulary.
        # A name the vocabulary does not carry stays absent rather than becoming
        # the nearest match: every consumer of this field branches domestic
        # versus not, and none can express that the question went unanswered.
        supplier_country_code=country_code_for_printed_country_name(supplier_country),
        customer_tax_id=customer_tax_id,
        customer_name=customer_name,
        customer_postal_code=customer_postal_code,
        customer_country=customer_country,
        customer_country_code=country_code_for_printed_country_name(customer_country),
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        taxable_base=taxable_base,
        iva_rate=iva_rate,
        iva_amount=iva_amount,
        retencion_rate=retencion_rate,
        retencion_amount=retencion_amount,
        grand_total=grand_total,
        regime_legend=regime_legend,
        currency=currency,
        provenance=envelopes,
        discrepancies=_unverified_identity_findings(response, grounded),
        raw_text_length=raw_text_length,
    )
