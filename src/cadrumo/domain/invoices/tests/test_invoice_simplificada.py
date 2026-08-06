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

import pytest
from pydantic import ValidationError

from ....domain.iva import InvoiceKind, IvaCategory
from .. import Invoice, InvoiceClass, InvoiceLine, IvaRate, PaymentStatus

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


def _invoice(**overrides: object) -> Invoice:
    payload: dict[str, object] = {
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


def test_a_simplificada_still_requires_the_tax_id_for_an_exempt_intracommunity_supply() -> None:
    """RD 1619/2012 art. 6.1.d, 1.º: an entrega intracomunitaria exenta always needs it."""
    with pytest.raises(ValidationError, match=r"RD 1619/2012 art. 6.1.d"):
        _invoice(
            counterparty_country="DE",
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
