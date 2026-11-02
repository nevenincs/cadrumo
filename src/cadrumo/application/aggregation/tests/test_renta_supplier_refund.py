"""A supplier's refund takes the expense back; it is not income, and it counts once.

LIRPF art. 28.1 fixes the rendimiento neto by the rules of the Impuesto sobre Sociedades, and
art. 14.1.b imputes by them. What a supplier returns undoes an acquisition, so it comes off
the expense the row was deducted under, with that row's category rule. The manual lists what
reduces income, in its "Partidas negativas" (Manual Renta, ch. 7): returns of sales and the
like, nothing returned by a supplier. Worked by hand:

- Cash, paid 121,00 (base 100,00) on R-1, refunded 121,00 on R-2: expense 100,00 - 100,00 = 0,00,
  income 0,00, net 0,00.
- Accrual, the same payment, a 100,00 correction naming R-1, the refund linked to the correction:
  the correction takes 100/100 of the row, so expense 0,00, income 0,00, net 0,00.
- The instalment reads the same figures from the quarter the refund is placed in.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.categories.spending_category import SpendingCategory
from ....domain.invoices.models import Invoice
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ...actividad_asset.history import ActivityAssetHistory
from ..source_mesh import CalculationSourceResolution
from .ledger_source_mesh_support import (
    BUCKET_ID,
    _InMemoryInvoiceCatalogueRepository,
    m130_box,
    resolve_m100,
    resolve_m130,
)
from .ledger_transaction_support import ledger_raw_transaction
from .test_renta_imputation_criterion import (
    _CASH,
    _DEVENGO,
    _INCOME_0171,
    _INCOME_M130_01,
    _declared,
    _expense_row,
    _profile,
    _received,
    _unresolved_bindings,
)
from .test_renta_rectificativa_expense import _correction
from .test_renta_rectificativa_income import _resolve as _resolve_income

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEAR = 2025
_PAID_ON = date(_YEAR, 2, 1)
_REFUNDED_ON = date(_YEAR, 5, 1)
_ZERO = Decimal("0")
_HUNDRED = Decimal("100.00")


def _supplier_refund(
    on: date,
    *,
    evidence_id: str | None,
    accrual_date: date | None = None,
    base: Decimal | None = _HUNDRED,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": ledger_raw_transaction(f"abono-{on.isoformat()}", booked_date=on, amount=Decimal("121.00")),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "purchase_invoice_evidence_id": evidence_id,
            "taxable_base": base,
            "accrual_date": accrual_date,
            "category_id": SpendingCategory.from_registry("asesoria_fiscal").value,
            "classified_at": datetime(_YEAR, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _refund_invoice(number: str, linked: str) -> Invoice:
    """Return a plain received invoice of 100,00 + 21,00 carrying the refund as its only link."""
    return _received(_REFUNDED_ON, linked=(linked,)).model_copy(update={"invoice_number": number})


def _repository(*invoices: Invoice) -> _InMemoryInvoiceCatalogueRepository:
    repository = _InMemoryInvoiceCatalogueRepository()
    repository.save(build_invoice_catalogue(invoices))
    return repository


def _case_a() -> tuple[tuple[Transaction, Transaction], tuple[Invoice, Invoice]]:
    """Paid on R-1, refunded with the only link on R-2."""
    paid_unlinked = _expense_row(_PAID_ON, evidence_id=None)
    refund_unlinked = _supplier_refund(_REFUNDED_ON, evidence_id=None)
    first = _received(_PAID_ON, linked=(paid_unlinked.transaction_id,))
    second = _refund_invoice("R-2", refund_unlinked.transaction_id)
    return (
        _expense_row(_PAID_ON, evidence_id=first.invoice_id),
        _supplier_refund(_REFUNDED_ON, evidence_id=second.invoice_id),
    ), (first, second)


def _case_b(*, accrual_date: date | None) -> tuple[tuple[Transaction, Transaction], tuple[Invoice, Invoice]]:
    """Paid on R-1, a 100,00 correction naming R-1, the refund linked to the correction."""
    paid_unlinked = _expense_row(_PAID_ON, evidence_id=None)
    refund_unlinked = _supplier_refund(_REFUNDED_ON, evidence_id=None, accrual_date=accrual_date)
    first = _received(_PAID_ON, linked=(paid_unlinked.transaction_id,))
    correction = _correction(_REFUNDED_ON, base=_HUNDRED, linked=(refund_unlinked.transaction_id,))
    return (
        _expense_row(_PAID_ON, evidence_id=first.invoice_id),
        _supplier_refund(_REFUNDED_ON, evidence_id=correction.invoice_id, accrual_date=accrual_date),
    ), (first, correction)


def _income(
    operation: PinnedAuthorityOperation,
    criterion: str,
    rows: tuple[Transaction, ...],
    invoices: tuple[Invoice, ...],
    *,
    modelo: str = "100",
    period: str = "0A",
) -> CalculationSourceResolution:
    return _resolve_income(
        operation, ((_YEAR, criterion),), rows=rows, invoices=invoices, year=_YEAR, modelo=modelo, period=period
    )


def _m100_expense(resolution: CalculationSourceResolution) -> Decimal:
    return sum(resolution.binding_values.values(), _ZERO)


def _blocked(resolution: CalculationSourceResolution) -> list[str]:
    return [item.message for item in resolution.diagnostics if item.reason == "unresolved_binding"]


def test_a_refund_of_a_cash_expense_nets_to_nothing_in_the_annual_return(operation: PinnedAuthorityOperation) -> None:
    rows, invoices = _case_a()
    income = _income(operation, _CASH, rows, invoices)
    expense = resolve_m100(
        ActivityAssetHistory(),
        rows=rows,
        profile=_profile(operation, _declared((_YEAR, _CASH))),
        invoices=_repository(*invoices),
    )
    assert income.binding_values[_INCOME_0171] == _ZERO
    assert _INCOME_0171 not in _unresolved_bindings(income)
    assert _m100_expense(expense) == _ZERO
    assert _blocked(expense) == []


def test_the_instalment_reads_a_cash_refund_as_the_annual_return_does(operation: PinnedAuthorityOperation) -> None:
    rows, invoices = _case_a()
    profile = _profile(operation, _declared((_YEAR, _CASH)))
    income = _income(operation, _CASH, rows, invoices, modelo="130", period="2T")
    expense = resolve_m130(ActivityAssetHistory(), "2T", rows=rows, profile=profile, invoices=_repository(*invoices))
    assert income.binding_values[_INCOME_M130_01] == _ZERO
    assert m130_box(expense) == _ZERO
    assert _blocked(expense) == []


def test_the_instalment_before_the_refund_keeps_the_whole_expense(operation: PinnedAuthorityOperation) -> None:
    rows, invoices = _case_a()
    profile = _profile(operation, _declared((_YEAR, _CASH)))
    expense = resolve_m130(ActivityAssetHistory(), "1T", rows=rows, profile=profile, invoices=_repository(*invoices))
    assert m130_box(expense) == _HUNDRED


@pytest.mark.parametrize("accrual_date", [_REFUNDED_ON, None], ids=["accrual_stated", "accrual_absent"])
def test_a_refund_on_a_correction_is_left_to_the_netting_in_both_returns(
    operation: PinnedAuthorityOperation, accrual_date: date | None
) -> None:
    rows, invoices = _case_b(accrual_date=accrual_date)
    profile = _profile(operation, _declared((_YEAR, _DEVENGO)))
    income = _income(operation, _DEVENGO, rows, invoices)
    annual = resolve_m100(ActivityAssetHistory(), rows=rows, profile=profile, invoices=_repository(*invoices))
    instalment = resolve_m130(ActivityAssetHistory(), "2T", rows=rows, profile=profile, invoices=_repository(*invoices))
    assert income.binding_values[_INCOME_0171] == _ZERO
    assert _INCOME_0171 not in _unresolved_bindings(income)
    assert _m100_expense(annual) == _ZERO
    assert m130_box(instalment) == _ZERO
    assert _blocked(annual) == []
    assert _blocked(instalment) == []
    assert BUCKET_ID
