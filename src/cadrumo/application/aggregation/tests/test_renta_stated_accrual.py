"""A row with no invoice can state when it accrues, and only Renta reads that date.

Worked by hand: the expense row carries a taxable base of 100,00 and the receipt
1.060,00 with no IVA stated, so under accrual each lands whole in the year its
stated date names and adds nothing to the year its bank date falls in.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.iva.schema import InvoiceKind
from ....domain.transactions.models import Transaction
from ...actividad_asset.history import ActivityAssetHistory
from ..renta_imputation import ImputationUnresolved, row_accrual_date
from .ledger_source_mesh_support import m130_box, resolve_m100, resolve_m130
from .test_renta_imputation_criterion import (
    _CASH,
    _DEVENGO,
    _EARLIER,
    _INCOME_0171,
    _LATER,
    _ZERO,
    _declared,
    _expense_ledger,
    _expense_row,
    _profile,
    _receipt,
    _resolve,
    _unresolved_bindings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BASE = Decimal("100.00")
_RECEIPT = Decimal("1060.00")
_M130_YEAR = 2025
"""The ejercicio the Modelo 130 resolver support pins."""


def _stating(row: Transaction, accrual: date) -> Transaction:
    return row.model_copy(update={"accrual_date": accrual})


@pytest.mark.parametrize(
    ("criterion", "first_year", "second_year"),
    [(_DEVENGO, _BASE, _ZERO), (_CASH, _ZERO, _BASE)],
)
def test_m100_places_a_stated_expense_once_in_the_year_its_criterion_names(
    operation: PinnedAuthorityOperation, criterion: str, first_year: Decimal, second_year: Decimal
) -> None:
    row = _stating(_expense_row(date(_LATER, 1, 10), evidence_id=None), date(_EARLIER, 4, 1))
    profile = _profile(operation, _declared((_EARLIER, criterion), (_LATER, criterion)))
    history = ActivityAssetHistory()

    first = resolve_m100(history, rows=(row,), profile=profile, year=_EARLIER)
    second = resolve_m100(history, rows=(row,), profile=profile, year=_LATER)

    assert sum(first.binding_values.values(), _ZERO) == first_year
    assert sum(second.binding_values.values(), _ZERO) == second_year
    assert "unresolved_binding" not in {item.reason for item in (*first.diagnostics, *second.diagnostics)}


@pytest.mark.parametrize(("period", "expected"), [("1T", _ZERO), ("2T", _BASE), ("3T", _BASE)])
def test_m130_accumulates_a_stated_expense_from_the_quarter_it_accrues(
    operation: PinnedAuthorityOperation, period: str, expected: Decimal
) -> None:
    row = _stating(_expense_row(date(_M130_YEAR, 7, 10), evidence_id=None), date(_M130_YEAR, 4, 1))
    profile = _profile(operation, _declared((_M130_YEAR, _DEVENGO)))

    resolution = resolve_m130(ActivityAssetHistory(), period, rows=(row,), profile=profile)

    assert m130_box(resolution) == expected


def test_an_operation_date_is_not_a_stated_accrual(operation: PinnedAuthorityOperation) -> None:
    """Absent stays absent: the IVA date of the row answers nothing about Renta."""
    row = _expense_row(date(_M130_YEAR, 4, 1), evidence_id=None).model_copy(
        update={"operation_date": date(_M130_YEAR, 3, 1)}
    )
    profile = _profile(operation, _declared((_M130_YEAR, _DEVENGO)))

    resolution = resolve_m130(ActivityAssetHistory(), "2T", rows=(row,), profile=profile)

    assert m130_box(resolution) == _ZERO
    assert "unresolved_binding" in {item.reason for item in resolution.diagnostics}


def test_a_stated_receipt_lands_in_its_accrual_year_and_not_its_bank_year(operation: PinnedAuthorityOperation) -> None:
    row = _stating(_receipt(date(_LATER, 1, 10)), date(_EARLIER, 11, 20))
    facts = _declared((_EARLIER, _DEVENGO), (_LATER, _DEVENGO))

    first = _resolve(operation, facts, rows=(row,), year=_EARLIER)
    second = _resolve(operation, facts, rows=(row,), year=_LATER)

    assert first.binding_values[_INCOME_0171] == _RECEIPT
    assert second.binding_values[_INCOME_0171] == _ZERO
    assert _INCOME_0171 not in _unresolved_bindings(first)
    assert _INCOME_0171 not in _unresolved_bindings(second)


def test_a_stated_date_that_disagrees_with_the_invoice_stays_unresolved(operation: PinnedAuthorityOperation) -> None:
    row, invoices = _expense_ledger(date(_M130_YEAR, 4, 1), date(_M130_YEAR, 7, 10))
    stated = _stating(row, date(_M130_YEAR, 5, 1))
    profile = _profile(operation, _declared((_M130_YEAR, _DEVENGO)))

    resolution = resolve_m130(ActivityAssetHistory(), "3T", rows=(stated,), profile=profile, invoices=invoices)

    assert m130_box(resolution) == _ZERO
    assert any(ImputationUnresolved.ACCRUAL_CONFLICT.value in item.message for item in resolution.diagnostics)


def test_a_stated_date_that_agrees_with_the_invoice_counts_once(operation: PinnedAuthorityOperation) -> None:
    row, invoices = _expense_ledger(date(_M130_YEAR, 4, 1), date(_M130_YEAR, 7, 10))
    stated = _stating(row, date(_M130_YEAR, 4, 1))
    profile = _profile(operation, _declared((_M130_YEAR, _DEVENGO)))

    resolution = resolve_m130(ActivityAssetHistory(), "2T", rows=(stated,), profile=profile, invoices=invoices)

    assert m130_box(resolution) == _BASE
    assert row_accrual_date(stated, None, kind=InvoiceKind.RECEIVED) == date(_M130_YEAR, 4, 1)
