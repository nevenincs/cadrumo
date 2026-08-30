"""The factura simplificada ELIGIBILITY contract, distinct from its content relief.

RD 1619/2012 art. 6.1.d relaxes the counterparty tax id requirement for a
factura simplificada outside three enumerated cases (see
``test_invoice_simplificada.py``). That is a CONTENT question: given an
invoice already classed SIMPLIFICADA, which fields does it still need? Art. 4
answers a separate, prior ELIGIBILITY question: may this operation be
documented as a factura simplificada AT ALL? Before this contract nothing on
the invoice record answered the second question, so a document could declare
itself SIMPLIFICADA for an operation art. 4.4 forbids outright and pass every
existing check -- the tax-id relief the class carries would then apply to an
operation the class itself was never permitted to name.

Art. 4.4.a) is the one exclusion this record can enforce without inventing a
fact it has no field for: an entrega intracomunitaria exenta (LIVA art. 25,
``IvaCategory.INTRA_COMMUNITY_SUPPLY``) may never be documented as SIMPLIFICADA,
independent of amount, tax id, or anything else declared on the document.

Art. 4 also carries amount-based eligibility (a 400 EUR general ceiling, a
3.000 EUR ceiling restricted to a closed list of ~14 specific sectors such as
ventas al por menor, hostelería, or peluquería) and an AEAT-discretionary
authorisation for other cases (art. 4.3). Neither axis is modelled: the record
has no field naming which of the closed sector list an operation belongs to,
and the AEAT authorisation is a live administrative fact no document field
could ever state. That gap is declared, not silently assumed away: eligibility
resting on sector membership or a live AEAT authorisation is out of scope for
this record and must be judged by the taxpayer before filing.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory
from ..enums import InvoiceClass, IvaRate, PaymentStatus
from ..models import Invoice, InvoiceLine

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BASE = Decimal("1000.00")
_CUOTA = Decimal("210.00")


def _rated_line() -> InvoiceLine:
    return InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=IvaRate.RATE_21,
        iva_amount=_CUOTA,
    )


def _exempt_line() -> InvoiceLine:
    return InvoiceLine(
        description="Entrega intracomunitaria",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=IvaRate.EXEMPT,
        iva_amount=Decimal("0"),
    )


def _invoice(**overrides: Any) -> Invoice:
    payload: dict[str, Any] = {
        "kind": InvoiceKind.ISSUED,
        "invoice_number": "2026/EL-1",
        "issued_at": date(2026, 5, 3),
        "counterparty_name": "Cliente DE",
        "counterparty_tax_id": "DE123456789",
        "counterparty_country": "DE",
        "base_total": _BASE,
        "iva_total": Decimal("0"),
        "grand_total": _BASE,
        "currency": "EUR",
        "lines": (_exempt_line(),),
        "payment_status": PaymentStatus.PAID,
        "iva_category": IvaCategory.INTRA_COMMUNITY_SUPPLY,
    }
    payload.update(overrides)
    return Invoice(**payload)  # type: ignore[arg-type]


def test_a_simplificada_entrega_intracomunitaria_is_refused_regardless_of_tax_id() -> None:
    """The falsified case this guard exists to close.

    A valid foreign tax id is present -- the content relief question is
    already moot -- and the document is STILL refused, because art. 4.4.a)
    forbids the class for this operation outright, not merely the tax-id
    relief that would otherwise come with it.
    """
    with pytest.raises(ValidationError, match=r"RD 1619/2012 art. 4.4.a"):
        _invoice(invoice_class=InvoiceClass.SIMPLIFICADA)


def test_the_same_operation_is_representable_as_an_ordinaria() -> None:
    """The truthful companion: the identical entrega intracomunitaria, correctly classed."""
    invoice = _invoice(invoice_class=InvoiceClass.ORDINARIA)

    assert invoice.invoice_class is InvoiceClass.ORDINARIA
    assert invoice.iva_category is IvaCategory.INTRA_COMMUNITY_SUPPLY


def test_a_rectificativa_correcting_an_intracommunity_supply_is_unaffected() -> None:
    """Art. 4.4.a) names SIMPLIFICADA specifically; a rectificativa is a different class."""
    invoice = _invoice(
        invoice_class=InvoiceClass.RECTIFICATIVA,
        series="R",
        rectifies_invoice_number="2026/EL-0",
    )

    assert invoice.invoice_class is InvoiceClass.RECTIFICATIVA
    assert invoice.iva_category is IvaCategory.INTRA_COMMUNITY_SUPPLY


def test_a_simplificada_for_a_different_category_is_unaffected() -> None:
    """The guard is keyed on the category, not a blanket refusal of SIMPLIFICADA.

    A domestic ticket-style sale still needs no counterparty tax id at all
    (RD 1619/2012 art. 6.1.d, outside its three mandatory cases).
    """
    invoice = _invoice(
        invoice_class=InvoiceClass.SIMPLIFICADA,
        counterparty_country="ES",
        counterparty_tax_id=None,
        lines=(_rated_line(),),
        iva_total=_CUOTA,
        grand_total=_BASE + _CUOTA,
        iva_category=IvaCategory.DOMESTIC_GENERAL,
    )

    assert invoice.invoice_class is InvoiceClass.SIMPLIFICADA
    assert invoice.counterparty_tax_id is None


def test_a_simplificada_with_no_declared_category_is_unaffected() -> None:
    """An untagged category cannot trigger a category-specific exclusion."""
    invoice = _invoice(
        invoice_class=InvoiceClass.SIMPLIFICADA,
        counterparty_country="ES",
        counterparty_tax_id=None,
        lines=(_rated_line(),),
        iva_total=_CUOTA,
        grand_total=_BASE + _CUOTA,
        iva_category=None,
    )

    assert invoice.invoice_class is InvoiceClass.SIMPLIFICADA
    assert invoice.iva_category is None
