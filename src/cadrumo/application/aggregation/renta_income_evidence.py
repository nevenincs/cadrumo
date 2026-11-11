"""Sales-invoice evidence and retención inference for Renta income rows.

This sibling owns the document-facing facts that enrich an already eligible
income transaction.  The ledger projection remains responsible for deciding
whether a row belongs to a filing period; this module decides whether a linked
issued invoice may supply its fiscal figures and, where it may not, whether a
bounded retención can be inferred from the transaction itself.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from enum import StrEnum
from typing import NamedTuple

from pydantic import BaseModel

from ...core.aggregation import LedgerWithholdingDerivation
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.money.rounding import round_to_cents
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.invoices.decomposition import decompose_invoice
from ...domain.invoices.models import Invoice
from ...domain.invoices.service import INVOICE_MATCH_TOLERANCE
from ...domain.iva.components import category_cuota_is_zero_by_law
from ...domain.iva.schema import InvoiceKind
from ...domain.transactions.dates import transaction_operation_date
from ...domain.transactions.enums import TransactionDirection
from ...domain.transactions.irpf_categories import has_activity_irpf_category
from ...domain.transactions.models import Transaction
from ...domain.transactions.retencion_facts import (
    maximum_supported_activity_retencion_rate,
    retencion_effective_date,
)
from .currency_predicates import (
    effective_eur_amount,
    effective_eur_iva_amount,
    effective_eur_taxable_base,
    is_non_eur_without_conversion,
)


class SalesInvoiceEvidenceRefusal(StrEnum):
    """Why a linked sales invoice was not trusted for a row's fiscal figures.

    NOT an exclusion. Every member here leaves the row IN the aggregation,
    contributing its bank cash under ``CASH_FALLBACK`` grounding, because the
    taxpayer was paid and that income is declarable whatever state its paperwork
    is in. What the refusal withholds is the invoice's FIGURES, not the row.

    This is the income side of an asymmetry worth stating. An unevidenced gasto
    must NOT be claimed, so the expense pipeline excludes it. An unevidenced
    ingreso must STILL be declared, so this one degrades it. Same checks,
    opposite consequence; only the checks transfer.

    Spelled per failure rather than as one generic mismatch: which check
    rejected the link is what an operator needs to repair it, and one reason
    would make five different repairs look like one problem.
    """

    BUCKET_MISMATCH = "sales_invoice_bucket_mismatch"
    UNSUPPORTED_KIND = "unsupported_sales_invoice_kind"
    LINK_NOT_RECIPROCAL = "sales_invoice_link_mismatch"
    PARTIAL_OR_MULTI_TRANSACTION = "partial_or_multi_transaction_sales_invoice"
    AMOUNT_MISMATCH = "sales_invoice_amount_mismatch"
    UNGROUNDED_DECOMPOSITION = "ungrounded_sales_invoice_decomposition"
    NO_EUR_VALUE = "sales_invoice_no_eur_value"


class SalesInvoiceEvidencePayload(BaseModel):
    """The figures a trusted linked sales invoice contributes to one row.

    Empty when the row links no invoice, which is the ordinary case and not a
    defect. A populated payload has passed every guard in
    :func:`sales_invoice_evidence_payload`, so its figures may take precedence
    over the transaction's own tax substrate.
    """

    model_config = STRICT_FROZEN_CONFIG

    taxable_base: Decimal | None = None
    iva_amount: Decimal | None = None
    retencion_amount: Decimal | None = None
    allocated_to_part_payment: bool = False


def invoice_net_cash(invoice: Invoice) -> Decimal:
    """Return what the customer owes the bank account: the total less the retención it remits itself."""
    return invoice.grand_total - (invoice.retention_amount or Decimal("0"))


class SettlementComparison(NamedTuple):
    """Receipts and what their invoice leaves to be paid, stated in one currency."""

    cash: Decimal
    owed: Decimal

    @property
    def settled(self) -> bool:
        """Return whether the cash settles the invoice within the link tolerance."""
        return abs(self.cash - self.owed) <= INVOICE_MATCH_TOLERANCE

    @property
    def reversed(self) -> bool:
        """Return whether the cash hands the whole invoice back within the link tolerance."""
        return abs(self.cash + self.owed) <= INVOICE_MATCH_TOLERANCE


def row_settles_invoice(invoice: Invoice, row: Transaction) -> bool:
    """Return whether the row moved money the way paying ``invoice`` does, rather than returning it."""
    settling = TransactionDirection.INCOMING if invoice.kind is InvoiceKind.ISSUED else TransactionDirection.OUTGOING
    return row.direction is settling


def _in_settling_direction(invoice: Invoice, row: Transaction, magnitude: Decimal) -> Decimal:
    """Return the row's magnitude as it counts towards ``invoice``: a refund takes off what a payment adds."""
    return magnitude if row_settles_invoice(invoice, row) else -magnitude


