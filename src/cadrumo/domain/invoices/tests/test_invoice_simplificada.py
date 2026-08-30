"""The factura simplificada contract on the invoice record.

RD 1619/2012 art. 6.1.d makes the counterparty's tax id mandatory only in
three enumerated cases; a factura simplificada -- an ordinary ticket -- is
free of that requirement OUTSIDE those cases. Before this contract
``counterparty_tax_id`` was unconditionally required, so an ordinary retail
ticket with no identified customer could not be recorded as an invoice at
all -- a field the law does not require of it was refusing the document.

Case 3.º of art. 6.1.d (a domestic operation where the issuer is established
in the territorio de aplicación del impuesto) is deliberately NOT modelled:
this record carries no field naming where its issuer is established, so that
case is a declared gap, not a guessed default.
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

_BASE = Decimal("40.00")
_CUOTA = Decimal("8.40")


def _line() -> InvoiceLine:
    return InvoiceLine(
        description="Reparación urgente",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=IvaRate.RATE_21,
        iva_amount=_CUOTA,
    )


def _invoice(**overrides: Any) -> Invoice:
    payload: dict[str, Any] = {
        "kind": InvoiceKind.ISSUED,
        "invoice_class": InvoiceClass.SIMPLIFICADA,
        "invoice_number": "T-2026-001",
        "issued_at": date(2026, 5, 3),
        "counterparty_name": "Cliente de mostrador",
        "counterparty_tax_id": None,
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


def test_an_ordinary_ticket_needs_no_counterparty_tax_id() -> None:
    """The truthful ticket -- no customer identified -- is representable."""
    invoice = _invoice()

    assert invoice.invoice_class is InvoiceClass.SIMPLIFICADA
    assert invoice.counterparty_tax_id is None


def test_a_missing_tax_id_on_a_non_simplificada_invoice_is_refused() -> None:
    """Ordinaria and rectificativa keep the tax id mandatory, unchanged from before."""
    with pytest.raises(ValidationError, match="counterparty_tax_id is required unless invoice_class is SIMPLIFICADA"):
        _invoice(invoice_class=InvoiceClass.ORDINARIA)


def test_a_simplificada_is_refused_outright_for_an_exempt_intracommunity_supply() -> None:
    """RD 1619/2012 art. 4.4.a) forbids the class altogether, not merely its tax-id relief.

    Superseded by the stronger art. 4.4.a) eligibility guard
    (``test_invoice_simplificada_eligibility.py``): supplying a valid foreign
    tax id does not rescue this combination, because the document must never
    be SIMPLIFICADA for this category in the first place.
    """
    with pytest.raises(ValidationError, match=r"RD 1619/2012 art. 4.4.a"):
        _invoice(
            counterparty_country="DE",
            counterparty_tax_id="DE123456789",
            iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        )


def test_a_simplificada_still_requires_the_tax_id_when_the_destinatario_self_assesses() -> None:
    """RD 1619/2012 art. 6.1.d, 2.º: inversión del sujeto pasivo always needs it.

    On the ISSUED side ``domestic_reverse_charge`` carries a zero cuota by law
    (the recipient self-assesses), so the line must reflect that rather than
    an ordinary rated line.
    """
    zero_cuota_line = InvoiceLine(
        description="Servicio con inversión del sujeto pasivo",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=IvaRate.NOT_SUBJECT,
        iva_amount=Decimal("0"),
    )
    with pytest.raises(ValidationError, match=r"RD 1619/2012 art. 6.1.d"):
        _invoice(
            kind=InvoiceKind.ISSUED,
            iva_category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
            lines=(zero_cuota_line,),
            iva_total=Decimal("0"),
            grand_total=_BASE,
        )


def test_a_simplificada_with_no_declared_category_stays_untagged_and_needs_no_tax_id() -> None:
    """The undeclared-category case is not one of the three enumerated mandatory cases."""
    invoice = _invoice()

    assert invoice.iva_category is None
    assert invoice.counterparty_tax_id is None


def test_a_present_tax_id_still_carries_full_checksum_validation() -> None:
    """Optionality never relaxes validation when the field IS present."""
    with pytest.raises(ValidationError, match="checksum mismatch"):
        _invoice(counterparty_tax_id="B1234567X")


def test_a_valid_present_tax_id_on_a_simplificada_is_accepted_and_normalised() -> None:
    """A simplificada MAY still carry a tax id; when it does, it is validated like any other."""
    invoice = _invoice(counterparty_tax_id="b12345674")

    assert invoice.counterparty_tax_id == "B12345674"


def test_two_untagged_simplificadas_do_not_collide_on_invoice_id() -> None:
    """The stable hash still discriminates records with no counterparty tax id."""
    first = _invoice(invoice_number="T-2026-001")
    second = _invoice(invoice_number="T-2026-002")

    assert first.invoice_id != second.invoice_id


def test_a_received_simplificada_with_no_supplier_tax_id_is_refused() -> None:
    """The relief is ISSUED-only: on a RECEIVED invoice, ``counterparty_tax_id`` names the ISSUER.

    Art. 6.1.d's three cases govern the DESTINATARIO's NIF -- the customer on
    an ISSUED invoice, which is why the relief exists there. On a RECEIVED
    invoice the destinatario is the taxpayer (this app's own user, whose NIF
    is not even a field this record carries, since it is already known);
    ``counterparty_tax_id`` there is the SUPPLIER's own identification, which
    art. 6.1.d's opening clause and art. 7.1.d both keep mandatory regardless
    of class. Before this guard, a RECEIVED SIMPLIFICADA with no supplier NIF
    at all constructed successfully -- a document missing its own issuer's
    identity, not a legitimately relieved ticket.
    """
    with pytest.raises(
        ValidationError,
        match="counterparty_tax_id is required unless invoice_class is SIMPLIFICADA and kind is ISSUED",
    ):
        _invoice(kind=InvoiceKind.RECEIVED)


def test_a_received_simplificada_with_a_supplier_tax_id_is_accepted() -> None:
    """The truthful RECEIVED case: a real ticket naming its issuing supplier."""
    invoice = _invoice(kind=InvoiceKind.RECEIVED, counterparty_tax_id="B12345674")

    assert invoice.kind is InvoiceKind.RECEIVED
    assert invoice.counterparty_tax_id == "B12345674"
