"""Pure IVA-compensation wallet balance projection for Modelo 303.

Summarises a :class:`IvaCompensationCarryForwardReport` into a balance snapshot.
All logic here is pure: it depends only on :mod:`decimal`, pydantic,
:data:`STRICT_FROZEN_CONFIG`-style strict config, and the sibling carry-forward
records. The repository-backed orchestration that loads stored period states and
builds the report lives in the application layer.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Final

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.filing_year import FilingYear
from .carry_forward import (
    IvaCompensationCarryForwardReport,
    IvaCompensationExpiryReviewState,
)

_FOUR_YEAR_WINDOW: Final[int] = 4


CompensationExpiryYear = Annotated[int, Field(ge=2000, le=2200)]
"""The year an unused compensation lot lapses.

Deliberately wider than :obj:`~cadrumo.core.filing_year.FilingYear`. This is a
DERIVED year -- ``source_filing_year + 4`` for the earliest still-active lot --
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
    lot_count: int = Field(ge=0)
    next_expiry_year: CompensationExpiryYear | None = None
    unallocated_applied_amount: Decimal = Field(ge=Decimal("0"))


def build_iva_wallet_balance_report(
    carry_forward: IvaCompensationCarryForwardReport,
) -> IvaWalletBalanceReport:
    """Summarise a carry-forward report into a balance snapshot.

    ``total_balance`` is the gross remaining balance across all positive lots.
    ``active_balance`` is the portion still inside the four-year compensation
    window, including lots due for expiry review. ``expired_balance`` is the
    portion past that window and therefore not usable without separate review.

    ``next_expiry_year`` is ``source_filing_year + 4`` for the earliest
    non-expired lot that still carries a non-zero remaining balance (the lot
    closest to its four-year expiry boundary). ``None`` when no non-expired lots
    with remaining balance exist.

    Returns an :class:`IvaWalletBalanceReport`.
    """
    lots_with_balance = [lot for lot in carry_forward.lots if lot.remaining_amount > Decimal("0")]
    expired_lots_with_balance = [
        lot
        for lot in lots_with_balance
        if lot.expiry_review_state is IvaCompensationExpiryReviewState.EXPIRED_REVIEW_REQUIRED
    ]
    # Include ACTIVE and EXPIRY_REVIEW_DUE lots (age <= 4). EXPIRED_REVIEW_REQUIRED
    # lots (age > 4) have passed the four-year boundary and are not usable without
    # a separate policy review.
    active_lots_with_balance = [
        lot
        for lot in lots_with_balance
        if lot.expiry_review_state is not IvaCompensationExpiryReviewState.EXPIRED_REVIEW_REQUIRED
    ]

    next_expiry_year: int | None = None
    if active_lots_with_balance:
        next_expiry_year = min(lot.source_filing_year + _FOUR_YEAR_WINDOW for lot in active_lots_with_balance)

    active_balance = sum((lot.remaining_amount for lot in active_lots_with_balance), Decimal("0"))
    expired_balance = sum((lot.remaining_amount for lot in expired_lots_with_balance), Decimal("0"))
    total_balance = active_balance + expired_balance

    return IvaWalletBalanceReport(
        as_of_year=carry_forward.as_of_year,
        total_balance=total_balance,
        active_balance=active_balance,
        expired_balance=expired_balance,
        lot_count=len(carry_forward.lots),
        next_expiry_year=next_expiry_year,
        unallocated_applied_amount=carry_forward.unallocated_applied_amount,
    )


__all__ = [
    "IvaWalletBalanceReport",
    "build_iva_wallet_balance_report",
]
