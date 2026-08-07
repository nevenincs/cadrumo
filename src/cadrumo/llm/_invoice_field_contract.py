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
:class:`~llm._invoice_field_grounding.ExtractedInvoiceFields`), and both sides
derive from it: :mod:`._invoice_extraction_prompt` renders each row's
``form_instruction`` into the compiled prompt, and
:func:`~llm._invoice_field_grounding.ground_extracted_fields` dispatches each
row's :class:`InvoiceFieldForm` to the matching grounding validator. Two
hand-maintained lists that happen to agree today is the defect this closes, not
the fix.

**Anchor and value are deliberately distinct** (ADR
``2026-08-07-unstructured-document-ingestion-adr`` D4, anti-fabrication as
anchoring plus closure). Nothing here rewrites what the model transcribed:
:class:`~llm._invoice_field_grounding.ExtractedInvoiceFields` keeps the printed
string verbatim, which is the anchor a later closure check points at. The form
declaration governs only the DERIVATION of the typed value from that anchor. For
``IVA (21%)`` the anchor stays ``"21%"`` and the value becomes ``21``, which
serves anchoring rather than fighting it: the percent sign is a unit marker, not
a digit, so dropping it is unit normalisation and the number is still *copied*,
never computed.

See Also:
    :func:`~llm._invoice_field_grounding.ground_extracted_fields`
        Grounding side, which dispatches on :class:`InvoiceFieldForm`.
    :func:`~llm._invoice_extraction_prompt.build_invoice_extraction_prompt`
        Prompt side, which renders :attr:`InvoiceFieldContract.form_instruction`.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from ..core import STRICT_FROZEN_CONFIG

__all__ = [
    "INVOICE_FIELD_CONTRACTS",
    "InvoiceFieldContract",
    "InvoiceFieldForm",
    "contract_for_field",
]


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
            :class:`~llm._invoice_field_grounding.ExtractedInvoiceFields`. The
            parity gate proves this set equals that model's field set exactly,
            in both directions.
        form: The printed form the value must arrive in, dispatching the
            grounding validator.
        concept: What the field MEANS, phrased without naming a label in any
            particular language, because documents in scope are international.
        form_instruction: The per-field micro-guidance line rendered into the
            compiled prompt. Kept short: the design target is a lowest-bound
            vision model with a very small context budget.
    """

    model_config = STRICT_FROZEN_CONFIG

    field_name: str = Field(min_length=1)
    form: InvoiceFieldForm
    concept: str = Field(min_length=1)
    form_instruction: str = Field(min_length=1)


INVOICE_FIELD_CONTRACTS: tuple[InvoiceFieldContract, ...] = (
    InvoiceFieldContract(
        field_name="supplier_tax_id",
        form=InvoiceFieldForm.TAX_IDENTIFIER,
        concept="the issuing party's tax identification number",
        form_instruction="copy the identifier as printed, including any country prefix; no spaces",
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
        concept="the VAT/IVA percentage the tax was charged at",
        form_instruction="the bare number, without a percent sign",
    ),
    InvoiceFieldContract(
        field_name="iva_amount",
        form=InvoiceFieldForm.MONETARY_AMOUNT,
        concept="the VAT/IVA tax amount",
        form_instruction="digits only, keeping the printed decimal separator; no currency sign",
    ),
    InvoiceFieldContract(
        field_name="grand_total",
        form=InvoiceFieldForm.MONETARY_AMOUNT,
        concept="the total payable amount",
        form_instruction="digits only, keeping the printed decimal separator; no currency sign",
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
:class:`~llm._invoice_field_grounding.ExtractedInvoiceFields` (or the reverse)
fails that gate, which is the whole reason the tuple exists.
"""


def contract_for_field(field_name: str) -> InvoiceFieldContract:
    """Return the declared contract for ``field_name``.

    Args:
        field_name: Attribute name on
            :class:`~llm._invoice_field_grounding.ExtractedInvoiceFields`.

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
