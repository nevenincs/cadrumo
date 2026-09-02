"""Sales-invoice evidence and retención inference for Renta income rows.

This sibling owns the document-facing facts that enrich an already eligible
income transaction.  The ledger projection remains responsible for deciding
whether a row belongs to a filing period; this module decides whether a linked
issued invoice may supply its fiscal figures and, where it may not, whether a
bounded retención can be inferred from the transaction itself.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import NamedTuple

from pydantic import BaseModel

from ...core.aggregation import LedgerWithholdingDerivation
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.money.rounding import round_to_cents
from ...domain.invoices.decomposition import decompose_invoice
from ...domain.invoices.models import InvoiceCatalogue
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.components import category_cuota_is_zero_by_law
from ...domain.transactions.irpf_categories import has_activity_irpf_category
from ...domain.transactions.models import Transaction
from ...domain.transactions.retencion_parameters import maximum_supported_activity_retencion_rate


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


class _SalesInvoiceEvidencePayload(BaseModel):
    """The figures a trusted linked sales invoice contributes to one row.

    Empty when the row links no invoice, which is the ordinary case and not a
    defect. A populated payload has passed every guard in
    :func:`sales_invoice_evidence_payload`, so its figures may take precedence
    over the transaction's own tax substrate.
    """

    model_config = _STRICT_FROZEN

    taxable_base: Decimal | None = None
    iva_amount: Decimal | None = None
    retencion_amount: Decimal | None = None


def sales_invoice_evidence_payload(
    *,
    invoices: InvoiceCatalogue,
    bucket_id: str,
    transaction: Transaction,
) -> tuple[_SalesInvoiceEvidencePayload, SalesInvoiceEvidenceRefusal | None]:
    """Return the figures a linked sales invoice contributes, or why it is refused.

    Derive-on-read: nothing is copied onto the transaction at link time, so a
    corrected invoice is reflected on the next aggregation and no stale figure
    can outlive it.

    One guard differs from the expense side, and the difference is the point. An
    expense pays the whole contraprestación, so that side asserts the cash
    equals ``grand_total``. A sales invoice subject to retención is paid NET --
    the payer withholds and remits the retención on the taxpayer's account -- so
    the bank credit is ``grand_total - retention_amount``. Asserting equality
    against ``grand_total`` here would refuse precisely the net-paid
    professional invoices this evidence path exists to ground; asserting it
    against the cash without the retención term would accept an invoice that
    does not describe the payment.
    """
    invoice_id = transaction.invoice_id
    if invoice_id is None:
        return _SalesInvoiceEvidencePayload(), None
    invoice = invoices.get(invoice_id)
    if invoice is None:
        return _SalesInvoiceEvidencePayload(), None
    transaction_id = transaction.transaction_id
    if invoice.bucket_id != bucket_id:
        return _SalesInvoiceEvidencePayload(), SalesInvoiceEvidenceRefusal.BUCKET_MISMATCH
    if invoice.kind is not InvoiceKind.ISSUED:
        return _SalesInvoiceEvidencePayload(), SalesInvoiceEvidenceRefusal.UNSUPPORTED_KIND
    if transaction_id not in invoice.linked_transaction_ids:
        return _SalesInvoiceEvidencePayload(), SalesInvoiceEvidenceRefusal.LINK_NOT_RECIPROCAL
    if len(invoice.linked_transaction_ids) != 1:
        return _SalesInvoiceEvidencePayload(), SalesInvoiceEvidenceRefusal.PARTIAL_OR_MULTI_TRANSACTION
    expected_cash = invoice.grand_total - (invoice.retention_amount or Decimal("0"))
    if abs(transaction.raw.amount) != expected_cash:
        return _SalesInvoiceEvidencePayload(), SalesInvoiceEvidenceRefusal.AMOUNT_MISMATCH
    # Linkage is established by this point; coherence is a separate question and
    # the guards above cannot answer it. Delegated rather than re-derived: the
    # decomposition contract is the single authority on whether an invoice's own
    # figures are legally interpretable, and consulting it here is what makes a
    # correctly-linked but untagged invoice visible instead of silently grounded.
    if not decompose_invoice(invoice).is_grounded:
        return _SalesInvoiceEvidencePayload(), SalesInvoiceEvidenceRefusal.UNGROUNDED_DECOMPOSITION
    return (
        _SalesInvoiceEvidencePayload(
            taxable_base=invoice.base_total,
            iva_amount=invoice.iva_total,
            retencion_amount=invoice.retention_amount,
        ),
        None,
    )


class _WithheldInference(NamedTuple):
    """One row's derived retención and the route that produced it."""

    amount: Decimal
    derivation: LedgerWithholdingDerivation


def _determinable_cuota(transaction: Transaction) -> Decimal | None:
    """Return the row's IVA cuota when it can be known, else ``None``.

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
        return transaction.iva_amount
    category = transaction.iva_category
    if category is not None and category_cuota_is_zero_by_law(category, InvoiceKind.ISSUED):
        return Decimal("0")
    return None


def income_withheld_amount(
    transaction: Transaction,
    *,
    evidence: _SalesInvoiceEvidencePayload | None = None,
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
    """
    if not has_activity_irpf_category(transaction.irpf_category, direction=transaction.direction):
        return _WithheldInference(Decimal("0"), LedgerWithholdingDerivation.NOT_APPLICABLE)
    # Declared-first: a retención the linked invoice states is the document's
    # figure; the inference below reconstructs one from what reached the bank.
    if evidence is not None and evidence.retencion_amount is not None and evidence.retencion_amount > Decimal("0"):
        return _WithheldInference(
            evidence.retencion_amount,
            LedgerWithholdingDerivation.DECLARED_ON_LINKED_INVOICE,
        )
    if transaction.taxable_base is None:
        return _WithheldInference(Decimal("0"), LedgerWithholdingDerivation.NO_SUBSTRATE)
    cuota = _determinable_cuota(transaction)
    if cuota is None:
        return _WithheldInference(Decimal("0"), LedgerWithholdingDerivation.NO_SUBSTRATE)
    derivation = (
        LedgerWithholdingDerivation.INFERRED_FROM_DECLARED_CUOTA
        if transaction.iva_amount is not None
        else LedgerWithholdingDerivation.INFERRED_FROM_CATEGORY_ZERO_CUOTA
    )
    invoice_gross = transaction.taxable_base + cuota
    cash_received = abs(transaction.raw.amount)
    if invoice_gross <= cash_received:
        return _WithheldInference(Decimal("0"), LedgerWithholdingDerivation.NONE_WITHHELD)
    inferred = invoice_gross - cash_received
    maximum_supported = round_to_cents(transaction.taxable_base * maximum_supported_activity_retencion_rate())
    if round_to_cents(inferred) > maximum_supported:
        return _WithheldInference(Decimal("0"), LedgerWithholdingDerivation.REFUSED_ABOVE_SUPPORTED_RATE)
    return _WithheldInference(inferred, derivation)
