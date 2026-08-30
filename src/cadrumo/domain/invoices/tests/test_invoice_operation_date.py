"""The fecha de operación contract on the invoice record.

RD 1619/2012 art. 6.1.i treats "the date the operation took place" and "the
date an advance payment was received" as ONE datum stated in one clause, so
:class:`~cadrumo.domain.invoices.Invoice` carries ONE date field plus a role
discriminator naming which of the two clauses the operator is stating --
never two separate date fields. Before this contract the invoice carried no
authoritative devengo-relevant date at all: the only date on the record was
``issued_at``, which art. 6.1.i itself says can differ from the operation
date and therefore cannot stand in for it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from ....domain.iva import InvoiceKind
from ..enums import InvoiceOperationDateRole, IvaRate, PaymentStatus
from ..models import Invoice, InvoiceLine

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

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


def _invoice(**overrides: Any) -> Invoice:
    payload: dict[str, Any] = {
        "kind": InvoiceKind.ISSUED,
        "invoice_number": "2026/OP-1",
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


def test_an_invoice_can_state_its_operation_date_distinct_from_the_issue_date() -> None:
    """The fecha de operación is representable, naming which art. 6.1.i clause it answers."""
    invoice = _invoice(
        operation_date=date(2026, 3, 28),
        operation_date_role=InvoiceOperationDateRole.OPERATION_PERFORMED,
    )

    assert invoice.operation_date == date(2026, 3, 28)
    assert invoice.operation_date_role is InvoiceOperationDateRole.OPERATION_PERFORMED
    assert invoice.operation_date != invoice.issued_at


def test_an_ordinary_invoice_declares_no_operation_date() -> None:
    """Most invoices never need the axis: the operation coincides with the issue date."""
    invoice = _invoice()

    assert invoice.operation_date is None
    assert invoice.operation_date_role is None


def test_a_date_without_a_role_is_refused() -> None:
    """A bare date would leave a reader guessing which art. 6.1.i clause it answers."""
    with pytest.raises(ValidationError, match="operation_date and operation_date_role must be set together"):
        _invoice(operation_date=date(2026, 3, 28))


def test_a_role_without_a_date_is_refused() -> None:
    """A role with nothing to date states nothing."""
    with pytest.raises(ValidationError, match="operation_date and operation_date_role must be set together"):
        _invoice(operation_date_role=InvoiceOperationDateRole.OPERATION_PERFORMED)


def test_the_role_is_one_field_not_a_second_date() -> None:
    """The regulation's two clauses share one datum; the model must not grow a second field.

    This is a structural pin rather than a behavioural one: an
    ``advance_payment_date`` field appearing alongside ``operation_date``
    would silently reintroduce the two-clause-as-two-fields shape the brief
    explicitly rejected.
    """
    assert not hasattr(Invoice, "advance_payment_date")
    assert not hasattr(Invoice, "anticipo_date")
