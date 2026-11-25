"""A factura rectificativa corrects the accrued income of the invoice it names.

An invoice stores every total as a non-negative magnitude, with the direction in its
class, so the income projection has to apply the class. Worked by hand:

- F1: 1.000,00 base + 210,00 IVA, no retencion = 1.210,00 banked.
- R1: 200,00 base + 42,00 IVA = 242,00 refunded, naming F1.
- Under accrual the year holds 1.000,00 - 200,00 = 800,00, whether or not R1's refund is linked.

No source in the corpus says which year a correction reduces when it comes after the year
of its invoice, so that case refuses rather than choosing a year.

Nor does one say what is left of the credit when the invoice corrected states a retencion,
so that refuses too rather than reducing it in proportion or leaving it whole.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.invoice_legal_classification import invoice_class_rectificativa
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind, IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...actividad_asset.tests.register_support import MemoryRepository
from ..modelo_bindings import LedgerRentaIncomeAggregationSourceResolver
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution
from .ledger_source_mesh_support import BUCKET_ID, InMemoryTransactionCatalogueRepository
from .renta_income_aggregation_support import catalogue_read_ports
from .test_renta_imputation_criterion import (
    CASH,
    DEVENGO,
    EARLIER,
    INCOME_0171,
    INCOME_M130_01,
    LATER,
    ZERO,
    declared,
    issued,
    paid_invoice,
    renta_imputation_criterion_profile,
    renta_imputation_criterion_receipt,
    unresolved_bindings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_F1_DATE = date(LATER, 2, 1)
_R1_DATE = date(LATER, 5, 1)
_NETTED = Decimal("800.00")


def _rectificativa(
    on: date,
    *,
    rectifies: str | None = "F-1",
    base: Decimal = Decimal("200.00"),
    linked: tuple[str, ...] = (),
    retention: Decimal | None = None,
    number: str = "R-1",
) -> Invoice:
    iva = (base * Decimal("0.21")).quantize(Decimal("0.01"))
    line = InvoiceLine(
        description="Abono parcial",
        quantity=Decimal("1"),
        unit_price=base,
        subtotal=base,
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=iva,
    )
    stated_retention: dict[str, object] = (
        {} if retention is None else {"retention_rate": Decimal("0.15"), "retention_amount": retention}
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_class": invoice_class_rectificativa(),
            "series": "R",
            "rectifies_invoice_number": rectifies,
            "invoice_number": number,
            "issued_at": on,
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "bucket_id": BUCKET_ID,
            "base_total": base,
            "iva_total": iva,
            "grand_total": base + iva,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID if linked else PaymentStatus.PENDING,
            "iva_category": IvaCategory("domestic_general"),
            "linked_transaction_ids": linked,
            **stated_retention,
        },
    )


def renta_rectificativa_income_refund(
    on: date, *, invoice_id: str | None = None, amount: Decimal = Decimal("242.00")
) -> Transaction:
    """Return the outgoing bank row that gives a customer its money back."""
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=f"abono-{on.isoformat()}",
                booked_date=on,
                value_date=on,
                amount=amount,
                currency="EUR",
                counterparty="Cliente SL",
                description="abono factura",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="d" * 64,
                    source_row_index=2,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(LATER, 2, 1, 12, 0, tzinfo=UTC),
                    provider_name="CSV provider",
                ),
                raw_fields={},
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(LATER, 2, 1, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
            "invoice_id": invoice_id,
        },
    )


def resolve(
    operation: PinnedAuthorityOperation,
    criteria: tuple[tuple[int, str], ...],
    *,
    rows: tuple[Transaction, ...] = (),
    invoices: tuple[Invoice, ...] = (),
    year: int = LATER,
    modelo: str = "100",
    period: str = "0A",
) -> CalculationSourceResolution:
    transactions = TransactionCatalogue.from_transactions(rows)
    repository = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    repository.save(transactions)
    resolver = LedgerRentaIncomeAggregationSourceResolver(
        activity_asset_history_repository=MemoryRepository(),
        transaction_repository=repository,
        ports=catalogue_read_ports(invoices=build_invoice_catalogue(invoices), transactions=transactions),
    )
    return resolver.resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo=modelo,
            filing_year=year,
            period=Period.from_year_and_code(year, period),
            revision=published_snapshot(modelo, filing_year=year, period=period).revision,
            profile=renta_imputation_criterion_profile(operation, declared(*criteria)),
        ),
    )


_ACCRUAL_YEAR = ((LATER, DEVENGO),)


def _unretained(invoice: Invoice) -> Invoice:
    """Return the invoice with no retencion, because a correction of one that has it refuses."""
    return Invoice.model_validate(
        {**invoice.model_dump(exclude={"invoice_id"}), "retention_rate": None, "retention_amount": None}
    )


def _paid_unretained() -> tuple[Transaction, Invoice]:
    """Return F1 with no retencion, 1.210,00 banked, and the receipt that collects it."""
    amount = Decimal("1210.00")
    invoice = _unretained(
        issued(_F1_DATE, linked=(renta_imputation_criterion_receipt(_F1_DATE, amount=amount).transaction_id,))
    )
    return renta_imputation_criterion_receipt(_F1_DATE, invoice_id=invoice.invoice_id, amount=amount), invoice


def _blocked_because(resolution: CalculationSourceResolution, token: str) -> bool:
    return any(
        item.binding_id == INCOME_0171 and item.reason == "unresolved_binding" and token in item.message
        for item in resolution.diagnostics
    )


def test_an_unlinked_rectificativa_reduces_the_income_of_its_year(operation: PinnedAuthorityOperation) -> None:
    row, first = _paid_unretained()
    resolution = resolve(operation, _ACCRUAL_YEAR, rows=(row,), invoices=(first, _rectificativa(_R1_DATE)))
    assert resolution.binding_values[INCOME_0171] == _NETTED
    assert INCOME_0171 not in unresolved_bindings(resolution)


def test_a_rectificativa_with_its_refund_linked_still_reduces_the_income(operation: PinnedAuthorityOperation) -> None:
    row, first = _paid_unretained()
    unlinked = renta_rectificativa_income_refund(_R1_DATE)
    corrected = _rectificativa(_R1_DATE, linked=(unlinked.transaction_id,))
    refund = renta_rectificativa_income_refund(_R1_DATE, invoice_id=corrected.invoice_id)
    resolution = resolve(operation, _ACCRUAL_YEAR, rows=(row, refund), invoices=(first, corrected))
    assert resolution.binding_values[INCOME_0171] == _NETTED
    assert INCOME_0171 not in unresolved_bindings(resolution)


def test_a_rectificativa_reduces_an_unpaid_invoice_too(operation: PinnedAuthorityOperation) -> None:
    resolution = resolve(operation, _ACCRUAL_YEAR, invoices=(_unretained(issued(_F1_DATE)), _rectificativa(_R1_DATE)))
    assert resolution.binding_values[INCOME_0171] == _NETTED


@pytest.mark.parametrize(("period", "expected"), [("1T", Decimal("1000.00")), ("2T", _NETTED), ("3T", _NETTED)])
def test_the_instalment_nets_from_the_quarter_the_correction_accrues(
    operation: PinnedAuthorityOperation, period: str, expected: Decimal
) -> None:
    """F1 accrues in February and R1 in May, so only the cumulative windows reaching May net it."""
    row, first = _paid_unretained()
    resolution = resolve(
        operation,
        _ACCRUAL_YEAR,
        rows=(row,),
        invoices=(first, _rectificativa(_R1_DATE)),
        modelo="130",
        period=period,
    )
    assert resolution.binding_values[INCOME_M130_01] == expected


def test_two_rectificativas_of_one_invoice_both_reduce_it(operation: PinnedAuthorityOperation) -> None:
    """1.000,00 - 200,00 - 100,00 = 700,00."""
    row, first = _paid_unretained()
    second = _rectificativa(date(LATER, 6, 1), base=Decimal("100.00"), number="R-2")
    resolution = resolve(operation, _ACCRUAL_YEAR, rows=(row,), invoices=(first, _rectificativa(_R1_DATE), second))
    assert resolution.binding_values[INCOME_0171] == Decimal("700.00")


def test_a_correction_in_a_later_year_refuses_rather_than_choosing_a_year(operation: PinnedAuthorityOperation) -> None:
    """F1 stays 1.000,00 in its own year; the later year takes no -200,00 and says so."""
    row, first = paid_invoice(date(EARLIER, 11, 1), date(EARLIER, 11, 1))
    criteria = ((EARLIER, DEVENGO), (LATER, DEVENGO))
    invoices = (first, _rectificativa(_R1_DATE))
    earlier = resolve(operation, criteria, rows=(row,), invoices=invoices, year=EARLIER)
    later = resolve(operation, criteria, rows=(row,), invoices=invoices, year=LATER)
    assert earlier.binding_values[INCOME_0171] == Decimal("1000.00")
    assert INCOME_0171 not in unresolved_bindings(earlier)
    assert later.binding_values[INCOME_0171] == ZERO
    assert _blocked_because(later, "rectificativa_across_years")


def test_a_correction_whose_invoice_is_not_recorded_refuses(operation: PinnedAuthorityOperation) -> None:
    resolution = resolve(operation, _ACCRUAL_YEAR, invoices=(_rectificativa(_R1_DATE, rectifies="F-404"),))
    assert resolution.binding_values[INCOME_0171] == ZERO
    assert _blocked_because(resolution, "rectificativa_target_unknown")


def test_a_correction_above_its_invoice_refuses(operation: PinnedAuthorityOperation) -> None:
    """A figure larger than the original cannot be a reduction of it, and may be a replacement."""
    row, first = _paid_unretained()
    excessive = _rectificativa(_R1_DATE, base=Decimal("1200.00"))
    resolution = resolve(operation, _ACCRUAL_YEAR, rows=(row,), invoices=(first, excessive))
    assert resolution.binding_values[INCOME_0171] == Decimal("1000.00")
    assert _blocked_because(resolution, "rectificativa_above_invoice")


def test_two_corrections_adding_up_above_their_invoice_refuse(operation: PinnedAuthorityOperation) -> None:
    row, first = _paid_unretained()
    second = _rectificativa(date(LATER, 6, 1), base=Decimal("900.00"), number="R-2")
    resolution = resolve(operation, _ACCRUAL_YEAR, rows=(row,), invoices=(first, _rectificativa(_R1_DATE), second))
    assert resolution.binding_values[INCOME_0171] == Decimal("1000.00")
    assert _blocked_because(resolution, "rectificativa_above_invoice")


def test_a_correction_stating_a_retencion_refuses(operation: PinnedAuthorityOperation) -> None:
    """Nothing settles what a stated retencion on a correction does to the credit, so no figure is chosen."""
    row, first = paid_invoice(_F1_DATE, _F1_DATE)
    withheld = _rectificativa(_R1_DATE, retention=Decimal("30.00"))
    resolution = resolve(operation, _ACCRUAL_YEAR, rows=(row,), invoices=(first, withheld))
    assert _blocked_because(resolution, "rectificativa_retencion_stated")


def test_a_receipt_linked_to_a_rectificativa_refuses_under_accrual(operation: PinnedAuthorityOperation) -> None:
    """Money coming in on a correction contradicts a reduction, so the year blocks and the receipt adds nothing.

    F1 1000 less R1 200 is 800; the receipt of R1 stays out of the income it could not be read into.
    """
    row, first = _paid_unretained()
    unlinked = renta_imputation_criterion_receipt(_R1_DATE, amount=Decimal("242.00"))
    corrected = _rectificativa(_R1_DATE, linked=(unlinked.transaction_id,))
    inbound = renta_imputation_criterion_receipt(_R1_DATE, invoice_id=corrected.invoice_id, amount=Decimal("242.00"))
    resolution = resolve(operation, _ACCRUAL_YEAR, rows=(row, inbound), invoices=(first, corrected))
    assert resolution.binding_values[INCOME_0171] == Decimal("800.00")
    assert _blocked_because(resolution, "rectificativa_with_receipt")


def test_the_netted_reading_is_named_for_the_operator(operation: PinnedAuthorityOperation) -> None:
    """RD 1619/2012 art. 15.5 lets a rectificativa state the correction or the result, and the record does not say."""
    row, first = _paid_unretained()
    resolution = resolve(operation, _ACCRUAL_YEAR, rows=(row,), invoices=(first, _rectificativa(_R1_DATE)))
    (advisory,) = [item for item in resolution.diagnostics if item.source_ref == "renta-rectificativa:netted"]
    assert advisory.reason == "unsettled_legal_reading"
    assert "R-1" in advisory.message
    assert "200.00" in advisory.message


def test_a_rectificativa_does_not_touch_a_year_under_cash(operation: PinnedAuthorityOperation) -> None:
    """Under cash nothing accrues, so its unpaid correction moves nothing and raises nothing."""
    row, first = paid_invoice(_F1_DATE, _F1_DATE)
    resolution = resolve(operation, ((LATER, CASH),), rows=(row,), invoices=(first, _rectificativa(_R1_DATE)))
    assert resolution.binding_values[INCOME_0171] == Decimal("1000.00")


def _refunded_correction() -> tuple[Transaction, Invoice]:
    unlinked = renta_rectificativa_income_refund(_R1_DATE)
    corrected = _rectificativa(_R1_DATE, linked=(unlinked.transaction_id,))
    return renta_rectificativa_income_refund(_R1_DATE, invoice_id=corrected.invoice_id), corrected


def test_a_refund_on_a_correction_under_cash_refuses_in_the_year_it_was_paid(
    operation: PinnedAuthorityOperation,
) -> None:
    """RIRPF art. 7.2 and the manual place cobros and pagos; none says a refund nets against income."""
    row, first = paid_invoice(_F1_DATE, _F1_DATE)
    refund, corrected = _refunded_correction()
    resolution = resolve(operation, ((LATER, CASH),), rows=(row, refund), invoices=(first, corrected))
    assert resolution.binding_values[INCOME_0171] == Decimal("1000.00")
    assert _blocked_because(resolution, "rectificativa_refund_under_cash")


def test_a_cash_year_without_the_refund_is_not_blocked_by_it(operation: PinnedAuthorityOperation) -> None:
    """The refund was paid in the later year, so the earlier year's 1.000,00 stands unblocked."""
    on = date(EARLIER, 2, 1)
    row, first = paid_invoice(on, on)
    refund, corrected = _refunded_correction()
    criteria = ((EARLIER, CASH), (LATER, CASH))
    earlier = resolve(operation, criteria, rows=(row, refund), invoices=(first, corrected), year=EARLIER)
    assert earlier.binding_values[INCOME_0171] == Decimal("1000.00")
    assert INCOME_0171 not in unresolved_bindings(earlier)


@pytest.mark.parametrize("base", [Decimal("1000.00"), Decimal("200.00")], ids=["whole", "part"])
def test_a_correction_of_an_invoice_with_a_retencion_refuses(
    operation: PinnedAuthorityOperation, base: Decimal
) -> None:
    """F-1 credits 150,00; no bundled source says what is left of it once the income falls, so no credit is chosen."""
    row, first = paid_invoice(_F1_DATE, _F1_DATE)
    resolution = resolve(operation, _ACCRUAL_YEAR, rows=(row,), invoices=(first, _rectificativa(_R1_DATE, base=base)))
    assert _blocked_because(resolution, "rectificativa_of_retencion")
