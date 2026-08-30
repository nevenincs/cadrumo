"""The entrega intracomunitaria acquirer-IDENTIFICATION contract on the invoice record.

RD 1619/2012 art. 6.1.d requires, for an entrega intracomunitaria exenta
(LIVA art. 25), a NIF "atribuido ... por la de otro Estado miembro" -- the
acquirer must purchase under an IVA identification another Member State issued.
That is a fact about REGISTRATION, and the record now carries it as
:attr:`~cadrumo.domain.invoices.Invoice.counterparty_identification_state`.

The guard previously read
:attr:`~cadrumo.domain.invoices.Invoice.counterparty_country` as a stand-in for
it. The two are different facts and they diverge in real trade, so the stand-in
was wrong in both directions: it refused a Spanish-ESTABLISHED acquirer holding
a French IVA number -- an entrega intracomunitaria art. 25 exempts, which could
not previously be recorded at all -- while accepting a German-established
acquirer purchasing under a Spanish NIF-IVA, which is a domestic supply.

The guard stays narrower than an EU-membership requirement: Northern Ireland
(``XI``) is a legitimate M349 goods destination under the Windsor Framework
despite not being one of the 27 Member States. The one identification the
category can never legitimately name is a Spanish one.

Absent identification is NOT refused here. It is not a contradiction, it is an
unrecorded fact, and the aggregation gate withholds such a row with a review
item rather than letting this record invent one from the address.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from ....domain.iva import EUMemberState, InvoiceKind, IvaCategory
from ..enums import IvaRate, PaymentStatus
from ..models import Invoice, InvoiceLine

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BASE = Decimal("1000.00")
_REFUSAL = "cannot name an acquirer purchasing under a Spanish IVA identification"


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
        "counterparty_identification_state": EUMemberState.DE,
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


def test_a_genuine_entrega_intracomunitaria_names_a_foreign_identification() -> None:
    """The truthful case: an acquirer identified in another Member State is accepted."""
    invoice = _invoice()

    assert invoice.counterparty_identification_state is EUMemberState.DE
    assert invoice.iva_category is IvaCategory.INTRA_COMMUNITY_SUPPLY


def test_an_intracommunity_supply_to_a_spanish_identified_acquirer_is_refused() -> None:
    """The falsified case: a Spanish IVA identification contradicts the category.

    The ESTABLISHMENT is German here, deliberately. The refusal must come from
    the identification alone, otherwise the guard has merely moved the old
    country check behind a new name.
    """
    with pytest.raises(ValidationError, match=_REFUSAL):
        _invoice(counterparty_identification_state=EUMemberState.ES)


def test_a_spanish_established_acquirer_identified_abroad_is_accepted() -> None:
    """The direction the old country-keyed guard refused outright.

    A Spanish-established acquirer holding a French IVA number is an
    intra-community acquirer under art. 25. Keyed on the address this invoice
    could not be constructed, so the exemption was unreachable and the supply
    was declared with Spanish IVA -- over-declaration.
    """
    invoice = _invoice(
        counterparty_country="ES",
        counterparty_tax_id="B12345674",
        counterparty_identification_state=EUMemberState.FR,
    )

    assert invoice.counterparty_country == "ES"
    assert invoice.counterparty_identification_state is EUMemberState.FR


def test_northern_ireland_is_not_refused_despite_not_being_an_eu_member_state() -> None:
    """The guard is narrower than EU membership: XI is a real M349 goods destination."""
    invoice = _invoice(
        counterparty_country="XI",
        counterparty_tax_id="XI123456789",
        counterparty_identification_state=EUMemberState.XI,
    )

    assert invoice.counterparty_identification_state is EUMemberState.XI


def test_an_unrecorded_identification_is_not_refused_by_this_guard() -> None:
    """Absence is not a contradiction, and this record must not invent the fact.

    The aggregation gate is where an unanswered question is raised, with a
    review item naming what to supply. Refusing here would instead push an
    operator toward reading the address as the answer.
    """
    invoice = _invoice(
        counterparty_country="US",
        counterparty_tax_id="US-TAX-1",
        counterparty_identification_state=None,
    )

    assert invoice.counterparty_identification_state is None


def test_the_recorded_identification_governs_over_the_printed_number() -> None:
    """The guard reads the recorded fact, not whatever the document happened to print.

    Every other field here says Germany -- the address AND a structurally valid
    German IVA number. Only the recorded identification says Spain, and that
    alone refuses. This is the separation the field exists for: a printed number
    is evidence about identification, not identification itself, and an operator
    who has established that the acquirer actually purchases under a Spanish
    NIF-IVA has recorded something the document does not show.
    """
    with pytest.raises(ValidationError, match=_REFUSAL):
        _invoice(
            counterparty_country="DE",
            counterparty_tax_id="DE123456789",
            counterparty_identification_state=EUMemberState.ES,
        )
