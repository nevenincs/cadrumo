"""Behavioural tests for the :class:`Invoice` retención consistency contract.

Pins three things a later edit could plausibly get wrong, each of which
silently changes a declared tax figure rather than failing loudly:

* the retención base is the **base imponible**, not the IVA-inclusive total
  (RIRPF art. 95.1 withholds "sobre los ingresos íntegros satisfechos", and the
  IVA repercutido is not an ingreso of the issuer per PGC NRV 12.ª/14.ª);
* ``retention_rate`` is a fraction, so a percentage written into it is refused
  rather than read as a hundredfold rate;
* retención never enters ``grand_total`` -- an invoice whose total was netted
  of the withholding is refused.

The expected figures here are the arithmetic of a declared rate against a
declared base, which is a *contract* the model enforces rather than a
regulatory formula under test; the legally-grounded choice each case pins is
which base the rate applies to, and every case would still fail if that choice
were changed.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ...iva.classification import InvoiceKind
from ..enums import IvaRate, PaymentStatus, iva_rate_percentage
from ..models import Invoice, InvoiceLine

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _line(unit_price: str) -> InvoiceLine:
    """Return one general-rate line worth ``unit_price``."""
    subtotal = Decimal(unit_price)
    rate = iva_rate_percentage(IvaRate.RATE_21)
    assert rate is not None
    return InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=subtotal,
        subtotal=subtotal,
        iva_rate=IvaRate.RATE_21,
        iva_amount=subtotal * rate,
    )


def _invoice(
    *,
    unit_price: str = "1000.00",
    retention_rate: Decimal | None = None,
    retention_amount: Decimal | None = None,
    grand_total: Decimal | None = None,
) -> Invoice:
    """Build a domestic professional invoice with the given retención fields."""
    line = _line(unit_price)
    base_total = line.subtotal
    iva_total = line.iva_amount
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "F-2026-001",
            "issued_at": date(2026, 4, 1),
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": base_total,
            "iva_total": iva_total,
            "grand_total": base_total + iva_total if grand_total is None else grand_total,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "retention_rate": retention_rate,
            "retention_amount": retention_amount,
        },
    )


def test_declared_retencion_consistent_with_the_base_is_accepted() -> None:
    """A rate/amount pair agreeing on the base imponible validates."""
    invoice = _invoice(retention_rate=Decimal("0.15"), retention_amount=Decimal("150.00"))

    assert invoice.retention_amount == Decimal("150.00")
    assert invoice.grand_total == Decimal("1210.00")


def test_retencion_amount_may_stand_alone_without_a_rate() -> None:
    """An invoice may record what was withheld without recording the rate."""
    invoice = _invoice(retention_amount=Decimal("150.00"))

    assert invoice.retention_amount == Decimal("150.00")
    assert invoice.retention_rate is None


def test_retencion_rate_alone_is_refused() -> None:
    """A rate with no amount declares a proportion of nothing."""
    with pytest.raises(ValidationError, match="rate alone declares no withheld figure"):
        _invoice(retention_rate=Decimal("0.15"))


def test_retencion_rate_written_as_a_percentage_is_refused() -> None:
    """``15`` for "15 %" must not be read as a 1500 % rate."""
    with pytest.raises(ValidationError, match="must be a fraction between 0 and 1"):
        _invoice(retention_rate=Decimal("15"), retention_amount=Decimal("150.00"))


def test_negative_retencion_amount_is_refused() -> None:
    """A withheld figure is a magnitude."""
    with pytest.raises(ValidationError, match="retention_amount must be non-negative"):
        _invoice(retention_amount=Decimal("-150.00"))


def test_retencion_amount_above_the_base_is_refused() -> None:
    """Nothing can withhold more than the ingresos íntegros it withholds from."""
    with pytest.raises(ValidationError, match="must not exceed base_total"):
        _invoice(retention_amount=Decimal("1000.01"))


def test_retencion_amount_disagreeing_with_its_declared_rate_is_refused() -> None:
    """A pair that cannot both be true is a recording defect, not a rounding one."""
    with pytest.raises(ValidationError, match="within 1 cent"):
        _invoice(retention_rate=Decimal("0.15"), retention_amount=Decimal("70.00"))


def test_retencion_rate_product_is_allowed_one_cent_of_rounding() -> None:
    """A rate applied to a base rounds; the issuer's cent is accepted.

    ``0.15 * 333.33`` is ``49.9995``; an issuer who printed ``50.00`` rounded
    the same figure the model recomputes, so the pair is coherent.
    """
    invoice = _invoice(
        unit_price="333.33",
        retention_rate=Decimal("0.15"),
        retention_amount=Decimal("50.00"),
    )

    assert invoice.retention_amount == Decimal("50.00")


def test_retencion_base_is_the_base_imponible_not_the_grand_total() -> None:
    """15 % of the IVA-inclusive total is refused against a 15 % declared rate.

    ``0.15 * 1210.00 == 181.50`` is exactly the figure an implementation that
    withheld from the grand total would compute and accept. RIRPF art. 95.1
    withholds from the ingresos íntegros, so this pairing is incoherent and the
    case fails the moment the validator's base is changed.
    """
    with pytest.raises(ValidationError, match="within 1 cent"):
        _invoice(retention_rate=Decimal("0.15"), retention_amount=Decimal("181.50"))


def test_grand_total_netted_of_retencion_is_refused() -> None:
    """Retención is not a price component, so it never reduces the total.

    ``1210.00 - 150.00`` is the cash the payer transfers, not the
    contraprestación of the operation. Recording it as ``grand_total`` would
    under-state the operation and, because ``grand_total`` is an input to
    :func:`~cadrumo.domain.invoices.derive_invoice_id`, would also mint a
    different invoice identity for the same document.
    """
    with pytest.raises(ValidationError, match="grand_total must equal base_total \\+ iva_total"):
        _invoice(
            retention_rate=Decimal("0.15"),
            retention_amount=Decimal("150.00"),
            grand_total=Decimal("1060.00"),
        )
