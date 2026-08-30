"""Unit tests for the LIRPF art. 23.1 expense rollup.

Exercises :func:`cadrumo.domain.fincas.compute_gastos_for_year` against the
per-category aggregation, the LIRPF art. 23.1.a) cap, and the
4-year carry-forward consumption / expiration rules.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..enums import ExpenseCategory
from ..expense_rollup import CarryForwardEntry, compute_gastos_for_year
from ..models import FincaGasto

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _expense(category: ExpenseCategory, amount: Decimal, *, year: int = 2025) -> FincaGasto:
    return FincaGasto(
        finca_id=1,
        period_year=year,
        category=category,
        amount=amount,
    )


class TestPerCategoryAggregation:
    """Per-:class:`cadrumo.domain.fincas.ExpenseCategory` aggregation behaviour."""

    def test_sums_per_category(self) -> None:
        ibi_a = Decimal("420.00")
        ibi_b = Decimal("80.00")
        comunidad = Decimal("780.00")
        expenses = [
            _expense(ExpenseCategory.IBI_TRIBUTOS_NO_ESTATALES, ibi_a),
            _expense(ExpenseCategory.IBI_TRIBUTOS_NO_ESTATALES, ibi_b),
            _expense(ExpenseCategory.COMUNIDAD, comunidad),
        ]
        rollup = compute_gastos_for_year(
            expenses,
            period_year=2025,
            ingresos_for_period=Decimal("12000.00"),
        )
        assert rollup.por_categoria[ExpenseCategory.IBI_TRIBUTOS_NO_ESTATALES] == ibi_a + ibi_b
        assert rollup.por_categoria[ExpenseCategory.COMUNIDAD] == comunidad
        assert rollup.total_deductible == ibi_a + ibi_b + comunidad
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
        financiacion = Decimal("3000.00")
        reparacion = Decimal("2000.00")
        comunidad = Decimal("500.00")
        expenses = [
            _expense(ExpenseCategory.FINANCIACION_INTERESES, financiacion),
            _expense(ExpenseCategory.CONSERVACION_REPARACION, reparacion),
            _expense(ExpenseCategory.COMUNIDAD, comunidad),
        ]
        rollup = compute_gastos_for_year(
            expenses,
            period_year=2025,
            ingresos_for_period=Decimal("10000.00"),
        )
        capped_subtotal = financiacion + reparacion
        assert rollup.capped_categories_subtotal == capped_subtotal
        assert rollup.capped_categories_applied == capped_subtotal
        assert rollup.capped_categories_excess == Decimal("0.00")
        assert rollup.total_deductible == capped_subtotal + comunidad

    def test_above_cap_excess_carries(self) -> None:
        """8 000 financiación + 5 000 reparación = 13 000; ingresos 10 000;
        cap consumes 10 000; excess 3 000 carries forward."""
        financiacion = Decimal("8000.00")
        reparacion = Decimal("5000.00")
        ibi = Decimal("400.00")
        ingresos = Decimal("10000.00")
        expenses = [
            _expense(ExpenseCategory.FINANCIACION_INTERESES, financiacion),
            _expense(ExpenseCategory.CONSERVACION_REPARACION, reparacion),
            _expense(ExpenseCategory.IBI_TRIBUTOS_NO_ESTATALES, ibi),
        ]
        rollup = compute_gastos_for_year(
            expenses,
            period_year=2025,
            ingresos_for_period=ingresos,
        )
        capped_subtotal = financiacion + reparacion
        excess = capped_subtotal - ingresos
        assert rollup.capped_categories_subtotal == capped_subtotal
        assert rollup.capped_categories_applied == ingresos
        assert rollup.capped_categories_excess == excess
        assert rollup.total_deductible == ingresos + ibi
        assert rollup.carry_forward_after == (CarryForwardEntry(origination_year=2025, remaining_amount=excess),)


class TestCarryForwardConsumption:
    """4-year :class:`cadrumo.domain.fincas.CarryForwardEntry` consumption + expiry."""

    def test_carry_consumed_against_remaining_capacity(self) -> None:
        """Year-1 originated 500 carry; year-2 capped subtotal 7 000, ingresos
        10 000 → remaining capacity 3 000 → 500 consumed."""
        financiacion = Decimal("4000.00")
        reparacion = Decimal("3000.00")
        carry_in = Decimal("500.00")
        expenses = [
            _expense(ExpenseCategory.FINANCIACION_INTERESES, financiacion),
            _expense(ExpenseCategory.CONSERVACION_REPARACION, reparacion),
        ]
        rollup = compute_gastos_for_year(
            expenses,
            period_year=2025,
            ingresos_for_period=Decimal("10000.00"),
            carry_forward_in=(CarryForwardEntry(origination_year=2024, remaining_amount=carry_in),),
        )
        capped_subtotal = financiacion + reparacion
        assert rollup.capped_categories_subtotal == capped_subtotal
        assert rollup.capped_categories_applied == capped_subtotal + carry_in
        assert rollup.carry_consumed == carry_in
        assert rollup.carry_forward_after == ()

    def test_4_year_expiration_drops_old_entries(self) -> None:
        """Carry from 2020 expires at 2025 (5-year gap > 4)."""
        carry_2021 = Decimal("100.00")
        carry_2024 = Decimal("50.00")
        rollup = compute_gastos_for_year(
            [_expense(ExpenseCategory.FINANCIACION_INTERESES, Decimal("100.00"))],
            period_year=2025,
            ingresos_for_period=Decimal("10000.00"),
            carry_forward_in=(
                CarryForwardEntry(origination_year=2020, remaining_amount=Decimal("999.00")),
                CarryForwardEntry(origination_year=2021, remaining_amount=carry_2021),
                CarryForwardEntry(origination_year=2024, remaining_amount=carry_2024),
            ),
        )
        # 2020 dropped; 2021 within 4 years (2025 - 2021 = 4 → kept since
        # horizon is period_year - CARRY_FORWARD_MAX_YEARS = 2021).
        assert rollup.carry_consumed == carry_2021 + carry_2024
        # 2020 entry not consumed and not surfaced — it expired.
        assert all(entry.origination_year != 2020 for entry in rollup.carry_forward_after)

    def test_partial_carry_consumption_preserves_residue(self) -> None:
        """Carry 1 000, remaining capacity 200 → consume 200, residue 800
        stays in the queue."""
        financiacion = Decimal("4900.00")
        reparacion = Decimal("4900.00")
        carry_in = Decimal("1000.00")
        expenses = [
            _expense(ExpenseCategory.FINANCIACION_INTERESES, financiacion),
            _expense(ExpenseCategory.CONSERVACION_REPARACION, reparacion),
        ]
        rollup = compute_gastos_for_year(
            expenses,
            period_year=2025,
            ingresos_for_period=Decimal("10000.00"),
            carry_forward_in=(CarryForwardEntry(origination_year=2024, remaining_amount=carry_in),),
        )
        assert rollup.capped_categories_subtotal == financiacion + reparacion
        assert rollup.carry_consumed == Decimal("200.00")
        assert rollup.carry_forward_after == (
            CarryForwardEntry(origination_year=2024, remaining_amount=carry_in - Decimal("200.00")),
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
