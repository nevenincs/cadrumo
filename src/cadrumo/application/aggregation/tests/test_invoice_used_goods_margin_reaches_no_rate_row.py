"""A sale under the régimen especial de los bienes usados is taxed on its margin, not its lines.

LIVA art. 135.Dos lets a sujeto pasivo revendedor apply the régimen especial de
los bienes usados, objetos de arte, antigüedades y objetos de colección
operation by operation, so the invoice's IVA category marks it. Art. 137 makes
the taxable base the margin de beneficio of each operation, IVA included, and
art. 138 forbids stating the cuota on the invoice. An issued REBU invoice
therefore carries neither the base nor the cuota the return declares: entered
with no cuota it used to reach no casilla, or a domestic exempt row, while the
real liability on the margin was missing. The screen now declares it on no rate
row and blocks the period until the operator enters the margin base and its
cuota. A received REBU invoice carries no deductible cuota (art. 138, second
paragraph), so it declares nothing and finds nothing.

Real-behaviour: real invoices through the real screen and period side over the
published authority, for every year of the registry envelope. No mocks, stubs,
skips or xfail.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.iva_category_catalogue import resolve_iva_category_catalogue
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.invoices.enums import PaymentStatus, resolve_iva_rate_token
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind, IvaCategory
from ....domain.transactions.models import TransactionCatalogue
from ...invoices.catalogue_add_operation import declared_invoice_category
from ...ledger.preflight import HeldTransactionCatalogue, LedgerPreflightIssueReason
from ...state_projection_models import OPERATOR_ACTION_BY_MODELO_READINESS_LEDGER_ISSUE, OperatorActionAxis
from ..invoice_iva_source import InvoiceIvaFinding, InvoiceIvaFindingReason, period_invoice_iva_side
from ..iva_ledger_apportionment import resolve_iva_ledger_binding_values
from ..modelo_bindings_invoice_iva import ScreenedInvoiceIva, screened_invoice_iva_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "42424242-4242-4242-8242-424242424242"
_YEARS = tuple(filing_year_envelope().years)
_REBU = "special_regime_used_goods"
_PRICE = Decimal("1500.00")
_BASE = Decimal("1000.00")
_CUOTA = Decimal("210.00")


def _issued_on(year: int) -> date:
    return date(year, 5, 12)


def _rebu_invoice(year: int, *, kind: InvoiceKind) -> Invoice:
    """A REBU invoice as art. 138 requires it: the total price and no separate cuota."""
    on = _issued_on(year)
    line = InvoiceLine(
        description="Vehículo usado",
        quantity=Decimal("1"),
        unit_price=_PRICE,
        subtotal=_PRICE,
        iva_rate=resolve_iva_rate_token("RATE_0", on),
        iva_amount=Decimal("0"),
    )
    return _invoice(on, kind=kind, line=line, number=f"REBU-{kind.value}-0001", iva_category=IvaCategory(_REBU))


def _ordinary_invoice(year: int, *, kind: InvoiceKind) -> Invoice:
    on = _issued_on(year)
    line = InvoiceLine(
        description="Servicio",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=resolve_iva_rate_token("RATE_21", on),
        iva_amount=_CUOTA,
    )
    return _invoice(on, kind=kind, line=line, number=f"F-{kind.value}-0001", iva_category=None)


def _invoice(
    on: date,
    *,
    kind: InvoiceKind,
    line: InvoiceLine,
    number: str,
    iva_category: IvaCategory | None,
) -> Invoice:
    return Invoice.model_validate(
        {
            "bucket_id": _BUCKET_ID,
            "kind": kind,
            "invoice_number": number,
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
            "iva_category": iva_category,
        },
    )


def _period(year: int) -> Period:
    return Period.from_year_and_code(year, "2T")


def _screen(invoices: tuple[Invoice, ...], year: int) -> ScreenedInvoiceIva:
    with bundled_indexed_authority().operation() as operation:
        return screened_invoice_iva_observations(
            invoices,
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


def _findings(invoices: tuple[Invoice, ...], year: int) -> tuple[tuple[InvoiceIvaFinding, ...], int]:
    window = TransactionCatalogue.from_transactions(())
    with bundled_indexed_authority().operation() as operation:
        side = period_invoice_iva_side(
            invoices,
            bucket_id=_BUCKET_ID,
            period=_period(year),
            window=window,
            repository=HeldTransactionCatalogue(window),
            operation=operation,
        )
    return side.source.findings, len(side.source.observations)


@pytest.mark.parametrize("year", _YEARS)
def test_an_issued_rebu_sale_reaches_no_rate_row_and_blocks_the_period(year: int) -> None:
    invoice = _rebu_invoice(year, kind=InvoiceKind.ISSUED)

    screened = _screen((invoice,), year)

    assert screened.observations == (), f"a REBU sale reached the rate rows: {_declared_values(screened, year)!r}"
    assert screened.invoice_ids == ()
    assert screened.used_goods_margin_unmodelled == (invoice,)
    findings, observations = _findings((invoice,), year)
    assert observations == 0
    assert findings == (
        InvoiceIvaFinding(reason=InvoiceIvaFindingReason.USED_GOODS_MARGIN_UNMODELLED, invoice_id=invoice.invoice_id),
    )


@pytest.mark.parametrize("year", _YEARS)
def test_a_received_rebu_purchase_deducts_nothing_and_finds_nothing(year: int) -> None:
    invoice = _rebu_invoice(year, kind=InvoiceKind.RECEIVED)

    screened = _screen((invoice,), year)

    assert screened.observations == ()
    assert screened.used_goods_margin_unmodelled == ()
    assert screened.deduction_authority_missing == ()
    assert _findings((invoice,), year) == ((), 0)


@pytest.mark.parametrize("year", _YEARS)
@pytest.mark.parametrize("kind", [InvoiceKind.ISSUED, InvoiceKind.RECEIVED])
def test_an_ordinary_invoice_beside_a_rebu_one_still_declares_its_base_and_cuota(year: int, kind: InvoiceKind) -> None:
    """The control: an ordinaria in the same period keeps reaching its rate rows unchanged."""
    ordinary = _ordinary_invoice(year, kind=kind)
    rebu = _rebu_invoice(year, kind=kind)

    screened = _screen((ordinary, rebu), year)

    assert screened.invoice_ids == (ordinary.invoice_id,)
    assert [(observation.base_amount, observation.iva_amount) for observation in screened.observations] == [
        (_BASE, _CUOTA)
    ]
    assert {_BASE, _CUOTA} <= set(_declared_values(screened, year).values())
    expected_blocked = (rebu,) if kind is InvoiceKind.ISSUED else ()
    assert screened.used_goods_margin_unmodelled == expected_blocked


@pytest.mark.parametrize("year", _YEARS)
def test_the_add_and_bulk_import_reader_admits_the_rebu_category(year: int) -> None:
    on = _issued_on(year)
    with bundled_indexed_authority().operation() as operation:
        admitted = declared_invoice_category(_REBU, effective_date=on, authority_operation=operation)
        catalogue = resolve_iva_category_catalogue(effective_date=on, authority=operation)

    assert admitted == IvaCategory(_REBU)
    assert admitted in catalogue.projection("margin_taxable_base")
    assert admitted in catalogue.projection("m303_base_out_of_scope")


def test_the_ledger_reports_the_reason_calculation_refuses() -> None:
    reason = LedgerPreflightIssueReason.INVOICE_USED_GOODS_MARGIN_UNMODELLED

    assert reason.value == InvoiceIvaFindingReason.USED_GOODS_MARGIN_UNMODELLED.value
    assert OPERATOR_ACTION_BY_MODELO_READINESS_LEDGER_ISSUE[reason] is OperatorActionAxis.SUPPLY_MANUAL_INPUT
