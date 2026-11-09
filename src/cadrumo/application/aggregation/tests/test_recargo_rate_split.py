"""An issued invoice's one recargo over several IVA rates is declared rate by rate.

The recargo de equivalencia is recorded once per invoice while the Modelo 303
recargo casillas are per IVA rate. LIVA art. 161 fixes the recargo rate that
goes with each IVA rate, so the part of the recargo that belongs to each rate is
its base times that published rate. When those parts add up to the recorded
recargo, each part is declared under its rate. When they do not, no figure the
invoice records says how the recargo divides, so the issued invoice blocks the
period rather than the 303 declaring it without that recargo. A received
invoice's recargo reaches no Modelo 303 casilla, so it never blocks.

The screen runs for real here, over the published authority and real invoices.
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
from ....domain.transactions.models import TransactionCatalogue
from ...ledger.preflight import HeldTransactionCatalogue
from ..invoice_iva_source import InvoiceIvaFinding, InvoiceIvaFindingReason, period_invoice_iva_side
from ..modelo_bindings_invoice_iva import ScreenedInvoiceIva, screened_invoice_iva_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "30303030-3030-4030-8030-303030303030"
_PERIOD = Period.from_year_and_code(2026, "2T")
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


def _invoice(
    number: str,
    lines: tuple[InvoiceLine, ...],
    *,
    recargo: str,
    kind: InvoiceKind = InvoiceKind.ISSUED,
) -> Invoice:
    base = sum((line.subtotal for line in lines), Decimal("0"))
    cuota = sum((line.iva_amount for line in lines), Decimal("0"))
    return Invoice.model_validate(
        {
            "bucket_id": _BUCKET_ID,
            "kind": kind,
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


def _mixed(*, recargo: str, kind: InvoiceKind = InvoiceKind.ISSUED) -> Invoice:
    """1000.00 at 21% and 500.00 at 10%: art. 161 gives 5.2% and 1.4%, so 52.00 + 7.00."""
    return _invoice(
        f"RECARGO-MIXED-{recargo}",
        (_line("General", "1000.00", "RATE_21", "210.00"), _line("Reducido", "500.00", "RATE_10", "50.00")),
        recargo=recargo,
        kind=kind,
    )


def _single() -> Invoice:
    return _invoice("RECARGO-SINGLE", (_line("General", "1000.00", "RATE_21", "210.00"),), recargo="52.00")


def _screen(*invoices: Invoice) -> ScreenedInvoiceIva:
    with bundled_indexed_authority().operation() as operation:
        return screened_invoice_iva_observations(
            invoices,
            bucket_id=_BUCKET_ID,
            period=_PERIOD,
            linked_movements={},
            operation=operation,
        )


def _recargo_by_line(screened: ScreenedInvoiceIva) -> dict[str, Decimal]:
    return {observation.ledger_id: observation.recargo_amount for observation in screened.observations}


def test_a_recargo_whose_rate_parts_add_up_is_declared_under_each_rate() -> None:
    invoice = _mixed(recargo="59.00")

    screened = _screen(invoice)

    assert _recargo_by_line(screened) == {
        f"invoice:{invoice.invoice_id}:0": Decimal("52.00"),
        f"invoice:{invoice.invoice_id}:1": Decimal("7.00"),
    }
    assert screened.recargo_split_unresolved == ()


def test_a_recargo_the_published_rates_do_not_produce_is_declared_nowhere_and_named() -> None:
    """60.00 is not 52.00 + 7.00, and no recorded figure says which rate holds the extra euro."""
    invoice = _mixed(recargo="60.00")

    screened = _screen(invoice)

    assert set(_recargo_by_line(screened).values()) == {Decimal("0")}
    assert screened.recargo_split_unresolved == (invoice,)


def test_a_received_invoice_recargo_is_never_named() -> None:
    """No Modelo 303 casilla declares a recargo the filer bore, so it cannot block the period."""
    screened = _screen(_mixed(recargo="60.00", kind=InvoiceKind.RECEIVED))

    assert screened.recargo_split_unresolved == ()


def test_a_recargo_over_one_rate_is_declared_as_recorded() -> None:
    """One rate names its casilla, so the recorded figure stands; the rate advisory cross-checks it."""
    invoice = _single()

    screened = _screen(invoice)

    assert _recargo_by_line(screened) == {f"invoice:{invoice.invoice_id}:0": Decimal("52.00")}
    assert screened.recargo_split_unresolved == ()


def test_the_unresolved_split_blocks_the_period_with_a_door_to_the_invoice() -> None:
    invoice = _mixed(recargo="60.00")
    window = TransactionCatalogue.from_transactions(())

    with bundled_indexed_authority().operation() as operation:
        side = period_invoice_iva_side(
            (invoice,),
            bucket_id=_BUCKET_ID,
            period=_PERIOD,
            window=window,
            repository=HeldTransactionCatalogue(window),
            operation=operation,
        )

    assert side.source.findings == (
        InvoiceIvaFinding(reason=InvoiceIvaFindingReason.RECARGO_SPLIT_UNRESOLVED, invoice_id=invoice.invoice_id),
    )
