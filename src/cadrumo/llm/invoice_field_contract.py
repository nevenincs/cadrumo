"""The one declaration of what FORM each extracted invoice field must arrive in.

The reading prompt and the grounded re-validation step both need an answer to
"what shape is this field's value?", and until this module existed each held its
own. The prompt's prose said *copy the value exactly as printed*; the grounder
required a bare :class:`~decimal.Decimal`. On an invoice printing ``IVA (21%)``
those two answers disagree, and the disagreement was measured: a model that
obeyed the prompt literally returned ``"21%"`` and lost the field entirely, while
a model that quietly normalised to ``"21"`` was accepted. The reading was correct
both times; only the contract was ambiguous.

So the form is declared ONCE here, as typed data
(:class:`InvoiceFieldContract`, one row per field of
:class:`~llm.invoice_field_grounding.ExtractedInvoiceFields`), and both sides
derive from it: :mod:`._invoice_extraction_prompt` renders each row's
``form_instruction`` into the compiled prompt, and
:func:`~llm.invoice_field_grounding.ground_extracted_fields` dispatches each
row's :class:`InvoiceFieldForm` to the matching grounding validator. Two
hand-maintained lists that happen to agree today is the defect this closes, not
the fix.

**Anchor and value are deliberately distinct**: anti-fabrication works by
anchoring the model's transcription and closing over it, never by rewriting
what it said. Nothing here rewrites what the model transcribed:
:class:`~llm.invoice_field_grounding.ExtractedInvoiceFields` keeps the printed
string verbatim, which is the anchor a later closure check points at. The form
declaration governs only the DERIVATION of the typed value from that anchor. For
``IVA (21%)`` the anchor stays ``"21%"`` and the value becomes ``21``, which
serves anchoring rather than fighting it: the percent sign is a unit marker, not
a digit, so dropping it is unit normalisation and the number is still *copied*,
never computed.

See Also:
    :func:`~llm.invoice_field_grounding.ground_extracted_fields`
        Grounding side, which dispatches on :class:`InvoiceFieldForm`.
    :func:`~llm.invoice_extraction_prompt.build_invoice_extraction_prompt`
        Prompt side, which renders :attr:`InvoiceFieldContract.form_instruction`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel, Field, model_validator

from ..core import STRICT_FROZEN_CONFIG

__all__ = [
    "ANCHOR_KEY_SUFFIX",
    "INVOICE_FIELD_CONTRACTS",
    "ROLE_EVIDENCE_KEY_SUFFIX",
    "InvoiceFieldContract",
    "InvoiceFieldForm",
    "anchor_key_for_field",
    "contract_for_field",
    "identity_field_names",
    "role_evidence_key_for_field",
]

ANCHOR_KEY_SUFFIX: Final[str] = "_anchor"
"""Suffix naming a field's anchor key in the model's JSON response.

Declared here rather than at either use site because three derivations depend on
it agreeing exactly: the compiled prompt renders the key it asks for, the parser
reads the key it receives, and the parity gate proves the two are the same
string. A suffix spelled twice is the same drift this module exists to close --
and its failure mode is silent, because an anchor key the parser does not
recognise looks identical to a model that returned no anchor at all.
"""


def anchor_key_for_field(field_name: str) -> str:
    """Return the JSON key carrying ``field_name``'s verbatim printed anchor.

    Args:
        field_name: Attribute name on
            :class:`~llm.invoice_field_grounding.ExtractedInvoiceFields`.

    Returns:
        The anchor key, e.g. ``"iva_rate_anchor"``.
    """
    return f"{field_name}{ANCHOR_KEY_SUFFIX}"


ROLE_EVIDENCE_KEY_SUFFIX: Final[str] = "_role_evidence"
"""Suffix naming an identity field's role-evidence key in the model's JSON response.

Declared beside :data:`ANCHOR_KEY_SUFFIX` and for the same reason: the compiled
prompt renders the key it asks for, the parser reads the key it receives, and a
suffix spelled twice drifts silently, because a key the parser does not
recognise is indistinguishable from a model that returned nothing.

