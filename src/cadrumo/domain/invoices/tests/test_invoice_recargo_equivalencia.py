"""The recargo de equivalencia contract on the invoice record.

Before this contract the invoice identity was ``grand_total == base_total +
iva_total`` exactly, so a supplier invoicing a comerciante minorista could not
record what they actually charged. The refusal fell on the *truthful* document
and the falsified one -- recargo silently dropped from the total -- was
accepted, so the model actively selected for wrong data rather than merely
failing to express right data. The first two tests pin that polarity inverted.

The rest pin the algebra. Recargo and retención are the two optional terms on
the identity and they sit on opposite sides: LIVA art. 161 has the supplier
repercutir the recargo on the entrega, so the minorista owes it and it belongs
to what the operation cost, while retención only changes what the payer
transfers. A future simplification that moved either to the other side would
still balance for an invoice carrying just one of them, which is why the case
carrying both is tested explicitly.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from ....adapters.outbound.fx import ECB_RATE_SOURCE_ID
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory
from ..decomposition import decompose_invoice
from ..enums import IvaRate, PaymentStatus
from ..models import Invoice, InvoiceLine

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BASE = Decimal("1000.00")
_CUOTA = Decimal("210.00")
_RECARGO = Decimal("52.00")
"""LIVA art. 161 charges 5.2 % alongside the 21 % general rate."""


def _rated_line() -> InvoiceLine:
    return InvoiceLine(
        description="Mercaderia para minorista",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=IvaRate.RATE_21,
        iva_amount=_CUOTA,
    )


def _exempt_line() -> InvoiceLine:
    return InvoiceLine(
        description="Operacion exenta",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=IvaRate.EXEMPT,
        iva_amount=Decimal("0"),
    )


def _invoice(**overrides: Any) -> Invoice:
    payload: dict[str, Any] = {
        "kind": InvoiceKind.ISSUED,
        "invoice_number": "2026/RE-1",
        "issued_at": date(2026, 3, 15),
        "counterparty_name": "Minorista SL",
        "counterparty_tax_id": "B12345674",
        "counterparty_country": "ES",
        "base_total": _BASE,
        "iva_total": _CUOTA,
        "grand_total": _BASE + _CUOTA + _RECARGO,
        "currency": "EUR",
        "lines": (_rated_line(),),
        "payment_status": PaymentStatus.PAID,
        "recargo_amount": _RECARGO,
    }
    payload.update(overrides)
    return Invoice(**payload)  # type: ignore[arg-type]


def test_a_supplier_can_record_what_the_minorista_was_actually_charged() -> None:
    """The truthful recargo invoice is representable, and its total carries the surcharge."""
    invoice = _invoice()

    assert invoice.recargo_amount == _RECARGO
    assert invoice.grand_total == Decimal("1262.00")
    assert invoice.grand_total == invoice.base_total + invoice.iva_total + _RECARGO


def test_dropping_the_recargo_from_the_total_is_refused() -> None:
    """The falsified document -- surcharge charged but not totalled -- must not pass.

    This is the case the old identity accepted. An invoice recording a recargo
    the grand total does not include understates what the customer owes by
    exactly the surcharge.
    """
    with pytest.raises(ValidationError, match=r"grand_total must equal base_total \+ iva_total \+ recargo_amount"):
        _invoice(grand_total=_BASE + _CUOTA)


def test_an_ordinary_invoice_declares_no_recargo_and_an_explicit_zero_is_a_different_statement() -> None:
    """Unrecorded and does-not-apply stay distinguishable.

    The field is nullable rather than defaulted to zero precisely so these two
    do not collapse: ``None`` is "this invoice makes no statement about
    recargo", an explicit zero is "the régimen was considered and does not
    apply". Reading them as the same value is the absence-as-signal conflation
    the surrounding contract exists to remove.
    """
    silent = _invoice(recargo_amount=None, grand_total=_BASE + _CUOTA)
    declared_zero = _invoice(recargo_amount=Decimal("0"), grand_total=_BASE + _CUOTA)

    assert silent.recargo_amount is None
    assert declared_zero.recargo_amount == Decimal("0")
    assert silent.recargo_amount != declared_zero.recargo_amount
    assert silent.grand_total == declared_zero.grand_total


def test_a_negative_recargo_is_refused() -> None:
    """A surcharge that reduces the total is not a surcharge."""
    with pytest.raises(ValidationError, match="recargo_amount must be non-negative"):
        _invoice(recargo_amount=Decimal("-52.00"), grand_total=_BASE + _CUOTA - _RECARGO)


def test_a_recargo_larger_than_the_cuota_it_rides_on_is_refused() -> None:
    """Every statutory tier is a smaller percentage than its companion IVA rate.

    5.2 against 21, 1.4 against 10, 0.5 against 4: a recargo above the cuota is
    impossible under any tier, and is far more likely to be the cuota written
    into the wrong field.
    """
    with pytest.raises(ValidationError, match="recargo_amount must not exceed iva_total"):
        _invoice(recargo_amount=Decimal("300.00"), grand_total=_BASE + _CUOTA + Decimal("300.00"))


def test_a_recargo_on_an_all_exempt_supply_is_refused() -> None:
    """The recargo rides on the cuota of a taxable supply, so a cuota-less one bears none."""
    with pytest.raises(ValidationError, match="recargo_amount must be zero when every line is EXEMPT"):
        _invoice(
            lines=(_exempt_line(),),
            iva_total=Decimal("0"),
            grand_total=_BASE + _RECARGO,
        )


def test_the_decomposition_carries_the_recargo_into_the_contraprestacion() -> None:
    """A grounded recargo invoice decomposes with the surcharge inside ``total``."""
    verdict = decompose_invoice(_invoice(iva_category=IvaCategory.DOMESTIC_GENERAL))

    assert verdict.is_grounded
    components = verdict.components
    assert components is not None
    assert components.recargo == _RECARGO
    assert components.total == Decimal("1262.00")
    assert components.cash == Decimal("1262.00")


def test_recargo_and_retencion_sit_on_opposite_sides_of_the_identity() -> None:
    """The load-bearing polarity test: one term joins ``total``, the other only ``cash``.

    An invoice carrying just one of the two would still balance if a future
    change moved that term to the other side, so only the case carrying both
    can catch the swap. The combination is unusual in practice -- recargo
    attaches to entregas de bienes and retención to professional services --
    but the model must not silently mis-place either.
    """
    retencion = Decimal("150.00")
    verdict = decompose_invoice(
        _invoice(iva_category=IvaCategory.DOMESTIC_GENERAL, retention_amount=retencion),
    )

    components = verdict.components
    assert components is not None
    # Recargo is inside the contraprestación; retención is not.
    assert components.total == _BASE + _CUOTA + _RECARGO
    # Retención comes off the cash; recargo does not.
    assert components.cash == components.total - retencion
    assert components.cash == Decimal("1112.00")


def test_the_recargo_converts_to_euro_with_the_rest_of_the_invoice() -> None:
    """A foreign-currency recargo is converted, not passed through as face value."""
    invoice = _invoice(
        currency="USD",
        fx_rate=Decimal("0.90"),
        fx_rate_date=date(2026, 3, 15),
        fx_rate_source=ECB_RATE_SOURCE_ID,
    )

    assert invoice.recargo_amount_eur == Decimal("46.80")


def test_an_unconverted_foreign_recargo_reports_no_euro_figure() -> None:
    """Without a resolved rate the euro value is unknown rather than the face value."""
    invoice = _invoice(currency="USD")

    assert invoice.recargo_amount is not None
    assert invoice.recargo_amount_eur is None
