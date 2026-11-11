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
from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition
from ....domain.categories.spending_category import SpendingCategory
from ....domain.invoices.models import Invoice
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ...actividad_asset.history import ActivityAssetHistory
from ..source_mesh import CalculationSourceResolution
from .ledger_source_mesh_support import (
    InMemoryInvoiceCatalogueRepository,
    m130_box,
    reasons,
    resolve_m100,
    resolve_m130,
)
from .ledger_transaction_support import ledger_raw_transaction
from .test_renta_imputation_criterion import (
    CASH,
    DEVENGO,
    INCOME_0171,
    INCOME_M130_01,
    declared,
    expense_row,
    received,
    renta_imputation_criterion_profile,
    unresolved_bindings,
)
from .test_renta_rectificativa_expense import renta_rectificativa_expense_correction
from .test_renta_rectificativa_income import resolve

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEAR = newest_authored_edition("100")
_PAID_ON = date(_YEAR, 2, 1)
_REFUNDED_ON = date(_YEAR, 5, 1)
_ZERO = Decimal("0")
_HUNDRED = Decimal("100.00")
_PREMIUM = Decimal("400.00")
_PREMIUM_IVA = Decimal("84.00")


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
    return received(_REFUNDED_ON, linked=(linked,)).model_copy(update={"invoice_number": number})


def _repository(*invoices: Invoice) -> InMemoryInvoiceCatalogueRepository:
    repository = InMemoryInvoiceCatalogueRepository()
    repository.save(build_invoice_catalogue(invoices))
    return repository


def _case_a() -> tuple[tuple[Transaction, Transaction], tuple[Invoice, Invoice]]:
    """Paid on R-1, refunded with the only link on R-2."""
    paid_unlinked = expense_row(_PAID_ON, evidence_id=None)
    refund_unlinked = _supplier_refund(_REFUNDED_ON, evidence_id=None)
    first = received(_PAID_ON, linked=(paid_unlinked.transaction_id,))
    second = _refund_invoice("R-2", refund_unlinked.transaction_id)
    return (
        expense_row(_PAID_ON, evidence_id=first.invoice_id),
        _supplier_refund(_REFUNDED_ON, evidence_id=second.invoice_id),
    ), (first, second)


