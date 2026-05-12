"""Application projections for invoice review and matching surfaces."""

from __future__ import annotations

import contextlib
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict

from ...domain.invoices import Invoice, InvoiceCatalogue
from ...domain.transactions import TransactionCatalogue
from ..review import InvoiceReviewFilterSpec, InvoiceReviewRecord, update_invoice_review
from ..workflow import WorkflowState


class InvoiceReviewProjection(BaseModel):
    """Rendered invoice row computed by backend review services."""

    model_config = ConfigDict(frozen=True)

    id: str
    kind: str
    issued_at: str | None = None
    base: str
    iva: str
    status: str
    payment: str | None = None
    payment_id: str | None = None
    review: InvoiceReviewRecord | None = None


class InvoiceMatchProjection(BaseModel):
    """Backend-owned invoice/payment matching projection."""

    model_config = ConfigDict(frozen=True)

    period: str
    matched: tuple[dict[str, str], ...]
    unmatched: tuple[dict[str, str], ...]


def _coerce_invoice_review(raw: object) -> InvoiceReviewRecord | None:
    """Coerce a raw value from WorkflowState.invoice_reviews to InvoiceReviewRecord.

    WorkflowState.invoice_reviews is typed `dict[str, Any]` to accept
    both already-validated InvoiceReviewRecord instances and raw dicts
    that need re-validation (e.g. after JSON deserialisation). This
    helper dispatches on the runtime shape and raises explicitly on
    anything else so the unsupported value does not silently slip
    through the projection pipeline.
    """
    if raw is None:
        return None
    if isinstance(raw, InvoiceReviewRecord):
        return raw
    if isinstance(raw, dict):
        return InvoiceReviewRecord.model_validate(raw)
    raise TypeError(
        f"WorkflowState.invoice_reviews value must be InvoiceReviewRecord or dict; got {type(raw).__name__}"
    )


def project_invoice_reviews(
    catalogue: InvoiceCatalogue,
    state: WorkflowState,
    *,
    spec: InvoiceReviewFilterSpec,
    invoice_id: str | None = None,
) -> tuple[InvoiceReviewProjection, ...]:
    """Return backend-computed review rows for invoices matching ``spec``."""

    rows: list[InvoiceReviewProjection] = []
    for invoice in catalogue.values():
        review = _coerce_invoice_review(state.invoice_reviews.get(invoice.invoice_id))
        status = invoice_review_status(invoice, review)
        if spec.kind is not None and invoice.kind is not spec.kind:
            continue
        if spec.status is not None and status != spec.status.value:
            continue
        if invoice_id is not None and invoice.invoice_id != invoice_id:
            continue
        rows.append(project_invoice_review(invoice, review))
    return tuple(rows)


def project_invoice_review(invoice: Invoice, review: InvoiceReviewRecord | None) -> InvoiceReviewProjection:
    """Return a backend-owned display projection for one invoice."""

    base, iva = invoice_display_amounts(invoice, review)
    payment = review.fields.get("payment.id") if review else None
    return InvoiceReviewProjection(
        id=invoice.invoice_id,
        kind=invoice.kind.value,
        issued_at=invoice.issued_at.isoformat() if invoice.issued_at else None,
        base=_format_decimal(base),
        iva=_format_decimal(iva),
        status=invoice_review_status(invoice, review),
        payment=payment,
        payment_id=payment,
        review=review,
    )


def invoice_display_amounts(
    invoice: Invoice, review: InvoiceReviewRecord | None
) -> tuple[Decimal | None, Decimal | None]:
    """Compute review-adjusted base and IVA display totals."""

    base = invoice.base_total
    iva = invoice.iva_total
    rate_decimal = None
    if review is None:
        return base, iva

    if "base" in review.fields:
        base = Decimal(review.fields["base"])
    if "iva.rate" in review.fields:
        rate_raw = review.fields["iva.rate"]
        if rate_raw.startswith("RATE_"):
            rate_decimal = Decimal(rate_raw[5:]) / Decimal("100")
        else:
            with contextlib.suppress(InvalidOperation):
                rate_decimal = Decimal(rate_raw) / Decimal("100")
    if "iva.amount" in review.fields:
        iva = Decimal(review.fields["iva.amount"])
    elif rate_decimal is not None and base is not None:
        iva = (base * rate_decimal).quantize(Decimal("0.01"))
    return base, iva


def invoice_review_status(invoice: Invoice, review: InvoiceReviewRecord | None) -> str:
    """Return the backend-owned invoice review status."""

    del invoice
    if review and review.fields.get("payment.id"):
        return "paid"
    if review and review.fields:
        return "reviewed"
    return "pending"


def apply_manual_invoice_match(state: WorkflowState, invoice_id: str, ledger_id: str) -> WorkflowState:
    """Return ``state`` with a manual invoice/payment match recorded."""

    return update_invoice_review(
        state,
        invoice_id,
        fields={"payment.id": ledger_id},
        action="match",
        reason="manual match",
    )


def project_invoice_payment_matches(
    *,
    period: str,
    catalogue: InvoiceCatalogue,
    transactions: TransactionCatalogue,
    state: WorkflowState,
) -> InvoiceMatchProjection:
    """Return period-labelled invoice/payment match status."""

    matched: list[dict[str, str]] = []
    unmatched: list[dict[str, str]] = []
    for invoice in catalogue.values():
        review = _coerce_invoice_review(state.invoice_reviews.get(invoice.invoice_id))
        payment_id = (review.fields.get("payment.id") if review else None) or ""
        if payment_id and payment_id in transactions.transactions:
            matched.append({"invoice": invoice.invoice_id, "payment": payment_id})
        else:
            unmatched.append({"invoice": invoice.invoice_id})
    return InvoiceMatchProjection(period=period, matched=tuple(matched), unmatched=tuple(unmatched))


def _format_decimal(value: Decimal | None) -> str:
    if value is None:
        return "0"
    normalized = value.normalize()
    return format(normalized, "f")


__all__ = [
    "InvoiceMatchProjection",
    "InvoiceReviewProjection",
    "apply_manual_invoice_match",
    "invoice_display_amounts",
    "invoice_review_status",
    "project_invoice_payment_matches",
    "project_invoice_review",
    "project_invoice_reviews",
]
