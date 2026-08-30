"""LIRPF art. 23.1 expense rollup with art. 23.1.a) cap.

:func:`compute_gastos_for_year` aggregates per-finca
:class:`FincaGasto` rows into a :class:`GastosForYear` result by
:class:`ExpenseCategory`. It implements the art. 23.1.a) párrafo segundo cap:
``intereses de los capitales ajenos`` (FINANCIACION_INTERESES) plus ``gastos de
conservación y reparación`` (CONSERVACION_REPARACION) jointly capped at the
ingresos íntegros del arrendamiento for the same period; the excess carries
forward up to 4 years and is consumed against future ingresos for the same
finca.

Carry-forward representation: a per-finca FIFO queue of
:class:`CarryForwardEntry` rows keyed by origination year. Each entry records the
original-year and the remaining unconsumed amount. Entries older than 4 years are
dropped at rollup time per BOE: "El exceso ... se podrá deducir en los cuatro
años siguientes".
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from decimal import Decimal

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.money import round_to_cents as _round_to_cents
from .enums import ExpenseCategory
from .models import FincaGasto

CARRY_FORWARD_MAX_YEARS: int = 4
"""LIRPF art. 23.1.a) párrafo segundo: ``en los cuatro años siguientes``."""

CAPPED_CATEGORIES: frozenset[ExpenseCategory] = frozenset(
    {ExpenseCategory.FINANCIACION_INTERESES, ExpenseCategory.CONSERVACION_REPARACION},
)
"""The two categories subject to the joint art. 23.1.a) cap."""


class CarryForwardEntry(BaseModel):
    """A single carry-forward generation, anchored to its origination year."""

    model_config = STRICT_FROZEN_CONFIG

    origination_year: int
    remaining_amount: Decimal = Field(ge=Decimal("0"))


class GastosForYear(BaseModel):
    """Aggregated per-finca gastos for a single ejercicio.

    Attributes:
        period_year: Ejercicio.
        ingresos_for_period: Sum of gross_rent_received across the
            finca's contracts for the period.
        por_categoria: Sum per :class:`ExpenseCategory` (uncapped).
        capped_categories_subtotal: Sum of capped-category expenses
            for the period (FINANCIACION + CONSERVACION).
        capped_categories_applied: Capped subtotal after the
            art. 23.1.a) cap is applied (= min(subtotal +
            consumed_carry, ingresos_for_period)).
        capped_categories_excess: Capped subtotal that COULD NOT be
            consumed in the period after applying the cap.
        carry_consumed: Carry-forward consumed (fed into
            capped_categories_applied).
        carry_forward_after: Carry-forward queue after the rollup
            (post-FIFO consumption + 4-year expiration).
        total_deductible: Sum across all deductible categories after
            applying caps and carry-forward consumption.
    """

    model_config = STRICT_FROZEN_CONFIG

    period_year: int
    ingresos_for_period: Decimal = Field(ge=Decimal("0"))
    por_categoria: dict[ExpenseCategory, Decimal]
    capped_categories_subtotal: Decimal = Field(ge=Decimal("0"))
    capped_categories_applied: Decimal = Field(ge=Decimal("0"))
    capped_categories_excess: Decimal = Field(ge=Decimal("0"))
    carry_consumed: Decimal = Field(ge=Decimal("0"))
    carry_forward_after: tuple[CarryForwardEntry, ...]
    total_deductible: Decimal = Field(ge=Decimal("0"))


def compute_gastos_for_year(
    expenses: Iterable[FincaGasto],
    *,
    period_year: int,
    ingresos_for_period: Decimal,
    carry_forward_in: Sequence[CarryForwardEntry] = (),
) -> GastosForYear:
    """Roll up per-finca gastos for ``period_year``.

    Args:
        expenses: Expense rows for the target finca + period.
        period_year: Ejercicio.
        ingresos_for_period: Gross-rent sum across the finca's
            contracts for ``period_year``. Drives the art. 23.1.a)
            cap.
        carry_forward_in: Pre-existing carry-forward queue from
            prior rollups for the same finca. Entries older than
            ``CARRY_FORWARD_MAX_YEARS`` from ``period_year`` are
            dropped.

    Returns:
        :class:`GastosForYear` carrying the aggregated rollup, the
        cap outcome, and the post-rollup carry-forward queue.
    """
    por_categoria: dict[ExpenseCategory, Decimal] = {}
    for expense in expenses:
        if expense.period_year != period_year:
            continue
        existing = por_categoria.get(expense.category, Decimal("0"))
        por_categoria[expense.category] = existing + expense.amount
    for category in list(por_categoria.keys()):
        por_categoria[category] = _round_to_cents(por_categoria[category])

    capped_subtotal = sum(
        (por_categoria.get(category, Decimal("0")) for category in CAPPED_CATEGORIES),
        start=Decimal("0"),
    )
    capped_subtotal = _round_to_cents(capped_subtotal)
    uncapped_subtotal = sum(
        (amount for category, amount in por_categoria.items() if category not in CAPPED_CATEGORIES),
        start=Decimal("0"),
    )
    uncapped_subtotal = _round_to_cents(uncapped_subtotal)

    fresh_carry = _filter_carry(carry_forward_in, period_year=period_year)
    cap_remaining_after_subtotal = max(ingresos_for_period - capped_subtotal, Decimal("0"))
    consumed_carry, remaining_carry = _consume_carry(fresh_carry, cap_remaining_after_subtotal)
    capped_applied = _round_to_cents(min(capped_subtotal, ingresos_for_period) + consumed_carry)
    capped_excess = _round_to_cents(max(capped_subtotal - ingresos_for_period, Decimal("0")))

    carry_after: list[CarryForwardEntry] = list(remaining_carry)
    if capped_excess > Decimal("0"):
        carry_after.append(
            CarryForwardEntry(origination_year=period_year, remaining_amount=capped_excess),
        )

    total_deductible = _round_to_cents(capped_applied + uncapped_subtotal)
    return GastosForYear(
        period_year=period_year,
        ingresos_for_period=_round_to_cents(ingresos_for_period),
        por_categoria=por_categoria,
        capped_categories_subtotal=capped_subtotal,
        capped_categories_applied=capped_applied,
        capped_categories_excess=capped_excess,
        carry_consumed=_round_to_cents(consumed_carry),
        carry_forward_after=tuple(carry_after),
        total_deductible=total_deductible,
    )


def _filter_carry(
    queue: Sequence[CarryForwardEntry],
    *,
    period_year: int,
) -> list[CarryForwardEntry]:
    """Drop carry-forward entries older than ``CARRY_FORWARD_MAX_YEARS``."""
    horizon = period_year - CARRY_FORWARD_MAX_YEARS
    return [entry for entry in queue if entry.origination_year >= horizon]


def _consume_carry(
    queue: Sequence[CarryForwardEntry],
    available_capacity: Decimal,
) -> tuple[Decimal, list[CarryForwardEntry]]:
    """FIFO-consume carry-forward up to ``available_capacity``."""
    if available_capacity <= Decimal("0"):
        return Decimal("0"), list(queue)
    consumed = Decimal("0")
    remaining: list[CarryForwardEntry] = []
    capacity_left = available_capacity
    sorted_queue = sorted(queue, key=lambda entry: entry.origination_year)
    for entry in sorted_queue:
        if capacity_left <= Decimal("0"):
            remaining.append(entry)
            continue
        take = min(entry.remaining_amount, capacity_left)
        consumed += take
        capacity_left -= take
        remainder = entry.remaining_amount - take
        if remainder > Decimal("0"):
            remaining.append(
                CarryForwardEntry(
                    origination_year=entry.origination_year,
                    remaining_amount=remainder,
                ),
            )
    return _round_to_cents(consumed), remaining


__all__ = [
    "CAPPED_CATEGORIES",
    "CARRY_FORWARD_MAX_YEARS",
    "CarryForwardEntry",
    "GastosForYear",
    "compute_gastos_for_year",
]
