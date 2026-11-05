"""A RETA cuota accrues in the month it is charged, with no invoice, under the devengo election.

A self-employed Seguridad Social cuota covers a calendar month and falls due within it, so its charge
date is its accrual (LIRPF art. 14.1.b, RIRPF art. 7), and the TGSS receipt justifies it. Any other
expense with no invoice or stated date has nothing to place it by under devengo and stays unplaced.

Worked figures: three monthly cuotas of 294,00 charged in January, February and March make 882,00 in
the first quarter; a cuota charged on 28 December belongs to that ejercicio and one charged on 2 January
to the next.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.casilla_id import validated_casilla_id
from ....domain.categories.spending_category import SpendingCategory
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ..renta_gasto_ledger import RentaGastoLedgerAggregation, aggregate_renta_gasto_ledger
from ..renta_imputation import ActivityImputationCriterion
from ..renta_ledger import aggregate_renta_ledger_expenses
from .renta_income_aggregation_support import _period
from .renta_ledger_support import ledger_expense_transaction
from .test_renta_gasto_linked_invoice import _BUCKET, _YEAR, _criteria

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_CUOTA = Decimal("294.00")
_RETA = SpendingCategory.from_registry("cuotas_autonomos_ss")
_ASESORIA = SpendingCategory.from_registry("asesoria_contable")


def _row(name: str, category: SpendingCategory, charged: date, amount: Decimal = _CUOTA) -> Transaction:
    return ledger_expense_transaction(
        name, amount=amount, category=category, booked_date=charged, value_date=charged, taxable_base=amount
    )


def _quarter(rows: tuple[Transaction, ...], code: str) -> RentaGastoLedgerAggregation:
    assert _criteria().usable(_YEAR) is ActivityImputationCriterion.DEVENGO
    return aggregate_renta_gasto_ledger(
        TransactionCatalogue.from_transactions(rows),
        bucket_id=_BUCKET,
        period=_period(_YEAR, code),
        modelo="130",
        target_casilla_id=validated_casilla_id("02", surface="the Modelo 130 expense box"),
        accept_activity_marker=True,
        invoices=build_invoice_catalogue(()),
        criteria=_criteria(),
    )


def _total(result: RentaGastoLedgerAggregation) -> Decimal:
    return sum((o.deductible_amount for o in result.observations), Decimal("0.00"))


def test_monthly_cuotas_without_an_invoice_are_placed_in_their_months() -> None:
    rows = tuple(_row(f"reta-{month}", _RETA, date(_YEAR, month, 28)) for month in (1, 2, 3))

    result = _quarter(rows, "1T")

    assert result.issues == ()
    assert _total(result) == Decimal("882.00")


def test_a_cuota_charged_in_a_later_quarter_is_not_in_the_first() -> None:
    assert _total(_quarter((_row("reta-abril", _RETA, date(_YEAR, 4, 28)),), "1T")) == Decimal("0.00")


def test_an_expense_that_is_not_a_cuota_and_has_no_invoice_stays_unplaced() -> None:
    result = _quarter((_row("asesoria", _ASESORIA, date(_YEAR, 2, 10)),), "1T")

    assert _total(result) == Decimal("0.00")
    assert [issue.reason.value for issue in result.issues] == ["imputation_unresolved"]


def test_a_december_cuota_belongs_to_its_ejercicio_and_a_january_one_to_the_next() -> None:
    december = _row("reta-diciembre", _RETA, date(_YEAR, 12, 28))
    january = _row("reta-enero", _RETA, date(_YEAR + 1, 1, 2))

    annual = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((december, january)),
        build_invoice_catalogue(()),
        bucket_id=_BUCKET,
        period=_period(_YEAR, "0A"),
        profile_year=_YEAR,
        criteria=_criteria(),
    )

    assert [o.transaction_id for o in annual.observations] == [december.transaction_id]
    assert sum((o.deductible_amount for o in annual.observations), Decimal("0.00")) == _CUOTA
