"""A factura rectificativa is a modification of bases and cuotas, never a new operation.

An invoice states magnitudes: its totals cannot be negative, and a rectificativa
carries no direction of its own. Projected through the rate rows like an
ordinaria, an issued abono of 1000.00 at 21 % would raise the repercutido of
Modelo 303 casillas 07-09 by 1000.00 and 210.00 instead of reducing it, and a
received one would raise the deducible of casillas 28/29. The AEAT Modelo 303
instructions place the correction elsewhere: casillas 14 and 15 carry the
"Modificación de bases y cuotas" with the sign that corresponds (LIVA art. 80,
art. 89 and RD 1619/2012 art. 15), and casillas 40 and 41 the "Rectificación de
deducciones". Both are operator-entered, so the screen declares the
rectificativa on no rate row and blocks the period until the operator states
the modification there.

Real-behaviour: real invoices through the real screen and period side over the
published authority. No mocks, stubs, skips or xfail.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.invoice_legal_classification import invoice_class_rectificativa
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.invoices.enums import PaymentStatus, RectificationFact, resolve_iva_rate_token
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind
from ....domain.transactions.models import TransactionCatalogue
from ...ledger.preflight import HeldTransactionCatalogue, LedgerPreflightIssueReason
from ..invoice_iva_source import InvoiceIvaFinding, InvoiceIvaFindingReason, period_invoice_iva_side
from ..iva_ledger_apportionment import resolve_iva_ledger_binding_values
from ..modelo_bindings_invoice_iva import ScreenedInvoiceIva, screened_invoice_iva_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "41414141-4141-4141-8141-414141414141"
_YEARS = tuple(filing_year_envelope().years)
_BASE = Decimal("1000.00")
_CUOTA = Decimal("210.00")


def _issued_on(year: int) -> date:
    return date(year, 5, 12)


def _invoice(year: int, *, kind: InvoiceKind, rectificativa: bool) -> Invoice:
    on = _issued_on(year)
    line = InvoiceLine(
        description="Abono por devolución" if rectificativa else "Servicio",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=resolve_iva_rate_token("RATE_21", on),
        iva_amount=_CUOTA,
    )
    correction: dict[str, object] = (
        {
            "invoice_class": invoice_class_rectificativa(effective_date=on),
            "series": "R",
            "rectifies_invoice_number": "F-0001",
        }
        if rectificativa
        else {}
    )
    return Invoice.model_validate(
        {
            "bucket_id": _BUCKET_ID,
            "kind": kind,
            "invoice_number": f"{'R' if rectificativa else 'F'}-{kind.value}-0002",
            "issued_at": on,
            "counterparty_name": "Cliente Nacional SL",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "base_total": line.subtotal,
            "iva_total": line.iva_amount,
            "grand_total": line.subtotal + line.iva_amount,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            **correction,
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


def _declared_values(screen: ScreenedInvoiceIva, year: int) -> dict[str, Decimal]:
    """The Modelo 303 binding values the screen's observations resolve to, zeros dropped."""
    revision = published_snapshot("303", filing_year=year, period="2T").revision
    with bundled_indexed_authority().operation() as operation:
        resolved = resolve_iva_ledger_binding_values(revision, screen.observations, operation=operation)
    return {str(key): value for key, value in resolved.items() if value}


@pytest.mark.parametrize("year", _YEARS)
@pytest.mark.parametrize("kind", [InvoiceKind.ISSUED, InvoiceKind.RECEIVED])
def test_a_rectificativa_contributes_to_no_rate_row(year: int, kind: InvoiceKind) -> None:
    invoice = _invoice(year, kind=kind, rectificativa=True)

    screened = _screen(invoice, year)

    assert screened.observations == (), f"a rectificativa reached the rate rows: {_declared_values(screened, year)!r}"
    assert screened.invoice_ids == ()
    assert [screened_rectificativa.invoice for screened_rectificativa in screened.rectificativas] == [invoice]


@pytest.mark.parametrize("year", _YEARS)
@pytest.mark.parametrize("kind", [InvoiceKind.ISSUED, InvoiceKind.RECEIVED])
def test_an_ordinaria_still_declares_its_base_and_cuota(year: int, kind: InvoiceKind) -> None:
    """The control: the same figures as an ordinaria keep reaching the rate rows unchanged."""
    invoice = _invoice(year, kind=kind, rectificativa=False)

    screened = _screen(invoice, year)

    assert screened.rectificativas == ()
    assert screened.invoice_ids == (invoice.invoice_id,)
    assert [(observation.base_amount, observation.iva_amount) for observation in screened.observations] == [
        (_BASE, _CUOTA)
    ]
    declared = set(_declared_values(screened, year).values())
    assert {_BASE, _CUOTA} <= declared


@pytest.mark.parametrize("year", _YEARS)
@pytest.mark.parametrize("kind", [InvoiceKind.ISSUED, InvoiceKind.RECEIVED])
def test_a_rectificativa_blocks_the_period_with_a_door_to_the_invoice(year: int, kind: InvoiceKind) -> None:
    invoice = _invoice(year, kind=kind, rectificativa=True)
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

    assert side.source.observations == ()
    assert side.source.findings == (
        InvoiceIvaFinding(
            reason=InvoiceIvaFindingReason.RECTIFICATIVA_MODIFICATION_UNMODELLED,
            invoice_id=invoice.invoice_id,
            missing_rectification_facts=_EXPECTED_MISSING_FACTS[kind],
        ),
    )


#: What a rectificativa stating none of its facts is missing, per side. The two
#: lists differ by exactly the reception date, which LIVA art. 114.Dos makes the
#: recipient's period and which an issued document never states. Enumerated here
#: rather than read back from the production helper, so a change to the per-side
#: fact set has to be stated twice before this passes.
_EXPECTED_MISSING_FACTS = {
    InvoiceKind.ISSUED: (
        RectificationFact.RECTIFICATION_METHOD,
        RectificationFact.RECTIFICATION_CAUSE,
        RectificationFact.RECTIFICATION_DIRECTION,
    ),
    InvoiceKind.RECEIVED: (
        RectificationFact.RECTIFICATION_METHOD,
        RectificationFact.RECTIFICATION_CAUSE,
        RectificationFact.RECTIFICATION_DIRECTION,
        RectificationFact.DOCUMENT_RECEIVED_ON,
    ),
}


def test_the_ledger_reports_the_reason_calculation_refuses() -> None:
    assert (
        LedgerPreflightIssueReason.INVOICE_RECTIFICATIVA_MODIFICATION_UNMODELLED.value
        == InvoiceIvaFindingReason.RECTIFICATIVA_MODIFICATION_UNMODELLED.value
    )
