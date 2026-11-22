"""The facts a factura rectificativa states, and the combinations the write boundary refuses.

A rectificativa's figures are magnitudes like every other invoice's, so the
document alone does not say what modification it makes. RD 1619/2012 art. 15.5
permits exactly two readings of those figures, LIVA art. 89.Cinco and art. 114
place the modification in different periods depending on the side and the
ground, and the recipient's reception date is what art. 114.Dos keys most
received-side rectifications on. Before these facts existed the record could
hold none of them, so every rectificativa was a document whose modification was
unstateable.

Four rules follow from whose document states what, and each is proved here
through the real :class:`Invoice` boundary under the published authority:

- the facts only apply to a rectificativa;
- a reception date only applies to a received one;
- a reception cannot precede the issue;
- the totals stay non-negative magnitudes, the direction fact carrying the sense.

The fifth property is the one an eager implementation would get wrong: a
rectificativa stating NONE of the facts is ACCEPTED. The person records the
document as it reaches them; the declaration refuses later, naming the gaps.

Real-behaviour: real invoices through the real model validators over the
published authority, with the facts projected through the real fact 0141
vocabulary. No mocks, stubs, skips or xfail.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from ...calculations.registry.authority import bundled_indexed_authority
from ...calculations.registry.invoice_legal_classification import (
    resolve_invoice_legal_classification_catalogue,
)
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ...iva.schema import InvoiceKind
from ..enums import InvoiceClass, IvaRate, PaymentStatus, RectificationFact
from ..models import INVOICE_WRITE_ADMISSION, Invoice, InvoiceLine
from ..rectification import missing_rectification_facts, required_rectification_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR = filing_year_envelope().horizon
_ISSUED_AT = date(_YEAR, 4, 15)
_BASE = Decimal("1000.00")
_CUOTA = Decimal("210.00")


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    """Validate invoices under the generation-pinned authority production uses."""
    with bundled_indexed_authority().operation():
        yield


def _rectificativa(**overrides: Any) -> Invoice:
    """One received rectificativa with its two art. 6.1.a mandatory facts and nothing else.

    Admitted through ``INVOICE_WRITE_ADMISSION``, which is the context both
    production write paths pass: the rules under test are scoped to it, so a
    fixture that omitted it would prove nothing.
    """
    payload: dict[str, Any] = {
        "kind": InvoiceKind.RECEIVED,
        "invoice_class": InvoiceClass.from_registry("RECTIFICATIVA"),
        "series": "R",
        "rectifies_invoice_number": "2026/F-0001",
        "invoice_number": "2026/R-0001",
        "issued_at": _ISSUED_AT,
        "counterparty_name": "Proveedor SL",
        "counterparty_tax_id": "B00015016",
        "counterparty_country": "ES",
        "base_total": _BASE,
        "iva_total": _CUOTA,
        "grand_total": _BASE + _CUOTA,
        "currency": "EUR",
        "lines": (
            InvoiceLine(
                description="Abono por devolución de envases",
                quantity=Decimal("1"),
                unit_price=_BASE,
                subtotal=_BASE,
                iva_rate=IvaRate.from_registry("RATE_21"),
                iva_amount=_CUOTA,
            ),
        ),
        "payment_status": PaymentStatus.PENDING,
    }
    payload.update(overrides)
    return Invoice.model_validate(payload, context=INVOICE_WRITE_ADMISSION)


def _served_tokens() -> tuple[str, str, str]:
    """One method, cause and direction the registry actually declares for this date."""
    catalogue = resolve_invoice_legal_classification_catalogue(effective_date=_ISSUED_AT)
    return (
        str(catalogue.diferencia_token),
        str(catalogue.art_80_tres_cause_token),
        str(catalogue.minoracion_token),
    )


def test_a_rectificativa_carries_every_fact_the_document_states() -> None:
    """The four facts round trip onto the record as the projected registry tokens."""
    method, cause, direction = _served_tokens()

    invoice = _rectificativa(
        rectification_method=method,
        rectification_cause=cause,
        rectification_direction=direction,
        document_received_on=date(_YEAR, 4, 20),
    )

    assert str(invoice.rectification_method) == method
    assert str(invoice.rectification_cause) == cause
    assert str(invoice.rectification_direction) == direction
    assert invoice.document_received_on == date(_YEAR, 4, 20)
    assert missing_rectification_facts(invoice) == ()


def test_a_rectificativa_stating_none_of_the_facts_is_admitted_and_reports_every_gap() -> None:
    """The record takes the document as it arrived; the gaps are reported, never defaulted."""
    invoice = _rectificativa()

    assert invoice.rectification_method is None
    assert invoice.rectification_cause is None
    assert invoice.rectification_direction is None
    assert invoice.document_received_on is None
    assert missing_rectification_facts(invoice) == required_rectification_facts(InvoiceKind.RECEIVED)


def test_the_issued_side_needs_no_reception_date() -> None:
    """LIVA art. 114.Dos keys the recipient's period on reception; an issuer states none."""
    issued = _rectificativa(kind=InvoiceKind.ISSUED)

    assert RectificationFact.DOCUMENT_RECEIVED_ON not in missing_rectification_facts(issued)
    assert missing_rectification_facts(issued) == required_rectification_facts(InvoiceKind.ISSUED)
    assert len(missing_rectification_facts(issued)) == 3