def settlement_comparison(invoice: Invoice, receipts: Sequence[Transaction]) -> SettlementComparison | None:
    """Put ``receipts`` and ``invoice`` in one currency, or return ``None`` when none can be justified.

    Figures stated in the invoice's own currency compare as stated, because no rate
    stands between them. Any other receipt compares in EUR: the movement's own
    ``value_in_eur`` against the invoice's total at the rate stamped on it. A side with
    no EUR value leaves nothing to compare, and the raw figures never stand in for it.
    """
    if all(receipt.raw.currency == invoice.currency for receipt in receipts):
        return SettlementComparison(
            cash=sum((_in_settling_direction(invoice, row, row.raw.amount) for row in receipts), Decimal("0")),
            owed=invoice_net_cash(invoice),
        )
    total_eur = invoice.grand_total_eur
    if total_eur is None or any(is_non_eur_without_conversion(receipt) for receipt in receipts):
        return None
    return SettlementComparison(
        cash=sum((_in_settling_direction(invoice, row, effective_eur_amount(row)) for row in receipts), Decimal("0")),
        owed=total_eur - (invoice.retention_amount_eur or Decimal("0")),
    )


def taxable_base_comparison(invoice: Invoice, rows: Sequence[Transaction]) -> SettlementComparison | None:
    """Put the bases ``rows`` state and the base of ``invoice`` in one currency, by the settlement rule.

    Bases stated in the invoice's own currency compare as stated. Any other row compares
    in EUR, and a side with no EUR value leaves nothing to compare.
    """
    if all(row.raw.currency == invoice.currency for row in rows):
        return SettlementComparison(
            cash=sum(
                (_in_settling_direction(invoice, row, row.taxable_base or Decimal("0")) for row in rows), Decimal("0")
            ),
            owed=invoice.base_total,
        )
    base_eur = invoice.base_total_eur
    if base_eur is None or any(is_non_eur_without_conversion(row) for row in rows):
        return None
    return SettlementComparison(
        cash=round_to_cents(
            sum(
                (_in_settling_direction(invoice, row, effective_eur_taxable_base(row) or Decimal("0")) for row in rows),
                Decimal("0"),
            )
        ),
        owed=base_eur,
    )


def part_payment_share(invoice: Invoice, transaction: Transaction) -> Decimal | None:
    """Return the share of ``invoice`` this receipt settles, or ``None`` when it is no part payment.

    The share is cash over what the invoice leaves to be paid, base + IVA - retención,
    read through :func:`settlement_comparison`, and it applies to the invoice's EUR
    figures. A receipt settling the whole invoice alone, or exceeding it, is no part
    payment, nor is a refund, and an invoice with no EUR value, a receipt that cannot be
    compared or ungrounded figures cannot be shared out.
    """
    comparison = settlement_comparison(invoice, (transaction,))
    if (
        not row_settles_invoice(invoice, transaction)
        or invoice.grand_total_eur is None
        or comparison is None
        or transaction.transaction_id not in invoice.linked_transaction_ids
        or comparison.owed <= Decimal("0")
        or comparison.cash > comparison.owed
        or (comparison.settled and len(invoice.linked_transaction_ids) == 1)
        or not decompose_invoice(invoice).is_grounded
    ):
        return None
    return comparison.cash / comparison.owed


def receipt_overpays_invoice(invoice: Invoice, transaction: Transaction) -> bool:
    """Return whether this one receipt exceeds what the invoice leaves to be paid, past the link tolerance."""
    comparison = settlement_comparison(invoice, (transaction,))
    return comparison is not None and comparison.cash - comparison.owed > INVOICE_MATCH_TOLERANCE


