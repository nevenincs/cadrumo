"""A retailer's till settlement accrues on its own day under the devengo election, with no invoice.

A retailer in the recargo de equivalencia sells to final consumers, who receive tickets or
simplified invoices (RD 1619/2012 art. 4), so a monthly settlement of those cash sales has no invoice to
date it. The sale accrues when it is made (LIRPF art. 14.1.b, RIRPF art. 7), which is the day the
settlement carries. An incoming activity row with no invoice and no such category has nothing to date it
and stays unplaced.

Worked figures: settlements of 4.850,00, 4.120,00 and 5.330,00 in January to March make 14.300,00 in
the first quarter; an April settlement is not in it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.casilla_id import validated_casilla_id
from ....domain.calculations.registry.iva_category_catalogue import require_iva_category
from ....domain.transactions.enums import BusinessClassification
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ..renta_income_ledger import aggregate_renta_income_ledger
from .renta_income_aggregation_support import (
    actividad_transaction,
    m130_activity_category_matcher,
    m130_employment_category_matcher,
    renta_income_aggregation_period,
)
from .test_renta_gasto_linked_invoice import BUCKET, YEAR, criteria

_ON_DATE = date(filing_year_envelope().horizon, 6, 15)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def _settlement(name: str, on: date, amount: str, *, till: bool = True) -> Transaction:
    row = actividad_transaction(
        name,
        value_date=on,
        amount=Decimal(amount),
        taxable_base=Decimal(amount),
        business_classification=BusinessClassification.BUSINESS,
    )
    return (
        row.model_copy(update={"iva_category": require_iva_category("recargo_equivalencia", effective_date=_ON_DATE)})
        if till
        else row
    )


def _first_quarter_income(*rows: Transaction) -> tuple[Decimal, list[str]]:
    result = aggregate_renta_income_ledger(
        TransactionCatalogue.from_transactions(rows),
        build_invoice_catalogue(()),
        bucket_id=BUCKET,
        period=renta_income_aggregation_period(YEAR, "1T"),
        modelo="130",
        target_casilla_id=validated_casilla_id("01", surface="the Modelo 130 income box"),
        activity_category_matcher=m130_activity_category_matcher,
        employment_category_matcher=m130_employment_category_matcher,
        criteria=criteria(),
    )
    return (
        sum((o.taxable_base_amount or o.gross_amount for o in result.observations), Decimal("0.00")),
        [issue.reason.value for issue in result.issues],
    )


def test_monthly_till_settlements_are_income_of_their_months() -> None:
    rows = (
        _settlement("tpv-1", date(YEAR, 1, 28), "4850.00"),
        _settlement("tpv-2", date(YEAR, 2, 27), "4120.00"),
        _settlement("tpv-3", date(YEAR, 3, 28), "5330.00"),
        _settlement("tpv-4", date(YEAR, 4, 28), "4680.00"),
    )

    assert _first_quarter_income(*rows) == (Decimal("14300.00"), [])


def test_an_activity_receipt_with_no_invoice_and_no_till_category_stays_unplaced() -> None:
    amount, issues = _first_quarter_income(_settlement("cobro", date(YEAR, 2, 10), "1000.00", till=False))

    assert amount == Decimal("0.00")
    assert issues == ["imputation_unresolved"]
