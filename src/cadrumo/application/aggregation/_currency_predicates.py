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
from ...domain.transactions.models import Transaction
from .errors import AggregationConfigError, t


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

    Raises :class:`~..errors.AggregationConfigError` when
    ``is_non_eur_without_conversion`` is ``True`` for the row, rather than
    documenting the precondition and trusting every caller to check it first.
    An unconverted foreign-currency row has no valid EUR projection to
    return, and a caller that skipped the gate must fail loud, not fold
    ``raw.amount`` into a EUR-denominated total in a foreign currency.

    Args:
        transaction: The transaction whose effective EUR amount is needed.

    Returns:
        A :class:`decimal.Decimal` suitable for casilla arithmetic.

    Raises:
        AggregationConfigError: The row is foreign-currency with no EUR
            conversion applied.
    """
    if is_non_eur_without_conversion(transaction):
        raise AggregationConfigError(
            translated_message=t("aggregation.service.errors.currency_conversion_required"),
            context={
                "transaction_id": transaction.transaction_id,
                "currency": transaction.raw.currency,
            },
        )
    if transaction.value_in_eur is not None:
        return transaction.value_in_eur
    return transaction.raw.amount


def effective_eur_taxable_base(transaction: Transaction) -> Decimal | None:
    """Return the EUR-equivalent ``taxable_base``, or ``None`` if unset.

    ``transaction.taxable_base`` is denominated in the row's NATIVE currency
    (the ``gross == base + iva + recargo`` invariant reconstitutes
    ``raw.amount``, never ``value_in_eur`` -- see
    ``domain.transactions.tests.test_gross_invariant``). A converted
    foreign-currency row must apply the same ``fx_rate`` multiplier import
    used to derive ``value_in_eur`` from ``raw.amount``
    (``raw.amount * fx_rate == value_in_eur``), so the base cannot be summed
    as EUR while still carrying its native-currency figure.

    Raises the same way ``effective_eur_amount`` does when the row is
    foreign-currency with no conversion applied.

    Args:
        transaction: The transaction whose EUR-equivalent taxable base is needed.

    Returns:
        A :class:`decimal.Decimal`, or ``None`` when ``taxable_base`` is unset.

    Raises:
        AggregationConfigError: The row is foreign-currency with no EUR
            conversion applied.
    """
    if transaction.taxable_base is None:
        return None
    if is_non_eur_without_conversion(transaction):
        raise AggregationConfigError(
            translated_message=t("aggregation.service.errors.currency_conversion_required"),
            context={
                "transaction_id": transaction.transaction_id,
                "currency": transaction.raw.currency,
            },
        )
    if transaction.fx_rate is not None:
        return transaction.taxable_base * transaction.fx_rate
    return transaction.taxable_base


def effective_eur_iva_amount(transaction: Transaction) -> Decimal | None:
    """Return the EUR-equivalent ``iva_amount``, or ``None`` if unset.

    Same native-currency contract and ``fx_rate`` conversion as
    :func:`effective_eur_taxable_base`, applied to ``iva_amount``.

    Args:
        transaction: The transaction whose EUR-equivalent IVA amount is needed.

    Returns:
        A :class:`decimal.Decimal`, or ``None`` when ``iva_amount`` is unset.

    Raises:
        AggregationConfigError: The row is foreign-currency with no EUR
            conversion applied.
    """
    if transaction.iva_amount is None:
        return None
    if is_non_eur_without_conversion(transaction):
        raise AggregationConfigError(
            translated_message=t("aggregation.service.errors.currency_conversion_required"),
            context={
                "transaction_id": transaction.transaction_id,
                "currency": transaction.raw.currency,
            },
        )
    if transaction.fx_rate is not None:
        return transaction.iva_amount * transaction.fx_rate
    return transaction.iva_amount


__all__ = [
    "effective_eur_amount",
    "effective_eur_iva_amount",
    "effective_eur_taxable_base",
    "is_non_eur_without_conversion",
]
