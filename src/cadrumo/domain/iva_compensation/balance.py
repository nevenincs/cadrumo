"""Pure IVA-compensation wallet balance projection for Modelo 303.

Summarises a :class:`IvaCompensationCarryForwardReport` into a balance snapshot.
All logic here is pure: it depends only on :mod:`decimal`, pydantic,
:data:`STRICT_FROZEN_CONFIG`-style strict config, and the sibling carry-forward
records. The repository-backed orchestration that loads stored period states and
builds the report lives in the application layer.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, cast

from pydantic import BaseModel, Field, NonNegativeInt

from ...core.filing_year import FilingYear
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import ResolvedScalarFact, ScalarFactQuery
from ..calculations.registry.schema_base import DateAxis
from .carry_forward import (
    IvaCompensationCarryForwardLot,
    IvaCompensationCarryForwardReport,
    IvaCompensationExpiryReviewState,
)

if TYPE_CHECKING:
    from ..calculations.registry.authority import ValidatedRegistryAuthority


_CARRY_WINDOW_FACT_ID = "liva-art-99-compensation-carry-window-years"

CompensationExpiryYear = Annotated[int, Field(ge=2000, le=2200)]
"""The year an unused compensation lot lapses.

Deliberately wider than :obj:`~cadrumo.core.filing_year.FilingYear`. This is a
DERIVED year based on the configured carry window for the earliest still-active lot --
so it may legitimately fall beyond the last year a return can be filed for, and
narrowing it to the filing-year range would refuse a balance the engine can
correctly produce.

Declared once because the CLI wallet payload projects the same field. The bound
was written out at both sites identically, which is the shape that drifts: the
payload can loosen or tighten without the model noticing.
"""


class IvaWalletBalanceReport(BaseModel):
    """Aggregated IVA compensation carry-forward balance as of a reference year."""

    model_config = _STRICT_FROZEN

    as_of_year: FilingYear
    total_balance: Decimal = Field(ge=Decimal("0"))
    active_balance: Decimal = Field(ge=Decimal("0"))
    expired_balance: Decimal = Field(ge=Decimal("0"))
    lot_count: NonNegativeInt
    next_expiry_year: CompensationExpiryYear | None = None
    unallocated_applied_amount: Decimal = Field(ge=Decimal("0"))


def build_iva_wallet_balance_report(
    carry_forward: IvaCompensationCarryForwardReport,
) -> IvaWalletBalanceReport:
    """Summarise a carry-forward report into a balance snapshot.

    ``total_balance`` is the gross remaining balance across all positive lots.
    ``active_balance`` is the portion still inside the statutory compensation
    window, including lots due for expiry review. ``expired_balance`` is the
    portion past that window and therefore not usable without separate review.

    ``next_expiry_year`` is the source filing year plus the configured carry
    window for the earliest non-expired lot that still carries a non-zero
    remaining balance. ``None`` when no non-expired lots
    with remaining balance exist.

    Returns an :class:`IvaWalletBalanceReport`.
    """
    active_lots_with_balance, expired_lots_with_balance = _partition_balance_lots(carry_forward)
    active_balance = _sum_lot_balances(active_lots_with_balance)
    expired_balance = _sum_lot_balances(expired_lots_with_balance)
    total_balance = active_balance + expired_balance

    return IvaWalletBalanceReport(
        as_of_year=carry_forward.as_of_year,
        total_balance=total_balance,
        active_balance=active_balance,
        expired_balance=expired_balance,
        lot_count=len(carry_forward.lots),
        next_expiry_year=_next_expiry_year(active_lots_with_balance),
        unallocated_applied_amount=carry_forward.unallocated_applied_amount,
    )


def _partition_balance_lots(
    carry_forward: IvaCompensationCarryForwardReport,
) -> tuple[list[IvaCompensationCarryForwardLot], list[IvaCompensationCarryForwardLot]]:
    lots_with_balance = [lot for lot in carry_forward.lots if lot.remaining_amount > Decimal("0")]
    expired_lots = [
        lot
        for lot in lots_with_balance
        if lot.expiry_review_state is IvaCompensationExpiryReviewState.EXPIRED_REVIEW_REQUIRED
    ]
    # Include ACTIVE and EXPIRY_REVIEW_DUE lots. EXPIRED_REVIEW_REQUIRED lots
    # have passed the statutory boundary and are not usable without a separate
    # policy review.
    active_lots = [
        lot
        for lot in lots_with_balance
        if lot.expiry_review_state is not IvaCompensationExpiryReviewState.EXPIRED_REVIEW_REQUIRED
    ]
    return active_lots, expired_lots


def _sum_lot_balances(lots: Iterable[IvaCompensationCarryForwardLot]) -> Decimal:
    return sum((lot.remaining_amount for lot in lots), Decimal("0"))


def _resolve_carry_window_years(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None = None,
) -> int:
    """Resolve the carry-window scalar through the validated registry authority."""
    if authority is None:
        from ..calculations.registry.authority import bundled_authority

        authority = bundled_authority()
    resolved = cast(
        "ResolvedScalarFact",
        authority.resolve_governed_fact(
            ScalarFactQuery(
                fact_id=_CARRY_WINDOW_FACT_ID,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=effective_date,
            ),
        ),
    )
    value = resolved.payload.value
    if isinstance(value, bool) or not isinstance(value, int):
        raise RegistryValidationError(
            f"IVA compensation carry-window fact {resolved.fact_id!r} resolved non-integer payload {value!r}",
        )
    return value


def _next_expiry_year(lots: Iterable[IvaCompensationCarryForwardLot]) -> int | None:
    lot_list = tuple(lots)
    if not lot_list:
        return None
    earliest_source_year = min(int(lot.source_filing_year) for lot in lot_list)
    carry_window_years = _resolve_carry_window_years(
        effective_date=date(earliest_source_year, 1, 1),
    )
    return min(int(lot.source_filing_year) + carry_window_years for lot in lot_list)


__all__ = [
    "IvaWalletBalanceReport",
    "build_iva_wallet_balance_report",
]
