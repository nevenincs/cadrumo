"""The factura rectificativa contract on the invoice record.

RD 1619/2012 art. 6.1.a forces a rectificativa into its own specific issuing
series (2.º of the "series obligatorias" list), and LIVA art. 89 requires a
rectification to name the invoice it corrects. Before this contract neither
fact was representable: the invoice record carried no invoice-class axis at
all, so a rectificativa looked identical to an ordinaria and had no field to
say what it corrected.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from ....domain.iva.classification import InvoiceKind
from ..enums import InvoiceClass, IvaRate, PaymentStatus
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
        "invoice_number": "2026/RECT-1",
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


def test_an_ordinary_invoice_defaults_to_the_ordinaria_class() -> None:
    """Every invoice before this guard is, and remains, an ordinaria."""
    invoice = _invoice()

    assert invoice.invoice_class is InvoiceClass.ORDINARIA
    assert invoice.series is None
    assert invoice.rectifies_invoice_number is None


def test_a_rectificativa_names_the_invoice_it_corrects_in_its_own_series() -> None:
    """The truthful rectificativa is representable with both mandatory facts."""
    invoice = _invoice(
        invoice_class=InvoiceClass.RECTIFICATIVA,
        series="R",
        rectifies_invoice_number="2026/RECT-0",
    )

    assert invoice.invoice_class is InvoiceClass.RECTIFICATIVA
    assert invoice.series == "R"
    assert invoice.rectifies_invoice_number == "2026/RECT-0"


def test_a_rectificativa_with_no_series_is_refused() -> None:
    """RD 1619/2012 art. 6.1.a.2.º makes a specific series obligatoria for rectificativas."""
    with pytest.raises(ValidationError, match="must be issued in a specific series"):
        _invoice(invoice_class=InvoiceClass.RECTIFICATIVA, rectifies_invoice_number="2026/RECT-0")


def test_a_rectificativa_naming_nothing_it_corrects_is_refused() -> None:
    """LIVA art. 89 requires a rectificativa to rectify a named prior invoice."""
    with pytest.raises(ValidationError, match="must name the invoice it rectifies"):
        _invoice(invoice_class=InvoiceClass.RECTIFICATIVA, series="R")


def test_a_stray_rectification_reference_on_an_ordinaria_is_refused() -> None:
    """The field only means something on a rectificativa; a stray reference is a contradiction.

    An ordinaria carrying ``rectifies_invoice_number`` would silently assert a
    correction the invoice's own declared class denies.
    """
    with pytest.raises(ValidationError, match="rectifies_invoice_number only applies to a factura rectificativa"):
        _invoice(rectifies_invoice_number="2026/RECT-0")


def test_a_series_alone_is_permitted_on_any_invoice_class() -> None:
    """Series are a general RD 1619/2012 art. 6.1.a concept, not exclusive to rectificativas."""
    invoice = _invoice(series="A")

    assert invoice.invoice_class is InvoiceClass.ORDINARIA
    assert invoice.series == "A"
