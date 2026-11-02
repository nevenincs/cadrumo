"""Write-boundary check that a foreign-currency row's euro value follows its rate."""

from __future__ import annotations

from ...core.money.rounding import CENT, round_to_cents
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.models import Transaction

FX_VALUE_TOLERANCE = CENT
"""Largest admitted gap between the stored euro value and the rounded product."""


def require_consistent_fx_value(transaction: Transaction) -> None:
    """Refuse a new or edited row whose ``value_in_eur`` is not ``amount * fx_rate``.

    Both sides are non-negative magnitudes: flow direction lives on the row's
    ``direction`` field. The
    expected figure is the half-up cent rounding of the product, and a gap of
    at most one cent is admitted. Rows without a rate pair (EUR-native or no
    rate available) have nothing to compare. This runs on writes only; stored
    rows are never re-checked on load.
    """
    if transaction.fx_rate is None or transaction.value_in_eur is None:
        return
    expected = round_to_cents(transaction.raw.amount * transaction.fx_rate)
    gap = abs(expected - transaction.value_in_eur)
    if gap <= FX_VALUE_TOLERANCE:
        return
    raise TransactionValidationError(
        "value_in_eur must equal amount * fx_rate rounded to the cent (one cent tolerance): "
        f"expected {expected}, got {transaction.value_in_eur}",
        translated_message="application.ledger.errors.fx_value_inconsistent",
        context={
            "currency": transaction.raw.currency,
            "expected_value_in_eur": str(expected),
            "value_in_eur": str(transaction.value_in_eur),
            "fx_rate": str(transaction.fx_rate),
            "transaction_id": transaction.transaction_id,
        },
    )
