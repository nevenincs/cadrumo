"""IVA compensation wallet balance summary for the aeat app modelo iva-wallet balance verb."""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from ._iva_compensation_history import (
    IvaCompensationCarryForwardReport,
    IvaCompensationExpiryReviewState,
    IvaCompensationHistoryRepository,
    build_iva_compensation_carry_forward_report,
)

_STRICT_FROZEN: Final = ConfigDict(strict=True, frozen=True, extra="forbid")
_FOUR_YEAR_WINDOW: Final[int] = 4


class IvaWalletBalanceReport(BaseModel):
    """Aggregated IVA compensation carry-forward balance as of a reference year."""

    model_config = _STRICT_FROZEN

    as_of_year: int = Field(ge=2000, le=2099)
    total_balance: Decimal = Field(ge=Decimal("0"))
    lot_count: int = Field(ge=0)
    next_expiry_year: int | None = Field(default=None, ge=2000, le=2200)
    unallocated_applied_amount: Decimal = Field(ge=Decimal("0"))


def build_iva_wallet_balance_report(
    carry_forward: IvaCompensationCarryForwardReport,
) -> IvaWalletBalanceReport:
    """Summarise a carry-forward report into a single-figure balance snapshot.

    ``next_expiry_year`` is ``source_filing_year + 4`` for the earliest
    ACTIVE lot that still carries a non-zero remaining balance (the lot
    closest to its four-year expiry boundary).  ``None`` when no ACTIVE
    lots with remaining balance exist.
    """

    # Include ACTIVE and EXPIRY_REVIEW_DUE lots (age <= 4) with remaining balance.
    # EXPIRED_REVIEW_REQUIRED lots (age > 4) are excluded — they have already passed
    # the four-year boundary and a policy decision is needed before they are usable.
    non_expired_lots_with_balance = [
        lot
        for lot in carry_forward.lots
        if lot.remaining_amount > Decimal("0")
        and lot.expiry_review_state is not IvaCompensationExpiryReviewState.EXPIRED_REVIEW_REQUIRED
    ]

    next_expiry_year: int | None = None
    if non_expired_lots_with_balance:
        next_expiry_year = min(
            lot.source_filing_year + _FOUR_YEAR_WINDOW for lot in non_expired_lots_with_balance
        )

    total_balance = sum(
        (lot.remaining_amount for lot in carry_forward.lots if lot.remaining_amount > Decimal("0")),
        Decimal("0"),
    )

    return IvaWalletBalanceReport(
        as_of_year=carry_forward.as_of_year,
        total_balance=total_balance,
        lot_count=len(carry_forward.lots),
        next_expiry_year=next_expiry_year,
        unallocated_applied_amount=carry_forward.unallocated_applied_amount,
    )


def query_iva_wallet_balance(*, as_of_year: int) -> IvaWalletBalanceReport:
    """Load all stored IVA compensation period states and return the balance report."""

    repo = IvaCompensationHistoryRepository()
    states = repo.list_periods()
    carry_forward = build_iva_compensation_carry_forward_report(states, as_of_year=as_of_year)
    return build_iva_wallet_balance_report(carry_forward)


__all__ = [
    "IvaWalletBalanceReport",
    "build_iva_wallet_balance_report",
    "query_iva_wallet_balance",
]
