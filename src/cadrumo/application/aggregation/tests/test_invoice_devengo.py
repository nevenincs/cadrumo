"""Tests for the LIVA art. 75 devengo-date resolution helper.

:func:`invoice_devengo_date` is the fact a future period-attribution wiring
(P06.S48) will read; these tests pin the fact itself -- that the invoice's own
recorded ``operation_date`` (under either art. 75 role) is preferred over the
issue-date proxy, and that the proxy is the correct fallback when no
``operation_date`` was ever recorded.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....domain.invoices import Invoice, InvoiceLine, InvoiceOperationDateRole, IvaRate, PaymentStatus
from ....domain.iva import InvoiceKind
from .. import invoice_devengo_date

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BASE = Decimal("1000.00")
_CUOTA = Decimal("210.00")


def _line() -> InvoiceLine:
    return InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=IvaRate.RATE_21,
        iva_amount=_CUOTA,
    )


def _invoice(**overrides: object) -> Invoice:
    payload: dict[str, object] = {
        "kind": InvoiceKind.ISSUED,
        "invoice_number": "2026/DEV-1",
        "issued_at": date(2026, 4, 15),
        "counterparty_name": "Cliente SL",
        "counterparty_tax_id": "B12345674",
        "counterparty_country": "ES",
        "base_total": _BASE,
        "iva_total": _CUOTA,
        "grand_total": _BASE + _CUOTA,
        "currency": "EUR",
        "lines": (_line(),),
        "payment_status": PaymentStatus.PAID,
    }
    payload.update(overrides)
    return Invoice(**payload)  # type: ignore[arg-type]


def test_an_undated_invoice_falls_back_to_the_issue_date_proxy() -> None:
    """No recorded operation date: the only date on the record is the proxy."""
    invoice = _invoice()

    assert invoice_devengo_date(invoice) == invoice.issued_at


def test_a_recorded_operation_date_takes_precedence_over_the_issue_date() -> None:
    """Art. 75.Uno: the general-regime devengo date, when it differs from issue."""
    invoice = _invoice(
        operation_date=date(2026, 3, 28),
        operation_date_role=InvoiceOperationDateRole.OPERATION_PERFORMED,
    )

    assert invoice_devengo_date(invoice) == date(2026, 3, 28)
    assert invoice_devengo_date(invoice) != invoice.issued_at


def test_a_pago_anticipado_collection_date_is_read_identically() -> None:
    """Art. 75.Dos: the collection date is the devengo date, read the same way.

    The role changes WHICH clause supplied the date, not how this helper
    reads it -- both cases resolve to the recorded ``operation_date``.
    """
    invoice = _invoice(
        operation_date=date(2026, 4, 1),
        operation_date_role=InvoiceOperationDateRole.ADVANCE_PAYMENT_RECEIVED,
    )

    assert invoice_devengo_date(invoice) == date(2026, 4, 1)
