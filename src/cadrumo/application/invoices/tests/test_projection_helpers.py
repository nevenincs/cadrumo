"""Focused unit tests for the invoices._projection pure helpers.

`_projection` exposes two pure-data helpers that drive the invoice
display column and the review-status badge:

- ``invoice_display_amounts(invoice, review)`` — returns ``(base,
  iva)`` adjusted by an optional :class:`InvoiceReviewRecord`. Handles
  ``RATE_X`` rate prefix, plain decimal rate, malformed rate (parsed
  via ``contextlib.suppress(InvalidOperation)``), and the computed-iva
  fallback when ``iva.amount`` is not explicit.
- ``invoice_review_status(invoice, review)`` — three-way dispatch
  on review record presence and field shape.

Currently no direct unit-test coverage. The public ``project_invoice_
reviews`` surface exercises the helpers indirectly through the
projection row builder, but the rate-prefix dispatch, the malformed-
rate suppression, and the explicit-iva-wins precedence all lack
focused coverage.

Tests here are structural / mapper-contract assertions on the
helpers, not calculation tautologies — the assertions verify the
helper's own contract (apply the review's overrides in the documented
order), not any external tax-authoritative calculation.
"""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal

import pytest

from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ...review.models import InvoiceReviewRecord
from .. import invoice_display_amounts, invoice_review_status

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _invoice(
    *,
    base_total: Decimal = Decimal("100.00"),
    iva_total: Decimal = Decimal("21.00"),
) -> Invoice:
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "INV-001",
            "issued_at": date(2026, 4, 1),
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": base_total,
            "iva_total": iva_total,
            "grand_total": base_total + iva_total,
            "currency": "EUR",
            "payment_status": PaymentStatus.PAID,
            "lines": (
                InvoiceLine.model_validate(
                    {
                        "description": "Servicios",
                        "quantity": Decimal("1"),
                        "unit_price": base_total,
                        "subtotal": base_total,
                        "iva_rate": IvaRate.RATE_21,
                        "iva_amount": iva_total,
                    },
                ),
            ),
        },
    )


#: ``invoice_id`` is a content-addressed digest, not the human invoice number
#: on the document; it is derived from that number so the fixture stays
#: readable while satisfying the identity type.
_INVOICE_ID = hashlib.sha256(b"INV-001").hexdigest()


def _review(fields: dict[str, str]) -> InvoiceReviewRecord:
    return InvoiceReviewRecord.model_validate({"invoice_id": _INVOICE_ID, "fields": fields})


# ---------------------------------------------------------------------------
# invoice_display_amounts — base + iva computation under review overrides
# ---------------------------------------------------------------------------


def test_invoice_display_amounts_passes_through_when_review_is_none() -> None:
    invoice = _invoice()

    base, iva = invoice_display_amounts(invoice, None)

    assert base == Decimal("100.00")
    assert iva == Decimal("21.00")


def test_invoice_display_amounts_applies_explicit_base_override_and_passes_iva_through() -> None:
    """An isolated `base` override changes the base but leaves the iva
    alone — there is no rate to recompute from."""
    invoice = _invoice()
    review = _review({"base": "200"})

    base, iva = invoice_display_amounts(invoice, review)

    assert base == Decimal("200")
    assert iva == Decimal("21.00")


def test_invoice_display_amounts_applies_explicit_iva_amount_override() -> None:
    invoice = _invoice()
    review = _review({"iva.amount": "33.33"})

    _base, iva = invoice_display_amounts(invoice, review)

    assert iva == Decimal("33.33")


def test_invoice_display_amounts_computes_iva_from_rate_prefix_with_base_override() -> None:
    """RATE_21 + base=200 → 200 * 0.21 = 42.00 quantized to 2 decimals."""
    invoice = _invoice()
    review = _review({"base": "200", "iva.rate": "RATE_21"})

    base, iva = invoice_display_amounts(invoice, review)

    assert base == Decimal("200")
    assert iva == Decimal("42.00")


def test_invoice_display_amounts_computes_iva_from_plain_decimal_rate() -> None:
    """Plain decimal rate (`"21"`) is divided by 100 just like the
    ``RATE_X`` prefix form."""
    invoice = _invoice()
    review = _review({"base": "200", "iva.rate": "21"})

    _base, iva = invoice_display_amounts(invoice, review)

    assert iva == Decimal("42.00")


def test_invoice_display_amounts_suppresses_malformed_rate_and_passes_iva_through() -> None:
    """A malformed `iva.rate` value is suppressed via
    ``contextlib.suppress(InvalidOperation)``; the rate stays None,
    no compute fires, and the iva is preserved from the invoice."""
    invoice = _invoice()
    review = _review({"iva.rate": "not-a-rate"})

    _base, iva = invoice_display_amounts(invoice, review)

    assert iva == Decimal("21.00")


def test_invoice_display_amounts_explicit_iva_amount_wins_over_computed_rate() -> None:
    """When both ``iva.amount`` and ``iva.rate`` are present, the
    explicit amount takes precedence over the rate-derived compute."""
    invoice = _invoice()
    review = _review({"base": "200", "iva.rate": "RATE_21", "iva.amount": "99.99"})

    _base, iva = invoice_display_amounts(invoice, review)

    assert iva == Decimal("99.99")


# ---------------------------------------------------------------------------
# invoice_review_status — three-way dispatch on review record presence
# ---------------------------------------------------------------------------


def test_invoice_review_status_returns_pending_when_review_is_none() -> None:
    invoice = _invoice()

    assert invoice_review_status(invoice, None) == "pending"


def test_invoice_review_status_returns_pending_when_review_fields_empty() -> None:
    invoice = _invoice()
    review = _review({})

    assert invoice_review_status(invoice, review) == "pending"


def test_invoice_review_status_returns_paid_when_payment_id_set() -> None:
    invoice = _invoice()
    review = _review({"payment.id": "tx-1"})

    assert invoice_review_status(invoice, review) == "paid"


def test_invoice_review_status_returns_reviewed_for_non_empty_fields_without_payment_id() -> None:
    invoice = _invoice()
    review = _review({"base": "100"})

    assert invoice_review_status(invoice, review) == "reviewed"


def test_invoice_review_status_returns_reviewed_when_payment_id_is_empty_string() -> None:
    """An empty `payment.id` is non-truthy after normalisation so it
    falls through to the second branch and yields `reviewed`."""
    invoice = _invoice()
    review = _review({"payment.id": ""})

    assert invoice_review_status(invoice, review) == "reviewed"
