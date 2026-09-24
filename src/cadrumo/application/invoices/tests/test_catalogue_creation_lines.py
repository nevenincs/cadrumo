"""Structured-line construction regressions for the catalogue writer."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....domain.invoices.enums import IvaRate
from ....domain.invoices.errors import InvoiceValidationError
from ....domain.invoices.models import InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ....tests.recorded_ecb_rates import recorded_ecb_rate_provider
from ..catalogue_creation import build_catalogue_invoice

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]
_RATE_21 = IvaRate.from_registry("RATE_21")


def _line(*, description: str, subtotal: str, iva_amount: str, iva_rate: IvaRate = _RATE_21) -> InvoiceLine:
    return InvoiceLine.model_validate(
        {
            "description": description,
            "quantity": "1",
            "unit_price": subtotal,
            "subtotal": subtotal,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
        },
    )


def _build(*, lines: tuple[InvoiceLine, ...] | None = None, taxable_base: Decimal | None = None):
    return build_catalogue_invoice(
        bucket_id="20202020-0000-4000-8000-000000000000",
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Papeleria Sol SL",
        counterparty_tax_id="A58818501",
        counterparty_country="ES",
        invoice_number="LINES-001",
        issued_at=date(2026, 3, 10),
        currency="EUR",
        rate_provider=recorded_ecb_rate_provider(),
        taxable_base=taxable_base,
        iva_rate=None if lines is not None else Decimal("21"),
        lines=lines,
    )


def test_structured_lines_derive_canonical_totals_and_preserve_order() -> None:
    first = _line(description="first", subtotal="10.00", iva_amount="2.10")
    second = _line(
        description="second",
        subtotal="5.00",
        iva_amount="0.50",
        iva_rate=IvaRate.from_registry("RATE_10"),
    )

    invoice = _build(lines=(first, second))

    assert invoice.lines == (first, second)
    assert invoice.base_total == Decimal("15.00")
    assert invoice.iva_total == Decimal("2.60")
    assert invoice.grand_total == Decimal("17.60")


def test_scalar_construction_still_synthesises_the_single_canonical_line() -> None:
    invoice = _build(taxable_base=Decimal("100.00"))

    assert invoice.base_total == Decimal("100.00")
    assert len(invoice.lines) == 1


def test_structured_lines_refuse_scalar_synthesis_inputs() -> None:
    with pytest.raises(InvoiceValidationError, match="structured lines"):
        _build(lines=(_line(description="first", subtotal="10.00", iva_amount="2.10"),), taxable_base=Decimal("10"))


def test_structured_lines_must_not_be_empty() -> None:
    with pytest.raises(InvoiceValidationError, match="lines must not be empty"):
        _build(lines=())
