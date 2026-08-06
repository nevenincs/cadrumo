"""The entrega intracomunitaria destination-country contract on the invoice record.

RD 1619/2012 art. 6.1.d requires, for an entrega intracomunitaria exenta
(LIVA art. 25), a NIF "atribuido ... por la de otro Estado miembro" -- the
counterparty's tax id must be one the DESTINATION Member State issued.
Before this contract nothing tied :attr:`~cadrumo.domain.invoices.Invoice.iva_category`
to :attr:`~cadrumo.domain.invoices.Invoice.counterparty_country`: an
:class:`~cadrumo.domain.iva.IvaCategory.INTRA_COMMUNITY_SUPPLY` invoice with
``counterparty_country="ES"`` and a domestic Spanish CIF passed every
existing check, silently accepting a domestic number where the law names a
foreign one.

The guard is deliberately narrower than an EU-membership requirement:
Northern Ireland (``XI``) is a legitimate M349 goods destination under the
Windsor Framework despite not being one of the 27 Member States, and a
non-EU destination is a real declared fact downstream M349/export
classification judges, not this record. The one country the category can
never legitimately name is Spain itself.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from ....domain.iva import InvoiceKind, IvaCategory
from .. import Invoice, InvoiceLine, IvaRate, PaymentStatus

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BASE = Decimal("1000.00")


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
        "invoice_number": "2026/IC-1",
        "issued_at": date(2026, 4, 15),
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


def test_a_genuine_entrega_intracomunitaria_names_a_foreign_destination() -> None:
    """The truthful case: a real EU destination other than Spain is accepted."""
    invoice = _invoice()

    assert invoice.counterparty_country == "DE"
    assert invoice.iva_category is IvaCategory.INTRA_COMMUNITY_SUPPLY


def test_an_intracommunity_supply_naming_spain_is_refused() -> None:
    """The falsified case this Step exists to close: Spain cannot be its own destination.

    Before this guard, a Spanish counterparty country with a valid Spanish
    CIF passed every existing check on this category -- the domestic number
    RD 1619/2012 art. 6.1.d's foreign-NIF requirement exists to exclude.
    """
    with pytest.raises(ValidationError, match="must name a destination other than Spain"):
        _invoice(counterparty_country="ES", counterparty_tax_id="B12345674")


def test_northern_ireland_is_not_refused_despite_not_being_an_eu_member_state() -> None:
    """The guard is narrower than EU membership: XI is a real M349 goods destination."""
    invoice = _invoice(counterparty_country="XI", counterparty_tax_id="XI123456789")

    assert invoice.counterparty_country == "XI"


def test_a_non_eu_destination_is_not_refused_by_this_guard() -> None:
    """A non-EU destination is a declared fact for downstream classification, not this guard.

    The generic non-EU IVA-number shape check still applies (delegated to
    :func:`~cadrumo.domain.invoices.validate_iva_number`); this guard only
    ever refuses Spain.
    """
    invoice = _invoice(counterparty_country="US", counterparty_tax_id="US-TAX-1")

    assert invoice.counterparty_country == "US"


def test_the_guard_fires_even_when_the_category_alone_would_not_require_a_tax_id() -> None:
    """The contradiction is in the declared country itself, not in whether a tax id is required.

    A SIMPLIFICADA with this category would otherwise require a tax id under
    P06.S44's rule; supplying a valid one does not rescue an ES destination.
    """
    with pytest.raises(ValidationError, match="must name a destination other than Spain"):
        _invoice(counterparty_country="ES", counterparty_tax_id="B12345674")
