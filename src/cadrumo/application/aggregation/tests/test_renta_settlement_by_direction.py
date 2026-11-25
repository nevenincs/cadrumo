"""What a linked invoice's receipts settle, read by the direction each row moved.

Bank amounts are magnitudes with the direction beside them, so a refund must be taken
off the receipts rather than added to them. Worked by hand on the shared invoice:

- F-1: 1.000,00 base + 210,00 IVA - 150,00 retencion leaves 1.060,00 to bank.
- Two receipts of 530,00 settle it, so the invoice's whole 150,00 is withheld and paid.
- 1.061,00 banked against 1.060,00 leaves 1,00 no document explains.
- 1.060,00 banked less a 106,00 refund nets 954,00.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.invoices.models import Invoice
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction
from ..renta_income_evidence import settlement_comparison, taxable_base_comparison
from .test_renta_imputation_criterion import (
    BANKED,
    CREDIT_0599,
    DEVENGO,
    INCOME_0171,
    LATER,
    declared,
    expense_row,
    issued,
    received,
    renta_imputation_criterion_receipt,
    unresolved_bindings,
)
from .test_renta_imputation_findings import messages, part_paid, resolve
from .test_renta_rectificativa_income import renta_rectificativa_income_refund

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_ACCRUED = date(LATER, 1, 15)
_ACCRUAL_YEAR = declared((LATER, DEVENGO))


def _with_refund() -> tuple[tuple[Transaction, ...], Invoice]:
    """Return a receipt and a refund, both linked to the invoice they move money on."""
    paid_on, refunded_on = date(LATER, 2, 1), date(LATER, 3, 1)
    refund_amount = Decimal("106.00")
    invoice = issued(
        _ACCRUED,
        linked=(
            renta_imputation_criterion_receipt(paid_on).transaction_id,
            renta_rectificativa_income_refund(refunded_on, amount=refund_amount).transaction_id,
        ),
    )
    return (
        renta_imputation_criterion_receipt(paid_on, invoice_id=invoice.invoice_id),
        renta_rectificativa_income_refund(refunded_on, invoice_id=invoice.invoice_id, amount=refund_amount),
    ), invoice


def test_a_refund_comes_off_the_receipts_of_an_issued_invoice() -> None:
    rows, invoice = _with_refund()
    comparison = settlement_comparison(invoice, rows)
    assert comparison is not None
    assert comparison.cash == BANKED - Decimal("106.00")
    assert not comparison.settled


def test_a_refund_comes_off_the_rows_of_a_received_invoice() -> None:
    """100,00 paid less 20,00 returned leaves 80,00 of the base covered."""
    on = date(LATER, 2, 1)
    paid = expense_row(on, evidence_id="x")
    returned = expense_row(date(LATER, 3, 1), evidence_id="x", amount=Decimal("24.20"), base=Decimal("20.00"))
    returned = returned.model_copy(update={"direction": TransactionDirection.INCOMING})
    invoice = received(on, linked=(paid.transaction_id, returned.transaction_id))
    comparison = taxable_base_comparison(invoice, (paid, returned))
    assert comparison is not None
    assert comparison.cash == Decimal("80.00")


def test_a_refund_does_not_read_as_an_overpayment(operation: PinnedAuthorityOperation) -> None:
    """1.060,00 less 106,00 is under the invoice, and accrued income is still the invoice's 1.000,00."""
    rows, invoice = _with_refund()
    resolution = resolve(operation, _ACCRUAL_YEAR, rows=rows, invoices=(invoice,), year=LATER)
    assert resolution.binding_values[INCOME_0171] == Decimal("1000.00")
    assert INCOME_0171 not in unresolved_bindings(resolution)


def test_part_payments_settling_the_invoice_credit_its_whole_retencion(operation: PinnedAuthorityOperation) -> None:
    """530,00 + 530,00 = 1.060,00: the invoice states 150,00 and all of it has been paid."""
    rows, invoice = part_paid(_ACCRUED, (date(LATER, 2, 1), "530.00"), (date(LATER, 3, 1), "530.00"))
    resolution = resolve(operation, _ACCRUAL_YEAR, rows=rows, invoices=(invoice,), year=LATER)
    assert resolution.binding_values[CREDIT_0599] == Decimal("150.00")
    assert messages(resolution, "part_payment_allocated") == []


def test_three_uneven_settling_payments_credit_exactly_the_stated_retencion(
    operation: PinnedAuthorityOperation,
) -> None:
    """100,00 + 333,33 + 626,67 = 1.060,00; the three shares of 150,00 meet at 150,00, not a cent off."""
    rows, invoice = part_paid(
        _ACCRUED, (date(LATER, 2, 1), "100.00"), (date(LATER, 3, 1), "333.33"), (date(LATER, 4, 1), "626.67")
    )
    resolution = resolve(operation, _ACCRUAL_YEAR, rows=rows, invoices=(invoice,), year=LATER)
    assert resolution.binding_values[CREDIT_0599] == Decimal("150.00")


def test_a_part_payment_short_of_the_invoice_stays_out_of_the_credit(operation: PinnedAuthorityOperation) -> None:
    """530,00 + 400,00 = 930,00 leaves the invoice open, so the pro rata share stays reported."""
    rows, invoice = part_paid(_ACCRUED, (date(LATER, 2, 1), "530.00"), (date(LATER, 3, 1), "400.00"))
    resolution = resolve(operation, _ACCRUAL_YEAR, rows=rows, invoices=(invoice,), year=LATER)
    assert resolution.binding_values[CREDIT_0599] == Decimal("0")
    assert messages(resolution, "part_payment_allocated")


def test_a_single_overpaying_receipt_does_not_pass_cash_off_as_income(operation: PinnedAuthorityOperation) -> None:
    """1.061,00 against 1.060,00: nothing says what the 1,00 is, and 1.061,00 of income would carry the IVA."""
    amount = Decimal("1061.00")
    invoice = issued(
        _ACCRUED, linked=(renta_imputation_criterion_receipt(date(LATER, 2, 1), amount=amount).transaction_id,)
    )
    row = renta_imputation_criterion_receipt(date(LATER, 2, 1), invoice_id=invoice.invoice_id, amount=amount)
    resolution = resolve(operation, _ACCRUAL_YEAR, rows=(row,), invoices=(invoice,), year=LATER)
    assert resolution.binding_values[INCOME_0171] != amount
    assert INCOME_0171 in unresolved_bindings(resolution)
    assert any("overpaid_invoice" in item.message for item in resolution.diagnostics)


def test_one_cent_over_still_settles(operation: PinnedAuthorityOperation) -> None:
    amount = Decimal("1060.01")
    invoice = issued(
        _ACCRUED, linked=(renta_imputation_criterion_receipt(date(LATER, 2, 1), amount=amount).transaction_id,)
    )
    row = renta_imputation_criterion_receipt(date(LATER, 2, 1), invoice_id=invoice.invoice_id, amount=amount)
    resolution = resolve(operation, _ACCRUAL_YEAR, rows=(row,), invoices=(invoice,), year=LATER)
    assert resolution.binding_values[INCOME_0171] == Decimal("1000.00")
    assert resolution.binding_values[CREDIT_0599] == Decimal("150.00")
    assert INCOME_0171 not in unresolved_bindings(resolution)