def invoice_settled_in_parts(invoice: Invoice, receipts: Sequence[Transaction]) -> bool:
    """Return whether every receipt the invoice links, all of them payments, together settle it."""
    comparison = settlement_comparison(invoice, receipts)
    return (
        comparison is not None
        and comparison.settled
        and 1 < len(invoice.linked_transaction_ids) == len(receipts)
        and all(part_payment_share(invoice, receipt) is not None for receipt in receipts)
    )


def _settled_part_of(
    invoice: Invoice, transaction: Transaction, receipts: Sequence[Transaction], amount: Decimal
) -> Decimal:
    """Return the cents of ``amount`` this receipt carries when its receipts settle the invoice.

    Cut by cumulative rounding in payment order, so the parts add up to ``amount`` exactly.
    """
    ordered = sorted(receipts, key=lambda row: (row.raw.value_date or row.raw.booked_date, row.transaction_id))
    paid_before = Decimal("0")
    for position, receipt in enumerate(ordered, start=1):
        paid_after = paid_before + (part_payment_share(invoice, receipt) or Decimal("0"))
        reached = Decimal("1") if position == len(ordered) else min(paid_after, Decimal("1"))
        if receipt.transaction_id == transaction.transaction_id:
            return round_to_cents(amount * reached) - round_to_cents(amount * paid_before)
        paid_before = reached
    return Decimal("0")


def sales_invoice_evidence_payload(
    *,
    invoices: InvoiceCatalogue,
    bucket_id: str,
    transaction: Transaction,
    receipts_by_invoice: Mapping[str, Sequence[Transaction]] | None = None,
) -> tuple[SalesInvoiceEvidencePayload, SalesInvoiceEvidenceRefusal | None]:
    """Return the figures a linked sales invoice contributes, or why it is refused.

    Derive-on-read: nothing is copied onto the transaction at link time, so a
    corrected invoice is reflected on the next aggregation and no stale figure
    can outlive it.

    A sales invoice subject to retención is paid NET -- the payer withholds and
    remits the retención on the taxpayer's account -- so the bank credit is
    ``grand_total - retention_amount``. Asserting equality against ``grand_total``
    here would refuse precisely the net-paid professional invoices this evidence
    path exists to ground; asserting it against the cash without the retención
    term would accept an invoice that does not describe the payment.

    The cash and the invoice are compared through :func:`settlement_comparison`, and
    the figures returned are always EUR, whatever currency the invoice is stated in.

    ``receipts_by_invoice`` holds each invoice's active linked rows; without it a part
    payment is not shared out. Receipts that together settle the invoice carry what it
    states, retencion included. Short of that, each carries a pro rata share.

    Core types:
    :class:`~cadrumo.domain.invoices.catalogue.InvoiceCatalogue`.
    """
    invoice_id = transaction.invoice_id
    invoice = None if invoice_id is None else invoices.get(invoice_id)
    if invoice is None:
        return SalesInvoiceEvidencePayload(), None
    refusal = _linkage_refusal(invoice, transaction, bucket_id=bucket_id)
    if refusal is not None:
        return SalesInvoiceEvidencePayload(), refusal
    return _linked_invoice_payload(invoice, transaction, receipts_by_invoice=receipts_by_invoice)


def _part_payment_payload(
    invoice: Invoice,
    transaction: Transaction,
    receipts: Sequence[Transaction] | None,
    *,
    share: Decimal,
    base_eur: Decimal,
    iva_eur: Decimal,
) -> SalesInvoiceEvidencePayload:
    """Return the receipt's part of the invoice: exact when the receipts settle it in parts, else by share."""
    if receipts is not None and invoice_settled_in_parts(invoice, receipts):
        return SalesInvoiceEvidencePayload(
            taxable_base=_settled_part_of(invoice, transaction, receipts, base_eur),
            iva_amount=_settled_part_of(invoice, transaction, receipts, iva_eur),
            retencion_amount=_settled_part_of(
                invoice, transaction, receipts, invoice.retention_amount_eur or Decimal("0")
            ),
        )
    return SalesInvoiceEvidencePayload(
        taxable_base=round_to_cents(base_eur * share),
        iva_amount=round_to_cents(iva_eur * share),
        retencion_amount=round_to_cents((invoice.retention_amount_eur or Decimal("0")) * share),
        allocated_to_part_payment=True,
    )


