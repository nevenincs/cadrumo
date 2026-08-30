"""The pago anticipado devengo contract on the invoice record.

LIVA art. 75.Dos moves devengo forward to the date of collection for an
advance payment received before the hecho imponible, "por los importes
efectivamente percibidos" -- money must actually have been received -- and
its second párrafo excludes "las entregas de bienes comprendidas en el
artículo 25" (an entrega intracomunitaria exenta) from that rule outright:
those always devengue under art. 75.Uno.8.º regardless of any advance.

The invoice records this through the SAME ``operation_date`` /
``operation_date_role`` axis art. 6.1.i already carries for the general-regime
operation date (see ``test_invoice_operation_date.py``); this module tests
the two guards specific to the ``ADVANCE_PAYMENT_RECEIVED`` role.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory
from ..enums import InvoiceOperationDateRole, IvaRate, PaymentStatus
from ..models import Invoice, InvoiceLine

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BASE = Decimal("1000.00")
_CUOTA = Decimal("210.00")


def _rated_line() -> InvoiceLine:
    return InvoiceLine(
        description="Anticipo de servicios",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=IvaRate.RATE_21,
        iva_amount=_CUOTA,
    )


def _exempt_line() -> InvoiceLine:
    return InvoiceLine(
        description="Entrega intracomunitaria exenta",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=IvaRate.EXEMPT,
        iva_amount=Decimal("0"),
    )


def _invoice(**overrides: Any) -> Invoice:
    payload: dict[str, Any] = {
        "kind": InvoiceKind.ISSUED,
        "invoice_number": "2026/ANT-1",
        "issued_at": date(2026, 6, 20),
        "counterparty_name": "Cliente SL",
        "counterparty_tax_id": "B12345674",
        "counterparty_country": "ES",
        "base_total": _BASE,
        "iva_total": _CUOTA,
        "grand_total": _BASE + _CUOTA,
        "currency": "EUR",
        "lines": (_rated_line(),),
        "payment_status": PaymentStatus.PAID,
        "operation_date": date(2026, 6, 10),
        "operation_date_role": InvoiceOperationDateRole.ADVANCE_PAYMENT_RECEIVED,
    }
    payload.update(overrides)
    return Invoice(**payload)  # type: ignore[arg-type]


def test_a_fully_collected_advance_payment_devengues_on_collection() -> None:
    """The truthful pago anticipado invoice is representable."""
    invoice = _invoice()

    assert invoice.operation_date == date(2026, 6, 10)
    assert invoice.operation_date_role is InvoiceOperationDateRole.ADVANCE_PAYMENT_RECEIVED


def test_a_partially_collected_advance_payment_is_also_permitted() -> None:
    """Art. 75.Dos's "cobro total o parcial" covers a partial collection too."""
    invoice = _invoice(payment_status=PaymentStatus.PARTIALLY_PAID)

    assert invoice.payment_status is PaymentStatus.PARTIALLY_PAID


@pytest.mark.parametrize("status", [PaymentStatus.PENDING, PaymentStatus.OVERDUE, PaymentStatus.CANCELLED])
def test_an_advance_payment_role_with_nothing_collected_is_refused(status: PaymentStatus) -> None:
    """Art. 75.Dos devengues on actual cobro; a status stating none happened contradicts the role."""
    with pytest.raises(ValidationError, match="requires a collected payment_status"):
        _invoice(payment_status=status)


def test_the_article_25_exclusion_refuses_an_advance_payment_devengo() -> None:
    """LIVA art. 75.Dos, párrafo segundo: an entrega intracomunitaria exenta is excluded outright.

    This is the load-bearing refusal: without it, the model would accept a
    devengo-shifting declaration the law does not permit for this category,
    silently misattributing the operation's period.
    """
    with pytest.raises(ValidationError, match="does not apply to an entrega intracomunitaria exenta"):
        _invoice(
            counterparty_country="DE",
            counterparty_tax_id="DE123456789",
            lines=(_exempt_line(),),
            iva_total=Decimal("0"),
            grand_total=_BASE,
            iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        )


def test_the_same_amounts_devengue_normally_without_the_advance_payment_role() -> None:
    """The control: an ordinary operation date on the same category is unaffected.

    Proves the exclusion is keyed on the ADVANCE_PAYMENT_RECEIVED role, not on
    the category alone -- otherwise this case would also be wrongly refused.
    """
    invoice = _invoice(
        counterparty_country="DE",
        counterparty_tax_id="DE123456789",
        lines=(_exempt_line(),),
        iva_total=Decimal("0"),
        grand_total=_BASE,
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        operation_date_role=InvoiceOperationDateRole.OPERATION_PERFORMED,
    )

    assert invoice.operation_date_role is InvoiceOperationDateRole.OPERATION_PERFORMED
