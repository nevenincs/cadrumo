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
from .currency_predicates import (
    effective_eur_iva_amount,
    effective_eur_taxable_base,
)
from .renta_ledger_models import RentaLedgerAggregationIssue, RentaLedgerAggregationIssueReason


class _PurchaseInvoiceEvidencePayload(BaseModel):
    """Typed enrichment fields copied from a reconciled linked invoice."""

    model_config = _STRICT_FROZEN

    invoice_issue_date: date | None = None
    taxable_base: Decimal | None = None
    iva_amount: Decimal | None = None


def purchase_invoice_evidence_payload(
    *,
    invoices: InvoiceCatalogue,
    bucket_id: str,
    transaction_id: str,
    purchase_invoice_evidence_id: str | None,
    category_id: str | None,
    transaction_amount: Decimal,
) -> _PurchaseInvoiceEvidencePayload | RentaLedgerAggregationIssue:
    """Validate a linked purchase invoice and extract its EUR totals.

    Takes ``invoices`` as a :class:`InvoiceCatalogue`.
    """
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
        transaction_id=transaction_id,
        purchase_invoice_evidence_id=purchase_invoice_evidence_id,
        category_id=category_id,
        transaction_amount=transaction_amount,
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
    transaction_id: str,
    purchase_invoice_evidence_id: str,
    category_id: str | None,
    transaction_amount: Decimal,
) -> _PurchaseInvoiceEvidencePayload | RentaLedgerAggregationIssue:
    """Reconcile EUR totals and project the linked invoice's evidence payload."""
    # invoice.grand_total is denominated in invoice.currency (native), while
    # transaction_amount is the caller's already-EUR-converted eur_amount (see
    # effective_eur_amount). Comparing them directly mixes currencies: a
    # legitimate foreign-currency invoice would compare its native total
    # against a converted EUR figure and mismatch even when the two documents
    # agree, so this compares grand_total_eur instead. An invoice that cannot
    # itself resolve a EUR total (foreign currency, unconverted) has no EUR
    # figure to compare or fold in, so it is refused the same way rather than
    # silently treated as a domestic-currency match.
    invoice_grand_total_eur = invoice.grand_total_eur
    if invoice_grand_total_eur is None or transaction_amount != invoice_grand_total_eur:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.AMOUNT_MISMATCH,
            detail="linked transaction amount does not match invoice grand total",
        )
    # invoice.base_total / invoice.iva_total are native-currency (same
    # currency as invoice.currency); the EUR-safe *_eur properties are the
    # ones that already exist for exactly this purpose (used correctly in
    # invoice_retencion.py). base_total_eur cannot be None here: the
    # grand_total_eur check above already proved the invoice resolves to EUR.
    base_total_eur = invoice.base_total_eur
    iva_total_eur = invoice.iva_total_eur
    if base_total_eur is None or iva_total_eur is None:
        msg = (
            f"purchase invoice {purchase_invoice_evidence_id} resolves a EUR grand total but no EUR "
            "base or cuota; its EUR-equivalent totals disagree with one another"
        )
        raise ValueError(msg)
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
