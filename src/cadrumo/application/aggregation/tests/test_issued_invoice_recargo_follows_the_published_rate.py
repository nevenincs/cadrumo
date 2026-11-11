"""An issued invoice's recargo de equivalencia at one IVA rate must be base x the art. 161 rate.

The filer of an issued invoice charges the recargo and declares it on the Modelo
303 recargo casillas, so the figure is a charged cuota the law fixes (LIVA arts.
160 and 161). Within a cent the recorded figure is the invoice's own rounding
and is declared; beyond it, or at the labores del tabaco rate no casilla is
bound for, the invoice blocks the period with a door back to it. A received
invoice's recargo reaches no casilla and is never refused. Expected figures are
worked by hand: 1000.00 at 5.2 % is 52.00, and the tobacco rate of 1.75 % gives
17.50.

Real-behaviour: real invoices through the real screen and period side over the
published authority. No mocks, stubs, skips or xfail.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.invoices.enums import PaymentStatus, resolve_iva_rate_token
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind
from ....domain.transactions.models import TransactionCatalogue
from ...ledger.preflight import HeldTransactionCatalogue, LedgerPreflightIssueReason
from ..invoice_iva_source import InvoiceIvaFinding, InvoiceIvaFindingReason, period_invoice_iva_side
from ..modelo_bindings_invoice_iva import (
    ScreenedInvoiceIva,
    modelo_bindings_invoice_iva_recargo_rate_divergence,
    screened_invoice_iva_observations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "32323232-3232-4232-8232-323232323232"
_YEARS = tuple(filing_year_envelope().years)


def _issued_on(year: int) -> date:
    return date(year, 5, 12)


def _invoice(year: int, *, recargo: str, kind: InvoiceKind = InvoiceKind.ISSUED) -> Invoice:
    on = _issued_on(year)
    line = InvoiceLine(
        description="General",
        quantity=Decimal("1"),
        unit_price=Decimal("1000.00"),
        subtotal=Decimal("1000.00"),
        iva_rate=resolve_iva_rate_token("RATE_21", on),
        iva_amount=Decimal("210.00"),
    )
    return Invoice.model_validate(
        {
            "bucket_id": _BUCKET_ID,
            "kind": kind,
            "invoice_number": f"RECARGO-{kind.value}-{recargo}",
            "issued_at": on,
            "counterparty_name": "Minorista Recargo SL",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "base_total": line.subtotal,
            "iva_total": line.iva_amount,
            "recargo_amount": Decimal(recargo),
            "grand_total": line.subtotal + line.iva_amount + Decimal(recargo),
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
        },
    )


def _period(year: int) -> Period:
    return Period.from_year_and_code(year, "2T")


def _screen(invoice: Invoice, year: int) -> ScreenedInvoiceIva:
    with bundled_indexed_authority().operation() as operation:
        return screened_invoice_iva_observations(
            (invoice,),
            bucket_id=_BUCKET_ID,
            period=_period(year),
            linked_movements={},
            operation=operation,
        )


@pytest.mark.parametrize("year", _YEARS)
@pytest.mark.parametrize("recargo", ["52.00", "52.01", "51.99"])
def test_a_recargo_within_a_cent_of_the_published_rate_is_declared_as_recorded(year: int, recargo: str) -> None:
    invoice = _invoice(year, recargo=recargo)

    screened = _screen(invoice, year)

    assert screened.recargo_not_declarable == ()
    assert {observation.recargo_amount for observation in screened.observations} == {Decimal(recargo)}


@pytest.mark.parametrize("year", _YEARS)
@pytest.mark.parametrize(
    "recargo",
    [
        # One hundredth beyond the cent, on both sides of 52.00.
        "52.02",
        "51.98",
        # The reduced-rate recargo on a general-rate sale.
        "14.00",
        # The labores del tabaco rate, whose casilla rung is not bound.
        "17.50",
    ],
)
def test_a_recargo_off_the_published_rate_is_named(year: int, recargo: str) -> None:
    invoice = _invoice(year, recargo=recargo)

    assert _screen(invoice, year).recargo_not_declarable == (invoice,)


@pytest.mark.parametrize("year", _YEARS)
def test_a_received_invoice_keeps_the_recargo_its_supplier_charged(year: int) -> None:
    assert _screen(_invoice(year, recargo="14.00", kind=InvoiceKind.RECEIVED), year).recargo_not_declarable == ()


@pytest.mark.parametrize("year", _YEARS)
def test_an_issued_invoice_raises_the_refusal_and_not_the_advisory(year: int) -> None:
    """The advisory that leaves the figure standing speaks for received invoices only."""
    with bundled_indexed_authority().operation() as operation:
        divergence = modelo_bindings_invoice_iva_recargo_rate_divergence(
            _invoice(year, recargo="14.00"), devengo_date=_issued_on(year), operation=operation
        )
    assert divergence is None


@pytest.mark.parametrize("year", _YEARS)
def test_the_refusal_blocks_the_period_with_a_door_to_the_invoice(year: int) -> None:
    invoice = _invoice(year, recargo="14.00")
    window = TransactionCatalogue.from_transactions(())

    with bundled_indexed_authority().operation() as operation:
        side = period_invoice_iva_side(
            (invoice,),
            bucket_id=_BUCKET_ID,
            period=_period(year),
            window=window,
            repository=HeldTransactionCatalogue(window),
            operation=operation,
        )

    assert side.source.findings == (
        InvoiceIvaFinding(reason=InvoiceIvaFindingReason.RECARGO_NOT_DECLARABLE, invoice_id=invoice.invoice_id),
    )


def test_the_ledger_reports_the_reason_calculation_refuses() -> None:
    assert (
        LedgerPreflightIssueReason.INVOICE_RECARGO_NOT_DECLARABLE.value
        == InvoiceIvaFindingReason.RECARGO_NOT_DECLARABLE.value
    )
