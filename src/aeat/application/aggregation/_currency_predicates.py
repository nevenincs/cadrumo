"""Shared currency predicates for aggregation gates.

Used by :mod:`~._iva_ledger`, :mod:`~._renta_ledger`,
:mod:`~._renta_income_ledger`, and :mod:`~._renta_gasto_ledger` to gate
non-EUR rows and extract effective EUR amounts.

Provides two predicates that replace independent
``if transaction.raw.currency != "EUR": ...`` guards.
"""

from __future__ import annotations

from decimal import Decimal

from ...core.external_constants import DEFAULT_CURRENCY
from ...domain.transactions import Transaction


def is_non_eur_without_conversion(transaction: Transaction) -> bool:
    """Return whether a transaction is foreign-currency with no pre-converted EUR value.

    Returns ``True`` only when both conditions hold:
    - the raw currency is not EUR, AND
    - ``value_in_eur`` is ``None`` (no conversion was applied at import).

    Aggregation gates use this predicate to decide whether to emit
    ``UNSUPPORTED_CURRENCY``.  A non-EUR row with ``value_in_eur`` set
    can proceed through the gate using the pre-converted amount.

    Args:
        transaction: The transaction to inspect.

    Returns:
        ``True`` if the currency is foreign and no EUR equivalent is available.
    """
    return transaction.raw.currency != DEFAULT_CURRENCY and transaction.value_in_eur is None


def effective_eur_amount(transaction: Transaction) -> Decimal:
    """Return the EUR amount to use for this transaction in casilla projections.

    Returns ``transaction.value_in_eur`` for foreign-currency rows whose
    conversion was pre-applied at import; otherwise returns
    ``transaction.raw.amount`` (the native EUR amount for domestic rows).

    Note: callers are responsible for ensuring ``is_non_eur_without_conversion``
    returns ``False`` before calling this function.  An unconverted
    foreign-currency row would return ``raw.amount`` in a foreign currency,
    which is not a valid EUR projection.

    Args:
        transaction: The transaction whose effective EUR amount is needed.

    Returns:
        A :class:`decimal.Decimal` suitable for casilla arithmetic.
    """
    if transaction.value_in_eur is not None:
        return transaction.value_in_eur
    return transaction.raw.amount


__all__ = [
    "effective_eur_amount",
    "is_non_eur_without_conversion",
]