def _case_b(*, accrual_date: date | None) -> tuple[tuple[Transaction, Transaction], tuple[Invoice, Invoice]]:
    """Paid on R-1, a 100,00 correction naming R-1, the refund linked to the correction."""
    paid_unlinked = expense_row(_PAID_ON, evidence_id=None)
    refund_unlinked = _supplier_refund(_REFUNDED_ON, evidence_id=None, accrual_date=accrual_date)
    first = received(_PAID_ON, linked=(paid_unlinked.transaction_id,))
    correction = renta_rectificativa_expense_correction(
        _REFUNDED_ON, base=_HUNDRED, linked=(refund_unlinked.transaction_id,)
    )
    return (
        expense_row(_PAID_ON, evidence_id=first.invoice_id),
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
    return resolve(
        operation, ((_YEAR, criterion),), rows=rows, invoices=invoices, year=_YEAR, modelo=modelo, period=period
    )


def _m100_expense(resolution: CalculationSourceResolution) -> Decimal:
    return sum(resolution.binding_values.values(), _ZERO)


def _blocked(resolution: CalculationSourceResolution) -> list[str]:
    return [item.message for item in resolution.diagnostics if item.reason == "unresolved_binding"]


def test_a_refund_of_a_cash_expense_nets_to_nothing_in_the_annual_return(operation: PinnedAuthorityOperation) -> None:
    rows, invoices = _case_a()
    income = _income(operation, CASH, rows, invoices)
    expense = resolve_m100(
        ActivityAssetHistory(),
        rows=rows,
        profile=renta_imputation_criterion_profile(operation, declared((_YEAR, CASH))),
        invoices=_repository(*invoices),
    )
    assert income.binding_values[INCOME_0171] == _ZERO
    assert INCOME_0171 not in unresolved_bindings(income)
    assert _m100_expense(expense) == _ZERO
    assert _blocked(expense) == []


def test_the_instalment_reads_a_cash_refund_as_the_annual_return_does(operation: PinnedAuthorityOperation) -> None:
    rows, invoices = _case_a()
    profile = renta_imputation_criterion_profile(operation, declared((_YEAR, CASH)))
    income = _income(operation, CASH, rows, invoices, modelo="130", period="2T")
    expense = resolve_m130(ActivityAssetHistory(), "2T", rows=rows, profile=profile, invoices=_repository(*invoices))
    assert income.binding_values[INCOME_M130_01] == _ZERO
    assert m130_box(expense) == _ZERO
    assert _blocked(expense) == []


def test_the_instalment_before_the_refund_keeps_the_whole_expense(operation: PinnedAuthorityOperation) -> None:
    rows, invoices = _case_a()
    profile = renta_imputation_criterion_profile(operation, declared((_YEAR, CASH)))
    expense = resolve_m130(ActivityAssetHistory(), "1T", rows=rows, profile=profile, invoices=_repository(*invoices))
    assert m130_box(expense) == _HUNDRED


@pytest.mark.parametrize("accrual_date", [_REFUNDED_ON, None], ids=["accrual_stated", "accrual_absent"])
def test_a_refund_on_a_correction_is_left_to_the_netting_in_both_returns(
    operation: PinnedAuthorityOperation, accrual_date: date | None
) -> None:
    rows, invoices = _case_b(accrual_date=accrual_date)
    profile = renta_imputation_criterion_profile(operation, declared((_YEAR, DEVENGO)))
    income = _income(operation, DEVENGO, rows, invoices)
    annual = resolve_m100(ActivityAssetHistory(), rows=rows, profile=profile, invoices=_repository(*invoices))
    instalment = resolve_m130(ActivityAssetHistory(), "2T", rows=rows, profile=profile, invoices=_repository(*invoices))
    assert income.binding_values[INCOME_0171] == _ZERO
    assert INCOME_0171 not in unresolved_bindings(income)
    assert _m100_expense(annual) == _ZERO
    assert m130_box(instalment) == _ZERO
    assert _blocked(annual) == []
    assert _blocked(instalment) == []
    assert "source_issue" not in reasons(annual)
    assert "source_issue" not in reasons(instalment)


def _premium(on: date, *, direction: TransactionDirection, evidence_id: str | None) -> Transaction:
    """Return a 400,00 health premium, or its refund, capped together with the others."""
    return expense_row(on, evidence_id=evidence_id, amount=_PREMIUM + _PREMIUM_IVA, base=_PREMIUM).model_copy(
        update={"direction": direction, "category_id": SpendingCategory.from_registry("seguros_salud_autonomo").value}
    )


def _premium_invoice(number: str, on: date, linked: str) -> Invoice:
    line = (
        received(on, linked=(linked,))
        .lines[0]
        .model_copy(
            update={
                "unit_price": _PREMIUM,
                "subtotal": _PREMIUM,
                "iva_amount": _PREMIUM_IVA,
            }
        )
    )
    return received(on, linked=(linked,)).model_copy(
        update={
            "invoice_number": number,
            "base_total": _PREMIUM,
            "iva_total": _PREMIUM_IVA,
            "grand_total": _PREMIUM + _PREMIUM_IVA,
            "lines": (line,),
        }
    )


@pytest.mark.parametrize(
    ("months", "expected"),
    [((1, 2), Decimal("400.00")), ((1, 2, 3), Decimal("500.00"))],
    ids=["refund_keeps_the_total_under_the_cap", "remainder_still_above_the_cap"],
)
def test_a_refund_counts_against_the_shared_cap_of_the_instalment(
    operation: PinnedAuthorityOperation, months: tuple[int, ...], expected: Decimal
) -> None:
    """400,00 x 2 less 400,00 = 400,00 stays under the 500,00 cap; 400,00 x 3 less 400,00 = 800,00 is held to it."""
    rows: list[Transaction] = []
    invoices: list[Invoice] = []
    for month in months:
        on = date(_YEAR, month, 1)
        row = _premium(on, direction=TransactionDirection.OUTGOING, evidence_id=None)
        invoice = _premium_invoice(f"P-{month}", on, row.transaction_id)
        invoices.append(invoice)
        rows.append(_premium(on, direction=TransactionDirection.OUTGOING, evidence_id=invoice.invoice_id))
    refund_on = date(_YEAR, 5, 1)
    unlinked = _premium(refund_on, direction=TransactionDirection.INCOMING, evidence_id=None)
    refund_invoice = _premium_invoice("P-R", refund_on, unlinked.transaction_id)
    invoices.append(refund_invoice)
    rows.append(_premium(refund_on, direction=TransactionDirection.INCOMING, evidence_id=refund_invoice.invoice_id))
    profile = renta_imputation_criterion_profile(operation, declared((_YEAR, CASH)))
    expense = resolve_m130(
        ActivityAssetHistory(), "2T", rows=tuple(rows), profile=profile, invoices=_repository(*invoices)
    )
    assert m130_box(expense) == expected