def _linked_invoice_payload(
    invoice: Invoice, transaction: Transaction, *, receipts_by_invoice: Mapping[str, Sequence[Transaction]] | None
) -> tuple[SalesInvoiceEvidencePayload, SalesInvoiceEvidenceRefusal | None]:
    """Return the figures of an invoice already linked back to the row: its part-payment share, else the whole."""
    base_eur = invoice.base_total_eur
    iva_eur = invoice.iva_total_eur
    receipts = None if receipts_by_invoice is None else receipts_by_invoice.get(invoice.invoice_id, ())
    share = None if receipts is None else part_payment_share(invoice, transaction)
    if share is not None and base_eur is not None and iva_eur is not None:
        return (
            _part_payment_payload(invoice, transaction, receipts, share=share, base_eur=base_eur, iva_eur=iva_eur),
            None,
        )
    refusal = _whole_invoice_refusal(invoice, transaction)
    if refusal is not None:
        return SalesInvoiceEvidencePayload(), refusal
    if base_eur is None or iva_eur is None:
        return SalesInvoiceEvidencePayload(), SalesInvoiceEvidenceRefusal.NO_EUR_VALUE
    return (
        SalesInvoiceEvidencePayload(
            taxable_base=base_eur,
            iva_amount=iva_eur,
            retencion_amount=invoice.retention_amount_eur,
        ),
        None,
    )


def _linkage_refusal(
    invoice: Invoice, transaction: Transaction, *, bucket_id: str
) -> SalesInvoiceEvidenceRefusal | None:
    """Return the first reason the invoice is not this bucket's issued invoice linked back to the row."""
    transaction_id = transaction.transaction_id
    if invoice.bucket_id != bucket_id:
        return SalesInvoiceEvidenceRefusal.BUCKET_MISMATCH
    if invoice.kind is not InvoiceKind.ISSUED:
        return SalesInvoiceEvidenceRefusal.UNSUPPORTED_KIND
    if transaction_id not in invoice.linked_transaction_ids:
        return SalesInvoiceEvidenceRefusal.LINK_NOT_RECIPROCAL
    return None


def _whole_invoice_refusal(invoice: Invoice, transaction: Transaction) -> SalesInvoiceEvidenceRefusal | None:
    """Return the first reason a single receipt cannot stand for the whole invoice."""
    if len(invoice.linked_transaction_ids) != 1:
        return SalesInvoiceEvidenceRefusal.PARTIAL_OR_MULTI_TRANSACTION
    comparison = settlement_comparison(invoice, (transaction,))
    if comparison is None:
        return SalesInvoiceEvidenceRefusal.NO_EUR_VALUE
    if not comparison.settled:
        return SalesInvoiceEvidenceRefusal.AMOUNT_MISMATCH
    # Asked before the decomposition, which also fails an unrated invoice: the repair
    # here is stamping a rate, and that reason is the one that says so.
    if invoice.base_total_eur is None or invoice.iva_total_eur is None:
        return SalesInvoiceEvidenceRefusal.NO_EUR_VALUE
    # Linkage is established by this point; coherence is a separate question and
    # the guards above cannot answer it. Delegated rather than re-derived: the
    # decomposition contract is the single authority on whether an invoice's own
    # figures are legally interpretable. This path reads the IRPF figures alone,
    # so an undeclared IVA treatment, which stays an IVA defect, does not refuse.
    if not decompose_invoice(invoice).irpf_figures_grounded:
        return SalesInvoiceEvidenceRefusal.UNGROUNDED_DECOMPOSITION
    return None


class _WithheldInference(NamedTuple):
    """One row's derived retención and the route that produced it."""

    amount: Decimal
    derivation: LedgerWithholdingDerivation


def _determinable_cuota(transaction: Transaction) -> Decimal | None:
    """Return the row's IVA cuota in EUR when it can be known, else ``None``.

    A recorded ``iva_amount`` is the cuota. Failing that, the declared IVA
    category can still determine it: for a category whose cuota is zero by law
    the absent field is not missing data, it is the operation having no cuota
    to record. Reading the Axis-A table rather than testing for nullness is
    what separates those two -- ``iva_amount is None`` alone cannot say whether
    an exempt supply was declared or nothing was tagged at all.

    The table is keyed on the category AND the invoice kind, because the same
    category resolves differently on each side. These are actividad-económica
    receipts, so the taxpayer is always the issuer by construction.
    """
    if transaction.iva_amount is not None:
        return effective_eur_iva_amount(transaction)
    category = transaction.iva_category
    if category is not None and category_cuota_is_zero_by_law(
        category,
        InvoiceKind.ISSUED,
        effective_date=transaction_operation_date(transaction),
    ):
        return Decimal("0")
    return None


