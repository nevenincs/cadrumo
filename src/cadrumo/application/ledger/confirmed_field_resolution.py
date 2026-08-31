"""Resolving one confirmed field from the operator's statement and the document.

Extraction is best-effort, so every field a confirm persists may be corrected.
The layering rule is named once here rather than restated per field
(:func:`_operator_value_or_reading`): an explicit operator value outranks the
reading, and a field that quietly inverted the order would prefer a misread
document over the person confirming it. The three fields that do NOT simply
layer -- currency, counterparty name, invoice date -- each carry their own
resolver stating why, and a field neither side supplies refuses through
:func:`_require_confirmed_field` rather than reaching the catalogue empty.

Two resolutions read the document's own per-rate breakdown rather than a single
flat triple, and both are skipped the moment the operator restates any of the
base, rate or cuota (:func:`_operator_restated_the_amounts`), because their
figures are then the authority and two authorities on one set of amounts is
exactly the condition that must not arise:

- :func:`domestic_rate_tier_from_the_document` answers which domestic rate tier
  the document charged, against the rates in force on the invoice's own issue
  date, and DECLINES rather than approximating whenever the document does not
  settle it unambiguously.
- :func:`_confirmed_lines_from_the_document` preserves WHICH part of the base
  carried which rate, which Modelo 303 needs because it sums cuota devengada per
  tier.

Nothing here persists anything or reaches a model; every function is a pure
resolution over the draft plus the operator's arguments.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...adapters.inbound.einvoice._parsers import FacturaeInvoiceClass
from ...application.invoices._creation import resolve_iva_rate_slot
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.parsing import parse_iso8601_date
from ...domain.invoices.enums import InvoiceClass
from ...domain.invoices.models import InvoiceLine
from ...domain.iva.lookup import rate_kinds_for_declared_rate
from ...domain.iva.schema import EUMemberState, IvaRateKind
from .evidence_errors import PurchaseInvoiceEvidenceInputError
from .invoice_draft_records import InvoiceDraft
from .preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict

__all__ = ["domestic_rate_tier_from_the_document"]


def _operator_value_or_reading[T](supplied: T | None, read: T) -> T:
    """Return the operator's value when they supplied one, else the document's.

    The layering rule every confirmable field follows, named once rather than
    restated per field. Extraction is best-effort, so an explicit operator value
    always outranks the reading; a field that quietly inverted the order would
    prefer a misread document over the person confirming it.
    """
    return supplied if supplied is not None else read


def _require_confirmed_field(value: Decimal | str | None, *, field: str) -> Decimal | str:
    if value is None:
        raise PurchaseInvoiceEvidenceInputError(
            translated_message="errors.refused.refused_ledger_evidence_input",
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.EVIDENCE_REQUIRED_FIELD_AVAILABLE,
                facts={"required_field_available": False},
            ),
        )
    return value


def _confirmed_currency(supplied: str | None, read: str | None) -> str:
    """Return the ISO-4217 code the invoice is minted in.

    Same override-on-extraction layering as every other field: an explicit
    operator value wins, else the currency actually printed on the document,
    else euro. Preferring the extracted code over the euro default is what stops
    a foreign-currency invoice being minted at its face value in euro. Falsy
    rather than ``None`` handling is deliberate here -- an empty printed code
    carries no more information than an absent one.
    """
    return (supplied or read or DEFAULT_CURRENCY).strip().upper()


def _confirmed_counterparty_name(supplied: str | None, read: str | None) -> str:
    """Return the counterparty display name, refusing when neither side states one.

    Unlike the tax id there is no extraction heuristic strong enough to stand
    alone, so a document naming nobody plus an operator supplying nothing is a
    refusal rather than an empty name reaching the catalogue.
    """
    resolved = (supplied or read or "").strip()
    if not resolved:
        raise PurchaseInvoiceEvidenceInputError(
            translated_message="errors.refused.refused_ledger_evidence_input",
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.EVIDENCE_REQUIRED_FIELD_AVAILABLE,
                facts={"counterparty_name_available": False},
            ),
        )
    return resolved


def _resolve_confirmed_invoice_date(invoice_date: date | None, draft: InvoiceDraft) -> date:
    if invoice_date is not None:
        return invoice_date
    if draft.invoice_date is not None:
        parsed = parse_iso8601_date(draft.invoice_date)
        if parsed is not None:
            return parsed
    raise PurchaseInvoiceEvidenceInputError(
        translated_message="errors.refused.refused_ledger_evidence_input",
        precondition_verdict=ledger_no_recovery_verdict(
            LedgerPreconditionCondition.EVIDENCE_INVOICE_DATE_AVAILABLE,
            facts={"invoice_date_available": False},
        ),
    )


def _resolved_invoice_class(
    draft: InvoiceDraft,
    *,
    invoice_class: InvoiceClass | None,
    rectifies_invoice_number: str | None,
) -> InvoiceClass:
    """Resolve Facturae class, preserving explicit operator and rectification facts."""
    declared_class = draft.facturae_invoice_class
    if declared_class in {FacturaeInvoiceClass.ORIGINAL, FacturaeInvoiceClass.COPY}:
        return InvoiceClass.ORDINARIA
    if declared_class in {
        FacturaeInvoiceClass.ORIGINAL_CORRECTIVE,
        FacturaeInvoiceClass.COPY_CORRECTIVE,
    }:
        return InvoiceClass.RECTIFICATIVA
    if invoice_class is not None:
        # Recapitulativa has no domain member; preserve the operator's statement.
        return invoice_class
    return InvoiceClass.RECTIFICATIVA if rectifies_invoice_number is not None else InvoiceClass.ORDINARIA


def _operator_restated_the_amounts(
    *,
    taxable_base: Decimal | None,
    iva_rate: Decimal | None,
    iva_amount: Decimal | None,
) -> bool:
    """Return whether the operator restated the invoice totals themselves.

    Any one of the three is a statement about the WHOLE invoice, which is why
    this single predicate gates both the rate tier the establishment ladder is
    handed and the per-rate line split. Two disagreeing authorities on the same
    figures is exactly the condition it exists to prevent, so the two decisions
    must never drift onto separately-derived answers.
    """
    return taxable_base is not None or iva_rate is not None or iva_amount is not None


def domestic_rate_tier_from_the_document(draft: InvoiceDraft, *, invoice_date: date) -> IvaRateKind | None:
    """Return the domestic rate tier the document's own lines charged, or ``None``.

    **A tier, not a category.** This resolution used to end in a domestic
    :class:`~domain.iva.IvaCategory`, which made it a second classifier sitting
    ahead of the rule table and reaching it never -- and it reached that
    category through :func:`~domain.iva.domestic_categories_by_rate_kind`, the
    exact mapping the table's own ``R05`` rule consults. Stopping at the tier
    keeps every one of the declines below and hands the answer to the table as
    a criteria axis, so the mapping is applied once, where the law is.

    :func:`~domain.iva.rate_kinds_for_declared_rate` answers which tier a
    declared rate WAS on a given date, against the registered rate records; it
    returns a tuple because that question can legitimately have more than one
    answer, so a caller detects ambiguity instead of picking one.

    The date is load-bearing and is the invoice's own issue date, not today's.
    A tier's rate changes by statute, so resolving a 2024 document against
    today's table would answer about a rate it was never charged at.

    Declines, rather than approximating, in three cases:

    - **More than one rate.** One invoice carries one category field and a
      two-tier document has two answers. Picking either declares part of the
      base under a rate it was not charged at, and picking by size is an
      invention. Which tier a multi-rate invoice takes is a modelling
      decision this resolution does not make.
    - **A recargo de equivalencia.** The rate resolves cleanly, but a supply
      carrying a recargo may belong to the ordinary domestic tier or to the
      recargo category, and the decomposition contract accepts BOTH -- so a
      wrong pick would be caught nowhere downstream. That is exactly the shape
      that must not be guessed.
    - **An unregistered or ambiguous rate.** A rate that was not a registered
      Spanish rate on the issue date is a real refusal rather than a lookup
      failure, and a rate matching two tiers is the ambiguity the tuple exists
      to surface.

    Declining is visible: the criteria carry no tier, the rule table refuses the
    domestic branch that needs one, and the resolution reports the operation
    unresolved. A guess would not be.

    Args:
        draft: The re-run extraction being confirmed.
        invoice_date: The resolved issue date the rate must be read against.

    Returns:
        The resolved :class:`~domain.iva.IvaRateKind`, or ``None`` when the
        document does not settle it unambiguously.
    """
    if len(draft.iva_breakdown) != 1:
        return None
    entry = draft.iva_breakdown[0]
    if entry.iva_rate is None:
        return None
    if entry.recargo_amount is not None or draft.recargo_amount is not None:
        return None
    # The lookup takes the rate as a FRACTION, matching how a transaction stores
    # it; the draft carries the bare percentage the document prints.
    tiers = rate_kinds_for_declared_rate(EUMemberState.ES, entry.iva_rate / Decimal("100"), invoice_date)
    if len(tiers) != 1:
        return None
    return tiers[0]


def _rate_tier_the_document_charged(
    draft: InvoiceDraft,
    *,
    invoice_date: date | None,
    operator_restated_amounts: bool,
) -> IvaRateKind | None:
    """Return the domestic rate tier to hand the establishment ladder, or ``None``.

    Resolved here and handed in, rather than left for the classification
    apparatus to re-read: which tier a document charged is the reading stage's
    business, and re-deciding it inside the classifier would be a second
    authority on the same lines. Skipped when the operator restated the amounts,
    for the same reason the per-rate split is -- their figures are the
    authority, not the reader's -- and skipped when no date resolves, because
    the tier is only meaningful against the rates in force on a given day.
    """
    if operator_restated_amounts or invoice_date is None:
        return None
    return domestic_rate_tier_from_the_document(draft, invoice_date=invoice_date)


def _confirmed_lines_from_the_document(
    *,
    draft: InvoiceDraft,
    invoice_number: str,
    taxable_base: Decimal,
    iva_rate: Decimal | None,
    iva_amount: Decimal | None,
    operator_overrode_the_amounts: bool,
) -> tuple[InvoiceLine, ...] | None:
    """Build the confirmed lines from what the document itself declared.

    Returns ``None`` when nothing better than the writer's own base-times-rate
    derivation is available, which is the correct outcome for a text or vision
    reader: those recover printed totals, not a tax breakdown.

    The per-rate breakdown is used whenever the document states one, at ANY
    length. A single entry is not the harmless case it looks like: the
    structured readers populate the breakdown and never the draft's flat
    ``iva_rate``, so a one-rate structured document reached the writer with no
    rate at all and resolved to the base-only EXEMPT slot -- minting a
    zero-cuota invoice out of a document that plainly charged one. Reading the
    breakdown at length one is what recovers that rate; reading it at length two
    or more is additionally what preserves WHICH part of the base carried which
    rate, since Modelo 303 sums cuota devengada per tier.

    Args:
        draft: The re-run extraction being confirmed.
        invoice_number: Resolved invoice number, used to label the lines.
        taxable_base: Resolved taxable base the lines must sum back to.
        iva_rate: Resolved IVA percentage, or ``None``.
        iva_amount: The operator-supplied printed cuota, or ``None``.
        operator_overrode_the_amounts: Whether the operator restated any of the
            base, rate or cuota.

    Returns:
        The lines to hand the writer, or ``None`` to let it derive one line.
    """
    if draft.iva_breakdown and not operator_overrode_the_amounts:
        # Every entry must state both halves of its subtotal. A partial
        # breakdown is not silently completed here: deriving the missing cuota
        # would put this function's arithmetic in place of the document's own
        # figure, which is the opposite of reading the record exactly. The
        # fall-through keeps the pre-existing behaviour, and the printed-total
        # cross-check still reports the shortfall.
        # Pair each entry with its narrowed amounts in one pass, so the guard and
        # the use are the same expression. An `all(...)` check ahead of a
        # comprehension proves the same thing to a reader but not to a checker,
        # which then cannot tell this from a genuine optional dereference.
        priced = [
            (entry, entry.taxable_base, entry.iva_amount)
            for entry in draft.iva_breakdown
            if entry.taxable_base is not None and entry.iva_amount is not None
        ]
        if len(priced) == len(draft.iva_breakdown):
            return tuple(
                InvoiceLine(
                    description=f"{invoice_number or 'Invoice'} - IVA {entry.iva_rate}%",
                    quantity=Decimal("1"),
                    unit_price=taxable_base,
                    subtotal=taxable_base,
                    iva_rate=resolve_iva_rate_slot(entry.iva_rate),
                    iva_amount=iva_amount,
                )
                for entry, taxable_base, iva_amount in priced
            )
    if iva_amount is not None:
        return (
            InvoiceLine(
                description=invoice_number or "Invoice",
                quantity=Decimal("1"),
                unit_price=taxable_base,
                subtotal=taxable_base,
                # The SAME resolver the writer applies to the same value, so an
                # unrepresentable percentage refuses identically whether or not
                # the document printed a cuota.
                iva_rate=resolve_iva_rate_slot(iva_rate),
                iva_amount=iva_amount,
            ),
        )
    return None
