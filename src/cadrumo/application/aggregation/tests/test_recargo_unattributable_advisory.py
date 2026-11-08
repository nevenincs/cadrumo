"""A recargo the screen cannot divide by rate is reported, not silently left out.

The recargo de equivalencia is recorded once per invoice while the Modelo 303
recargo casillas are per IVA rate. For an invoice whose cuota lines sit at
several rates the screen declines to guess a rate, which is right, but it also
left the recargo out of its comparison with the transaction ledger without a
word: a ledger that omitted that recargo passed the screen as though checked.

The screen runs for real here, over the published authority and real invoices;
the invoices are passed in directly.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.invoices.enums import PaymentStatus, resolve_iva_rate_token
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind
from ..modelo_bindings_invoice_iva import (
    recargo_unattributable_diagnostics,
    screened_invoice_iva_observations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "30303030-3030-4030-8030-303030303030"
_YEAR = 2026
_PERIOD_CODE = "2T"
_ISSUED = date(2026, 5, 12)


def _line(description: str, base: str, rate: str, cuota: str) -> InvoiceLine:
    return InvoiceLine(
        description=description,
        quantity=Decimal("1"),
        unit_price=Decimal(base),
        subtotal=Decimal(base),
        iva_rate=resolve_iva_rate_token(rate, _ISSUED),
        iva_amount=Decimal(cuota),
    )


def _issued(number: str, lines: tuple[InvoiceLine, ...], *, recargo: str) -> Invoice:
    base = sum((line.subtotal for line in lines), Decimal("0"))
    cuota = sum((line.iva_amount for line in lines), Decimal("0"))
    return Invoice.model_validate(
        {
            "bucket_id": _BUCKET_ID,
            "kind": InvoiceKind.ISSUED,
            "invoice_number": number,
            "issued_at": _ISSUED,
            "counterparty_name": "Minorista Recargo SL",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "base_total": base,
            "iva_total": cuota,
            "recargo_amount": Decimal(recargo),
            "grand_total": base + cuota + Decimal(recargo),
            "currency": "EUR",
            "lines": lines,
            "payment_status": PaymentStatus.PAID,
        },
    )


def _mixed() -> Invoice:
    return _issued(
        "RECARGO-MIXED",
        (_line("General", "1000.00", "RATE_21", "210.00"), _line("Reducido", "500.00", "RATE_10", "50.00")),
        recargo="59.00",
    )


def _single() -> Invoice:
    return _issued("RECARGO-SINGLE", (_line("General", "1000.00", "RATE_21", "210.00"),), recargo="52.00")


def _screen(*invoices: Invoice):
    period = Period.from_year_and_code(_YEAR, _PERIOD_CODE)
    with bundled_indexed_authority().operation() as operation:
        return screened_invoice_iva_observations(
            invoices,
            bucket_id=_BUCKET_ID,
            period=period,
            linked_movements={},
            operation=operation,
        )


def test_a_recargo_over_several_rates_is_named_by_the_screen() -> None:
    screened = _screen(_mixed(), _single())

    assert [invoice.invoice_number for invoice in screened.recargo_unattributable] == ["RECARGO-MIXED"]


def test_a_recargo_over_one_rate_is_attributed_and_not_reported() -> None:
    """The single-rate case keeps its attribution, so the advisory cannot fire on every recargo."""
    screened = _screen(_single())

    assert screened.recargo_unattributable == ()
    assert any(observation.recargo_amount == Decimal("52.00") for observation in screened.observations)


def test_the_advisory_names_the_invoice_and_what_was_not_compared() -> None:
    mixed = _mixed()
    (diagnostic,) = recargo_unattributable_diagnostics((mixed,), resolver_id="test-resolver")

    assert diagnostic.reason == "invoice_recargo_not_attributable_to_a_tier"
    assert diagnostic.source_ref == f"invoice:{mixed.invoice_id}"
    assert "RECARGO-MIXED" in diagnostic.message
    assert "59.00" in diagnostic.message
    assert "not compared" in diagnostic.message
    assert diagnostic.remedy is not None