**This is a second anchor, not a second note.** An anchor answers *where on the
page did this value come from*; role evidence answers *what on the page assigns
that value to THIS party*. Both are printed excerpts, both are checked against
the transcription, and neither is the reader's own account of what it did. That
distinction is the whole point of the key existing: the reading stage previously
manufactured ``"the reader assigned this identifier to supplier_tax_id"``, which
is a restatement of the assignment rather than evidence for it, and being
always truthy it permanently satisfied the guard that exists to refuse an
unevidenced identity.
"""


def role_evidence_key_for_field(field_name: str) -> str:
    """Return the JSON key carrying ``field_name``'s printed role evidence.

    Args:
        field_name: Attribute name of an identity field on
            :class:`~llm.invoice_field_grounding.ExtractedInvoiceFields`.

    Returns:
        The role-evidence key, e.g. ``"supplier_tax_id_role_evidence"``.
    """
    return f"{field_name}{ROLE_EVIDENCE_KEY_SUFFIX}"


class InvoiceFieldForm(StrEnum):
    """Closed set of printed forms an extracted invoice field can arrive in.

    A member names the SHAPE the emitted value must have, never the field it
    belongs to: ``taxable_base``, ``iva_amount`` and ``grand_total`` are three
    fields with one form, and adding a fourth monetary field must not need a
    fourth grounding branch.
    """

    TAX_IDENTIFIER = "tax_identifier"
    """A tax identification number, checksum- or VIES-structure-validated."""

    FREE_TEXT = "free_text"
    """An opaque printed token kept verbatim (an invoice reference)."""

    CALENDAR_DATE = "calendar_date"
    """A date, kept in whatever order the document prints it."""

    MONETARY_AMOUNT = "monetary_amount"
    """Digits with the printed decimal separator preserved, no currency sign."""

    PERCENTAGE_RATE = "percentage_rate"
    """A bare rate number; the printed percent sign is a unit, not a digit."""

    CURRENCY_CODE = "currency_code"
    """A three-letter ISO-4217 alphabetic code."""


class InvoiceFieldContract(BaseModel):
    """The declared contract for one extracted invoice field.

    Attributes:
        field_name: Attribute name on
            :class:`~llm.invoice_field_grounding.ExtractedInvoiceFields`. The
            parity gate proves this set equals that model's field set exactly,
            in both directions.
        form: The printed form the value must arrive in, dispatching the
            grounding validator.
        concept: What the field MEANS, phrased without naming a label in any
            particular language, because documents in scope are international.
        form_instruction: The per-field micro-guidance line rendered into the
            compiled prompt. Kept short: the design target is a lowest-bound
            vision model with a very small context budget.
        role_evidence_instruction: How to answer "what on the page assigns this
            value to THIS party". Present exactly on the identity fields and
            absent everywhere else, which the validator below enforces in both
            directions rather than leaving to the author.
    """

    model_config = STRICT_FROZEN_CONFIG

    field_name: str = Field(min_length=1)
    form: InvoiceFieldForm
    concept: str = Field(min_length=1)
    form_instruction: str = Field(min_length=1)
    role_evidence_instruction: str | None = Field(default=None, min_length=1)

    @property
    def carries_role_evidence(self) -> bool:
        """Whether this field is an identity field and so must evidence its role.

        Derived from the declared FORM rather than from a hand-listed field set.
        A tax identifier is the only kind of value on an invoice that names a
        PARTY, so "which party is this" is a question only this form raises --
        and deriving it means a fourth identity field added to the table asks
        for role evidence by construction instead of by remembering.
        """
        return self.form is InvoiceFieldForm.TAX_IDENTIFIER

    @model_validator(mode="after")
    def _only_an_identity_field_evidences_a_role(self) -> Self:
        """Tie the role-evidence instruction to the form that needs one.

        Enforced in both directions. An identity field without the instruction
        would be asked for an identifier and never for what assigns it to a
        party, which is the exact gap that let a lone survivor be promoted; and
        the instruction on a monetary or date field would ask a model to
        evidence a role that value does not have, inviting it to invent one.
        """
        if self.carries_role_evidence and self.role_evidence_instruction is None:
            raise ValueError(
                f"{self.field_name!r} is an identity field, so it must declare how its role is evidenced",
            )
        if not self.carries_role_evidence and self.role_evidence_instruction is not None:
            raise ValueError(
                f"role evidence is only meaningful for an identity field; got form={self.form.value!r}",
            )
        return self


INVOICE_FIELD_CONTRACTS: tuple[InvoiceFieldContract, ...] = (
    # An invoice prints TWO parties, and which one a downstream informativa needs
    # depends on the document's direction, which the reader does not know. So both
    # are asked for, separately and by role. Asking for one identifier and letting
    # the caller decide whose it was is what made the two indistinguishable: the
    # single recovered value landed on the issuer side regardless of which party
    # it actually named.
    InvoiceFieldContract(
        field_name="supplier_tax_id",
        form=InvoiceFieldForm.TAX_IDENTIFIER,
        concept="the tax identification number of the party who ISSUED the invoice and is owed the money",
        form_instruction=(
            "copy the identifier as printed, including any country prefix; no spaces; "
            "this is the issuer's own identifier, not the identifier of the party being billed"
        ),
        role_evidence_instruction=(
            "copy the printed heading, label or line that shows this identifier belongs to the ISSUER, "
            "exactly as it appears; null if the document shows nothing that does"
        ),
    ),
    # The party's NAME, asked beside its identifier for the same pairing reason
    # the postal code is. It carries no role-evidence key and that is a ruling
    # rather than an omission: the evidence keys stay at two because the
    # design-target model's context budget is a hard constraint and a key with no
    # consumer is review theatre. The name does not need one -- it is not a value
    # whose PARTY is in doubt separately from the identifier it sits beside, it is
    # the thing a reader would quote to evidence that identifier's role. Asking
    # for evidence OF the name would be asking what assigns the name to the party
    # whose name it is.
    InvoiceFieldContract(
        field_name="supplier_name",
        form=InvoiceFieldForm.FREE_TEXT,
        concept="the registered or trading name of the party who ISSUED the invoice and is owed the money",
        form_instruction=(
            "copy the name alone exactly as printed, without the address, the tax identifier "
            "or any legal-form suffix the document does not print; "
            "this is the issuer's own name, not the name of the party being billed"
        ),
    ),
    # Kept adjacent to the identifier it belongs to, for the reason the anchor
    # key sits beside its field in the JSON skeleton: a small model pairs two
    # facts about ONE party most reliably when they are asked for together.
    InvoiceFieldContract(
        field_name="supplier_postal_code",
        form=InvoiceFieldForm.FREE_TEXT,
        concept="the postal code printed in the postal address of the party who ISSUED the invoice",
        form_instruction=(
            "copy the postal code alone as printed, without the town, province or country; "
            "this is the issuer's own address, not the address of the party being billed"
        ),
    ),
    # Asked as the NAME the document prints, never as an alpha-2 code. A country
    # prints in the issuer's own language -- "Alemania", "Deutschland",
    # "Allemagne" -- so asking a reader for `DE` would be asking it to translate,
    # and translation is inference in the same sentence that forbids it. The
    # bounded registry vocabulary does the lookup downstream
    # (:func:`~domain.iva.country_code_for_printed_country_name`), which is a
    # deterministic match rather than a judgement, so the reader's whole job here
    # is transcription.
    InvoiceFieldContract(
        field_name="supplier_country",
        form=InvoiceFieldForm.FREE_TEXT,
        concept="the country printed in the postal address of the party who ISSUED the invoice",
        form_instruction=(
            "copy the country name alone exactly as printed, in the document's own language, "
            "without translating it and without abbreviating it to a code; "
            "this is the issuer's own address, not the address of the party being billed"
        ),
    ),
    InvoiceFieldContract(
        field_name="customer_tax_id",
        form=InvoiceFieldForm.TAX_IDENTIFIER,
        concept="the tax identification number of the party BILLED by the invoice, who owes the money",
        form_instruction=(
            "copy the identifier as printed, including any country prefix; no spaces; "
            "leave empty unless the document prints a second identifier for the party being billed"
        ),
        role_evidence_instruction=(
            "copy the printed heading, label or line that shows this identifier belongs to the party "
            "BEING BILLED, exactly as it appears; null if the document shows nothing that does"
        ),
    ),
    InvoiceFieldContract(
        field_name="customer_name",
        form=InvoiceFieldForm.FREE_TEXT,
        concept="the registered or trading name of the party BILLED by the invoice, who owes the money",
        form_instruction=(
            "copy the name alone exactly as printed, without the address, the tax identifier "
            "or any legal-form suffix the document does not print; "
            "leave empty unless the document prints a name for the party being billed"
        ),
    ),
    InvoiceFieldContract(
        field_name="customer_postal_code",
        form=InvoiceFieldForm.FREE_TEXT,
        concept="the postal code printed in the postal address of the party BILLED by the invoice",
        form_instruction=(
            "copy the postal code alone as printed, without the town, province or country; "
            "leave empty unless the document prints an address for the party being billed"
        ),
    ),
    InvoiceFieldContract(
        field_name="customer_country",
        form=InvoiceFieldForm.FREE_TEXT,
        concept="the country printed in the postal address of the party BILLED by the invoice",
        form_instruction=(
            "copy the country name alone exactly as printed, in the document's own language, "
            "without translating it and without abbreviating it to a code; "
            "leave empty unless the document prints an address for the party being billed"
        ),
    ),
    InvoiceFieldContract(
        field_name="invoice_number",
        form=InvoiceFieldForm.FREE_TEXT,
        concept="the invoice's own reference number",
        form_instruction="copy as printed, including any prefix or series",
    ),
    InvoiceFieldContract(
        field_name="invoice_date",
        form=InvoiceFieldForm.CALENDAR_DATE,
        concept="the invoice issue date",
        form_instruction="copy as printed; keep the document's own day/month order",
    ),
    InvoiceFieldContract(
        field_name="taxable_base",
        form=InvoiceFieldForm.MONETARY_AMOUNT,
        concept="the net amount before tax",
        form_instruction="digits only, keeping the printed decimal separator; no currency sign",
    ),
    InvoiceFieldContract(
        field_name="iva_rate",
        form=InvoiceFieldForm.PERCENTAGE_RATE,
        concept="the IVA percentage the tax was charged at",
        form_instruction="the bare number, without a percent sign",
    ),
    InvoiceFieldContract(
        field_name="iva_amount",
        form=InvoiceFieldForm.MONETARY_AMOUNT,
        concept="the IVA tax amount",
        form_instruction="digits only, keeping the printed decimal separator; no currency sign",
    ),
    InvoiceFieldContract(
        field_name="retencion_rate",
        form=InvoiceFieldForm.PERCENTAGE_RATE,
        concept="the income-tax withholding percentage the issuer deducted, if any",
        form_instruction="the bare number, without a percent sign or a minus sign",
    ),
    InvoiceFieldContract(
        field_name="retencion_amount",
        form=InvoiceFieldForm.MONETARY_AMOUNT,
        concept="the income-tax amount withheld and deducted from the total",
        form_instruction="digits only, keeping the printed decimal separator; no currency or minus sign",
    ),
    InvoiceFieldContract(
        field_name="grand_total",
        form=InvoiceFieldForm.MONETARY_AMOUNT,
        concept=(
            "the total payable amount exactly as printed on the document, copied even when it does "
            "not equal the sum of the base and the tax; never recompute it and never correct it"
        ),
        form_instruction="digits only, keeping the printed decimal separator; no currency sign",
    ),
    InvoiceFieldContract(
        field_name="regime_legend",
        form=InvoiceFieldForm.FREE_TEXT,
        concept="a printed statement that a special IVA regime applies to this operation",
        form_instruction="copy the phrase exactly as printed if one appears; otherwise null",
    ),
    InvoiceFieldContract(
        field_name="currency",
        form=InvoiceFieldForm.CURRENCY_CODE,
        concept="the currency the amounts are printed in",
        form_instruction="the three-letter ISO-4217 code, read from the printed symbol or code",
    ),
)
"""Every extracted field's declared form, in the order the prompt lists them.

