"""Unit tests for the LIRPF art. 23.1 expense rollup.

Exercises :func:`aeat.domain.rental.compute_gastos_for_year` against the
per-category aggregation, the LIRPF art. 23.1.a) cap, and the
4-year carry-forward consumption / expiration rules.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from . import (
    CarryForwardEntry,
    ExpenseCategory,
    RentalExpense,
    compute_gastos_for_year,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _expense(category: ExpenseCategory, amount: Decimal, *, year: int = 2025) -> RentalExpense:
    return RentalExpense(
        finca_id=1,
        period_year=year,
        category=category,
        amount=amount,
    )


class TestPerCategoryAggregation:
    """Per-:class:`aeat.domain.rental.ExpenseCategory` aggregation behaviour."""

    def test_sums_per_category(self) -> None:
        expenses = [
            _expense(ExpenseCategory.IBI_TRIBUTOS_NO_ESTATALES, Decimal("420.00")),
            _expense(ExpenseCategory.IBI_TRIBUTOS_NO_ESTATALES, Decimal("80.00")),
            _expense(ExpenseCategory.COMUNIDAD, Decimal("780.00")),
        ]
        rollup = compute_gastos_for_year(
            expenses,
            period_year=2025,
            ingresos_for_period=Decimal("12000.00"),
        )
        assert rollup.por_categoria[ExpenseCategory.IBI_TRIBUTOS_NO_ESTATALES] == Decimal("500.00")
        assert rollup.por_categoria[ExpenseCategory.COMUNIDAD] == Decimal("780.00")
        assert rollup.total_deductible == Decimal("1280.00")
        assert rollup.capped_categories_subtotal == Decimal("0.00")
        assert rollup.capped_categories_excess == Decimal("0.00")

    def test_ignores_other_periods(self) -> None:
        expenses = [
            _expense(ExpenseCategory.COMUNIDAD, Decimal("50.00"), year=2024),
            _expense(ExpenseCategory.COMUNIDAD, Decimal("60.00"), year=2025),
        ]
        rollup = compute_gastos_for_year(
            expenses,
            period_year=2025,
            ingresos_for_period=Decimal("1000.00"),
        )
        assert rollup.por_categoria[ExpenseCategory.COMUNIDAD] == Decimal("60.00")


class TestArt2311aCap:
    """LIRPF art. 23.1.a) ingreso-bound cap on financiación / reparación expenses."""

    def test_below_cap_no_excess(self) -> None:
        expenses = [
            _expense(ExpenseCategory.FINANCIACION_INTERESES, Decimal("3000.00")),
            _expense(ExpenseCategory.CONSERVACION_REPARACION, Decimal("2000.00")),
            _expense(ExpenseCategory.COMUNIDAD, Decimal("500.00")),
        ]
        rollup = compute_gastos_for_year(
            expenses,
            period_year=2025,
            ingresos_for_period=Decimal("10000.00"),
        )
        assert rollup.capped_categories_subtotal == Decimal("5000.00")
        assert rollup.capped_categories_applied == Decimal("5000.00")
        assert rollup.capped_categories_excess == Decimal("0.00")
        assert rollup.total_deductible == Decimal("5500.00")

    def test_above_cap_excess_carries(self) -> None:
        """8 000 financiación + 5 000 reparación = 13 000; ingresos 10 000;
        cap consumes 10 000; excess 3 000 carries forward."""
        expenses = [
            _expense(ExpenseCategory.FINANCIACION_INTERESES, Decimal("8000.00")),
            _expense(ExpenseCategory.CONSERVACION_REPARACION, Decimal("5000.00")),
            _expense(ExpenseCategory.IBI_TRIBUTOS_NO_ESTATALES, Decimal("400.00")),
        ]
        rollup = compute_gastos_for_year(
            expenses,
            period_year=2025,
            ingresos_for_period=Decimal("10000.00"),
        )
        assert rollup.capped_categories_subtotal == Decimal("13000.00")
        assert rollup.capped_categories_applied == Decimal("10000.00")
        assert rollup.capped_categories_excess == Decimal("3000.00")
        assert rollup.total_deductible == Decimal("10400.00")
        assert rollup.carry_forward_after == (
            CarryForwardEntry(origination_year=2025, remaining_amount=Decimal("3000.00")),
        )


class TestCarryForwardConsumption:
    """4-year :class:`aeat.domain.rental.CarryForwardEntry` consumption + expiry."""

    def test_carry_consumed_against_remaining_capacity(self) -> None:
        """Year-1 originated 500 carry; year-2 capped subtotal 7 000, ingresos
        10 000 → remaining capacity 3 000 → 500 consumed."""
        expenses = [
            _expense(ExpenseCategory.FINANCIACION_INTERESES, Decimal("4000.00")),
            _expense(ExpenseCategory.CONSERVACION_REPARACION, Decimal("3000.00")),
        ]
        rollup = compute_gastos_for_year(
            expenses,
            period_year=2025,
            ingresos_for_period=Decimal("10000.00"),
            carry_forward_in=(CarryForwardEntry(origination_year=2024, remaining_amount=Decimal("500.00")),),
        )
        assert rollup.capped_categories_subtotal == Decimal("7000.00")
        assert rollup.capped_categories_applied == Decimal("7500.00")
        assert rollup.carry_consumed == Decimal("500.00")
        assert rollup.carry_forward_after == ()

    def test_4_year_expiration_drops_old_entries(self) -> None:
        """Carry from 2020 expires at 2025 (5-year gap > 4)."""
        rollup = compute_gastos_for_year(
            [_expense(ExpenseCategory.FINANCIACION_INTERESES, Decimal("100.00"))],
            period_year=2025,
            ingresos_for_period=Decimal("10000.00"),
            carry_forward_in=(
                CarryForwardEntry(origination_year=2020, remaining_amount=Decimal("999.00")),
                CarryForwardEntry(origination_year=2021, remaining_amount=Decimal("100.00")),
                CarryForwardEntry(origination_year=2024, remaining_amount=Decimal("50.00")),
            ),
        )
        # 2020 dropped; 2021 within 4 years (2025 - 2021 = 4 → kept since
        # horizon is period_year - CARRY_FORWARD_MAX_YEARS = 2021).
        assert rollup.carry_consumed == Decimal("150.00")
        # 2020 entry not consumed and not surfaced — it expired.
        assert all(entry.origination_year != 2020 for entry in rollup.carry_forward_after)

    def test_partial_carry_consumption_preserves_residue(self) -> None:
        """Carry 1 000, remaining capacity 200 → consume 200, residue 800
        stays in the queue."""
        expenses = [
            _expense(ExpenseCategory.FINANCIACION_INTERESES, Decimal("4900.00")),
            _expense(ExpenseCategory.CONSERVACION_REPARACION, Decimal("4900.00")),
        ]
        rollup = compute_gastos_for_year(
            expenses,
            period_year=2025,
            ingresos_for_period=Decimal("10000.00"),
            carry_forward_in=(CarryForwardEntry(origination_year=2024, remaining_amount=Decimal("1000.00")),),
        )
        assert rollup.capped_categories_subtotal == Decimal("9800.00")
        assert rollup.carry_consumed == Decimal("200.00")
        assert rollup.carry_forward_after == (
            CarryForwardEntry(origination_year=2024, remaining_amount=Decimal("800.00")),
        )

    def test_no_capacity_no_consumption(self) -> None:
        """Capped subtotal already exceeds ingresos → 0 capacity for carry."""
        expenses = [_expense(ExpenseCategory.FINANCIACION_INTERESES, Decimal("12000.00"))]
        rollup = compute_gastos_for_year(
            expenses,
            period_year=2025,
            ingresos_for_period=Decimal("10000.00"),
            carry_forward_in=(CarryForwardEntry(origination_year=2024, remaining_amount=Decimal("500.00")),),
        )
        assert rollup.carry_consumed == Decimal("0.00")
        # Original carry preserved + new excess (2 000) added.
        ages = sorted(entry.origination_year for entry in rollup.carry_forward_after)
        assert ages == [2024, 2025]
