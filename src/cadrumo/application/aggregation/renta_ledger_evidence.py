"""Renta ledger invoice evidence validation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.invoices.models import Invoice
from ...domain.iva.schema import InvoiceKind
from ...domain.transactions.models import Transaction
from ..invoices.source_observations import is_rectificativa
from ._renta_business_eligibility import is_supplier_refund
from .currency_predicates import (
    effective_eur_iva_amount,
    effective_eur_taxable_base,
)
from .renta_imputation import received_invoice_reference
from .renta_income_evidence import settlement_comparison
from .renta_ledger_models import RentaLedgerAggregationIssue, RentaLedgerAggregationIssueReason


class _PurchaseInvoiceEvidencePayload(BaseModel):
    """Typed enrichment fields copied from a reconciled linked invoice."""

    model_config = _STRICT_FROZEN

    invoice_issue_date: date | None = None
    taxable_base: Decimal | None = None
    iva_amount: Decimal | None = None


def refund_left_to_correction_netting(transaction: Transaction, invoices: InvoiceCatalogue) -> bool:
    """Return whether the row is a supplier's refund on a correction, which the correction netting answers for.

    ``invoices`` is the :class:`InvoiceCatalogue`, the profile's invoice catalogue.
    """
    invoice_id = received_invoice_reference(transaction)
    if not is_supplier_refund(transaction) or invoice_id is None:
        return False
    invoice = invoices.get(invoice_id)
    return invoice is not None and is_rectificativa(invoice)


def purchase_invoice_evidence_payload(
    *,
    invoices: InvoiceCatalogue,
    bucket_id: str,
    transaction: Transaction,
) -> _PurchaseInvoiceEvidencePayload | RentaLedgerAggregationIssue:
    """Validate a linked purchase invoice and extract its EUR totals.

    Takes ``invoices`` as a :class:`InvoiceCatalogue`.
    """
    transaction_id = transaction.transaction_id
    purchase_invoice_evidence_id = received_invoice_reference(transaction)
    category_id = transaction.category_id
    if purchase_invoice_evidence_id is None:
        return _PurchaseInvoiceEvidencePayload()
    invoice = invoices.get(purchase_invoice_evidence_id)
    if invoice is None:
        return _missing_purchase_invoice_issue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
        )
    reference_issue = _purchase_invoice_reference_issue(
        invoice,
        bucket_id=bucket_id,
        transaction_id=transaction_id,
        purchase_invoice_evidence_id=purchase_invoice_evidence_id,
        category_id=category_id,
    )
    if reference_issue is not None:
        return reference_issue
    return _purchase_invoice_payload_for_totals(
        invoice,
        transaction=transaction,
        purchase_invoice_evidence_id=purchase_invoice_evidence_id,
    )


def _missing_purchase_invoice_issue(
    *,
    transaction_id: str,
    purchase_invoice_evidence_id: str,
    category_id: str | None,
) -> RentaLedgerAggregationIssue:
    """Describe an evidence reference absent from the confirmed invoice catalogue."""
    # The evidence reference addresses two id spaces and only the invoice
    # catalogue carries the fiscal totals this fold-in needs, so a miss here is
    # NOT proof the reference is broken: it is also what a legitimately
    # registered, not-yet-confirmed evidence record looks like from this side.
    # Naming both cases keeps the operator from hunting a phantom missing record.
    return RentaLedgerAggregationIssue(
        transaction_id=transaction_id,
        purchase_invoice_evidence_id=purchase_invoice_evidence_id,
        category_id=category_id,
        reason=RentaLedgerAggregationIssueReason.MISSING_PURCHASE_INVOICE_EVIDENCE,
        detail=(
            "transaction references no confirmed invoice in the catalogue, so this expense carries no "
            "invoice totals to fold in; if the reference names a registered evidence record, confirming "
            "it into an invoice does NOT repoint this transaction, and no verb currently replaces an "
            "already-set purchase-invoice-evidence reference -- so record the expense against the "
            "confirmed invoice on a transaction that has no evidence reference yet"
        ),
    )


def _purchase_invoice_reference_issue(
    invoice: Invoice,
    *,
    bucket_id: str,
    transaction_id: str,
    purchase_invoice_evidence_id: str,
    category_id: str | None,
) -> RentaLedgerAggregationIssue | None:
    """Validate bucket, kind, and reciprocal-link constraints for one invoice."""
    if invoice.bucket_id != bucket_id:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.PURCHASE_INVOICE_EVIDENCE_BUCKET_MISMATCH,
            detail="transaction references purchase invoice evidence outside the active bucket",
        )
    if invoice.kind is not InvoiceKind.RECEIVED:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.UNSUPPORTED_PURCHASE_INVOICE_EVIDENCE_KIND,
            detail=f"purchase invoice evidence kind {invoice.kind.value!r} is not RECEIVED",
        )
    if transaction_id not in invoice.linked_transaction_ids:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.PURCHASE_INVOICE_EVIDENCE_LINK_MISMATCH,
            detail="transaction and purchase invoice evidence links are not reciprocal",
        )
    if len(invoice.linked_transaction_ids) != 1:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.PARTIAL_OR_MULTI_TRANSACTION_PURCHASE_INVOICE_EVIDENCE,
            detail="first-slice aggregation only accepts one transaction per purchase invoice evidence record",
        )
    return None


def _purchase_invoice_payload_for_totals(
    invoice: Invoice,
    *,
    transaction: Transaction,
    purchase_invoice_evidence_id: str,
) -> _PurchaseInvoiceEvidencePayload | RentaLedgerAggregationIssue:
    """Reconcile the payment with the invoice and project the invoice's EUR totals.

    The comparison is the one every linked invoice reads, tolerance included: what the
    invoice leaves to be paid, against the movement in the one currency that needs no
    rate or else in EUR. An invoice with no EUR value has no figure to fold in, so it is
    refused however its own-currency figures compare.
    """
    comparison = settlement_comparison(invoice, (transaction,))
    base_total_eur = invoice.base_total_eur
    iva_total_eur = invoice.iva_total_eur
    if comparison is None or base_total_eur is None or iva_total_eur is None:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction.transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=transaction.category_id,
            reason=RentaLedgerAggregationIssueReason.AMOUNT_MISMATCH,
            detail="linked invoice or transaction has no EUR value to compare or fold in",
        )
    # A refund on a correction has no reading of its own here: the correction netting owns it.
    if not comparison.settled and (is_rectificativa(invoice) or not comparison.reversed):
        return RentaLedgerAggregationIssue(
            transaction_id=transaction.transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=transaction.category_id,
            reason=RentaLedgerAggregationIssueReason.AMOUNT_MISMATCH,
            detail="linked transaction amount does not match invoice grand total",
        )
    return _PurchaseInvoiceEvidencePayload(
        invoice_issue_date=invoice.issued_at,
        taxable_base=base_total_eur,
        iva_amount=iva_total_eur,
    )


def taxable_base_for(transaction: Transaction, evidence_payload: _PurchaseInvoiceEvidencePayload) -> Decimal | None:
    """Return the EUR taxable_base: the linked invoice's (already EUR), else the transaction's own.

    ``transaction.taxable_base`` is native-currency (see
    ``domain.transactions.tests.test_gross_invariant``), so the fallback goes
    through the EUR-equivalent accessor rather than the raw field.
    """
    if evidence_payload.taxable_base is not None:
        return evidence_payload.taxable_base
    return effective_eur_taxable_base(transaction)


def iva_amount_for(transaction: Transaction, evidence_payload: _PurchaseInvoiceEvidencePayload) -> Decimal | None:
    """Return the EUR iva_amount: the linked invoice's (already EUR), else the transaction's own.

    Via the EUR-equivalent accessor -- see :func:`taxable_base_for`.
    """
    if evidence_payload.iva_amount is not None:
        return evidence_payload.iva_amount
    return effective_eur_iva_amount(transaction)