def income_withheld_amount(
    transaction: Transaction,
    *,
    evidence: SalesInvoiceEvidencePayload | None = None,
) -> _WithheldInference:
    """Derive the retención practicada on one income row.

    Bounded inference only: the figure is the declared invoice gross minus the
    cash actually received. The base is never reconstructed from the cash by
    assuming a rate -- selecting the applicable rate (15 %, 7 %, a sectoral or
    convenio figure) is a per-row legal fact this application cannot determine,
    and inventing it would manufacture legal behaviour rather than read it.

    The result is capped by the registry maximum supported rate. That bound
    exists on the transaction gross invariant too, but only for rows carrying
    both a base and a cuota; zero-cuota rows admitted here never meet it, so the
    inference applies the bound uniformly.

    Every figure is the row's EUR value, so a converted foreign receipt infers EUR and
    an unconverted one infers nothing. The shortfall is rounded to cents because a
    converted ``value_in_eur`` is rounded while the converted base and cuota are not,
    and that gap is no retención.
    """
    if not has_activity_irpf_category(transaction.irpf_category, direction=transaction.direction):
        return _WithheldInference(Decimal("0"), LedgerWithholdingDerivation.NOT_APPLICABLE)
    stated = _stated_withholding(evidence)
    if stated is not None:
        return stated
    return _inferred_withholding(transaction)


def _stated_withholding(evidence: SalesInvoiceEvidencePayload | None) -> _WithheldInference | None:
    """Return the retención a linked invoice states, or ``None`` when it states none."""
    if evidence is not None and evidence.allocated_to_part_payment and evidence.retencion_amount not in (None, 0):
        return _WithheldInference(evidence.retencion_amount, LedgerWithholdingDerivation.ALLOCATED_ON_PART_PAYMENT)
    # Declared-first: a retención the linked invoice states is the document's
    # figure; the inference below reconstructs one from what reached the bank.
    if evidence is not None and evidence.retencion_amount is not None and evidence.retencion_amount > Decimal("0"):
        return _WithheldInference(
            evidence.retencion_amount,
            LedgerWithholdingDerivation.DECLARED_ON_LINKED_INVOICE,
        )
    return None


def _inferred_withholding(transaction: Transaction) -> _WithheldInference:
    """Reconstruct the retención from the invoice gross less the cash that reached the bank."""
    if is_non_eur_without_conversion(transaction):
        return _WithheldInference(Decimal("0"), LedgerWithholdingDerivation.NO_SUBSTRATE)
    base = effective_eur_taxable_base(transaction)
    if base is None:
        return _WithheldInference(Decimal("0"), LedgerWithholdingDerivation.NO_SUBSTRATE)
    cuota = _determinable_cuota(transaction)
    if cuota is None:
        return _WithheldInference(Decimal("0"), LedgerWithholdingDerivation.NO_SUBSTRATE)
    derivation = (
        LedgerWithholdingDerivation.INFERRED_FROM_DECLARED_CUOTA
        if transaction.iva_amount is not None
        else LedgerWithholdingDerivation.INFERRED_FROM_CATEGORY_ZERO_CUOTA
    )
    inferred = round_to_cents(base + cuota - abs(effective_eur_amount(transaction)))
    if inferred <= Decimal("0"):
        return _WithheldInference(Decimal("0"), LedgerWithholdingDerivation.NONE_WITHHELD)
    maximum_supported = round_to_cents(
        base
        * maximum_supported_activity_retencion_rate(
            effective_date=retencion_effective_date(
                value_date=transaction.raw.value_date,
                booked_date=transaction.raw.booked_date,
            ),
        )
    )
    if inferred > maximum_supported:
        return _WithheldInference(Decimal("0"), LedgerWithholdingDerivation.REFUSED_ABOVE_SUPPORTED_RATE)
    return _WithheldInference(inferred, derivation)