def test_an_ordinaria_needs_none_of_the_facts() -> None:
    """A document of any other class states no rectification fact, so none is missing."""
    ordinaria = _rectificativa(
        invoice_class=InvoiceClass.from_registry("ORDINARIA"),
        series=None,
        rectifies_invoice_number=None,
    )

    assert missing_rectification_facts(ordinaria) == ()


@pytest.mark.parametrize(
    "fact",
    [
        RectificationFact.RECTIFICATION_METHOD,
        RectificationFact.RECTIFICATION_CAUSE,
        RectificationFact.RECTIFICATION_DIRECTION,
        RectificationFact.DOCUMENT_RECEIVED_ON,
    ],
)
def test_each_rectification_fact_is_refused_on_a_non_rectificativa(fact: RectificationFact) -> None:
    """Each fact asserts a correction the invoice's own class denies, so each is refused."""
    method, cause, direction = _served_tokens()
    values: dict[RectificationFact, object] = {
        RectificationFact.RECTIFICATION_METHOD: method,
        RectificationFact.RECTIFICATION_CAUSE: cause,
        RectificationFact.RECTIFICATION_DIRECTION: direction,
        RectificationFact.DOCUMENT_RECEIVED_ON: date(_YEAR, 4, 20),
    }

    with pytest.raises(ValidationError) as refusal:
        _rectificativa(
            invoice_class=InvoiceClass.from_registry("ORDINARIA"),
            series=None,
            rectifies_invoice_number=None,
            **{fact.value: values[fact]},
        )

    assert f"{fact.value} only applies to a factura rectificativa" in str(refusal.value)


def test_a_reception_date_is_refused_on_an_issued_rectificativa() -> None:
    """The issuer never observes the recipient's reception, which RIVA art. 24.1 makes them prove."""
    with pytest.raises(ValidationError) as refusal:
        _rectificativa(kind=InvoiceKind.ISSUED, document_received_on=date(_YEAR, 4, 20))

    assert "only applies to a received invoice" in str(refusal.value)


def test_a_reception_before_the_issue_is_refused() -> None:
    """Not a tight window: a document cannot arrive before it exists."""
    with pytest.raises(ValidationError) as refusal:
        _rectificativa(document_received_on=_ISSUED_AT - timedelta(days=1))

    assert "cannot be received before it was issued" in str(refusal.value)


def test_a_reception_on_the_issue_date_is_admitted() -> None:
    """The boundary is the issue date itself: same-day delivery is ordinary, not impossible."""
    invoice = _rectificativa(document_received_on=_ISSUED_AT)

    assert invoice.document_received_on == _ISSUED_AT


def test_a_rectificativa_keeps_its_totals_as_non_negative_magnitudes() -> None:
    """A minoración is recorded as a positive magnitude plus its direction, never a negative total.

    The sign belongs where the modification is projected. A record that could
    hold a negative base would make the direction fact redundant and give the
    same reduction two contradictory representations.
    """
    _, cause, direction = _served_tokens()

    minoracion = _rectificativa(rectification_cause=cause, rectification_direction=direction)

    assert minoracion.base_total == _BASE
    assert minoracion.iva_total == _CUOTA

    with pytest.raises(ValidationError) as refusal:
        _rectificativa(
            base_total=-_BASE,
            iva_total=-_CUOTA,
            grand_total=-(_BASE + _CUOTA),
            rectification_direction=direction,
        )

    assert "non-negative" in str(refusal.value)


@pytest.mark.parametrize("field", ["rectification_method", "rectification_cause", "rectification_direction"])
def test_a_token_the_registry_does_not_declare_is_refused(field: str) -> None:
    """The vocabulary is fact 0141's, so the record admits nothing the registry omits."""
    with pytest.raises(Exception) as refusal:
        _rectificativa(**{field: "no_such_token"})

    assert field in str(refusal.value)
