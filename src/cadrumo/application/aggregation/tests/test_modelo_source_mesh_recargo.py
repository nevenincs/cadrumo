"""Recargo-equivalencia source-mesh screening contracts for Modelo 303."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.invoices.enums import resolve_iva_rate_token

from ....domain.invoices.enums import PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.classification import InvoiceKind as CatalogueInvoiceKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "28282828-2828-4828-8828-282828282828"


def test_a_multi_tier_recargo_is_not_attributed_to_a_guessed_tier() -> None:
    """An ambiguous attribution is skipped, not guessed.

    The recargo is recorded once on the invoice while the M303 casillas are per
    rate tier. When the invoice spans several tiers the invoice-level field
    cannot say how the surcharge divides.

    Placing a real amount in the wrong casilla is worse than the screen not
    seeing it: a mis-tiered recargo is a wrong figure declared confidently,
    where an unscreened one is only unscreened. That gap is a limit of the
    invoice-level field, not of this screen.
    """
    from .._modelo_bindings_invoice_iva import _sole_recargo_bearing_line_index

    mixed = Invoice.model_validate(
        {
            "bucket_id": _BUCKET_ID,
            "kind": CatalogueInvoiceKind.ISSUED,
            "invoice_number": "RECARGO-MIXED",
            "issued_at": date(2025, 2, 10),
            "counterparty_name": "Minorista Recargo SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("1500.00"),
            "iva_total": Decimal("260.00"),
            "recargo_amount": Decimal("60.00"),
            "grand_total": Decimal("1820.00"),
            "currency": "EUR",
            "lines": (
                InvoiceLine(
                    description="General",
                    quantity=Decimal("1"),
                    unit_price=Decimal("1000.00"),
                    subtotal=Decimal("1000.00"),
                    iva_rate=resolve_iva_rate_token("rate_21", date.today()),
                    iva_amount=Decimal("210.00"),
                ),
                InvoiceLine(
                    description="Reducido",
                    quantity=Decimal("1"),
                    unit_price=Decimal("500.00"),
                    subtotal=Decimal("500.00"),
                    iva_rate=resolve_iva_rate_token("rate_10", date.today()),
                    iva_amount=Decimal("50.00"),
                ),
            ),
            "payment_status": PaymentStatus.PAID,
        },
    )

    assert _sole_recargo_bearing_line_index(mixed) is None