This tuple is the single declaration the parity gate binds both derivations to.
Adding a field here without adding it to
:class:`~llm.invoice_field_grounding.ExtractedInvoiceFields` (or the reverse)
fails that gate, which is the whole reason the tuple exists.
"""


def identity_field_names() -> tuple[str, ...]:
    """Return the declared fields that name a party and so must evidence a role.

    Derived from :data:`INVOICE_FIELD_CONTRACTS` rather than restated, so the
    payload schema, the prompt and the grounding stage cannot disagree about
    which fields carry role evidence. A hand-listed set is how a family ends up
    half-covered: the collection describes the enrolled set while enforcing
    nothing about it.

    Returns:
        The identity field names, in declaration order.
    """
    return tuple(contract.field_name for contract in INVOICE_FIELD_CONTRACTS if contract.carries_role_evidence)


def contract_for_field(field_name: str) -> InvoiceFieldContract:
    """Return the declared contract for ``field_name``.

    Args:
        field_name: Attribute name on
            :class:`~llm.invoice_field_grounding.ExtractedInvoiceFields`.

    Returns:
        :class:`InvoiceFieldContract`: The declared contract.

    Raises:
        KeyError: When no contract is declared for ``field_name``. Raising is
            correct rather than returning a permissive default: an undeclared
            field has no agreed form, so grounding it would be a guess.
    """
    for contract in INVOICE_FIELD_CONTRACTS:
        if contract.field_name == field_name:
            return contract
    raise KeyError(field_name)
