"""Check an asset revision's acquisition against the ledger transaction it names."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from ...core.external_constants import DEFAULT_CURRENCY
from ...domain.renta.actividad_asset.errors import ActividadAssetValidationError
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.transactions.enums import TransactionDirection
from ...domain.transactions.models import Transaction
from .ports import AcquisitionLedgerReader


def require_acquisition_in_ledger(
    revision: ActivityAssetRevision, ledger: AcquisitionLedgerReader
) -> Transaction | None:
    """Refuse a revision whose acquisition the ledger does not bear out.

    Every row the revision owns must exist and be a payment.  The cost the basis
    states, price plus non-deductible IVA, cannot exceed what those rows paid
    together, and the price and the non-deductible IVA cannot exceed the base and
    the IVA they declare, when every row states one in EUR.  The comparisons are
    bounds, not equalities: a row can pay for more than one thing, and a
    business-allocated basis is already reduced to the taxpayer's share.  The
    basis stays the register's; the rows only reconcile against it.

    An element acquired outside the ledger has no primary row.  Rows it owns, such as a later
    instalment, must still exist and be payments, but the basis includes what was paid outside
    the ledger, so neither bound applies.

    Returns:
        The primary acquisition transaction, or ``None`` when the element owns none.

    Raises:
        ActividadAssetValidationError: When a transaction is absent, is not a
            payment, has no EUR amount, or the rows are smaller than the stated cost.
    """
    owned = revision.acquisition_transaction_ids
    if not owned:
        return None
    transactions = _acquisition_payments(revision, ledger)
    if revision.acquisition.observed_transaction_id is None:
        return None
    basis = revision.basis
    paid = sum((_paid_in_euro(transaction) for transaction in transactions), Decimal("0"))
    if basis.acquisition_cost() > paid:
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.acquisition_cost_exceeds_payment",
            context=_context(
                cost=basis.acquisition_cost(),
                price=basis.basis_amount,
                non_deductible_iva=basis.non_deductible_iva,
                paid=paid,
            ),
        )
    primary = transactions[0]
    _require_declared_bounds(revision, transactions)
    return primary


def _require_declared_bounds(revision: ActivityAssetRevision, transactions: list[Transaction]) -> None:
    if any(transaction.raw.currency != DEFAULT_CURRENCY for transaction in transactions):
        return
    basis = revision.basis
    taxable_base = _declared_total(transaction.taxable_base for transaction in transactions)
    if taxable_base is not None and basis.basis_amount > taxable_base:
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.acquisition_price_exceeds_base",
            context=_context(price=basis.basis_amount, taxable_base=taxable_base),
        )
    iva_amount = _declared_total(transaction.iva_amount for transaction in transactions)
    if iva_amount is not None and basis.non_deductible_iva > iva_amount:
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.acquisition_iva_exceeds_transaction_iva",
            context=_context(non_deductible_iva=basis.non_deductible_iva, iva_amount=iva_amount),
        )


def _acquisition_payments(revision: ActivityAssetRevision, ledger: AcquisitionLedgerReader) -> list[Transaction]:
    owned = revision.acquisition_transaction_ids
    found = ledger.load_by_ids(owned).transactions
    transactions: list[Transaction] = []
    for transaction_id in owned:
        transaction = found.get(transaction_id)
        if transaction is None:
            raise ActividadAssetValidationError(
                translated_message="ledger.actividad_asset.errors.acquisition_transaction_missing",
                context=_context(transaction_id=transaction_id),
            )
        if transaction.direction is not TransactionDirection.OUTGOING:
            raise ActividadAssetValidationError(
                translated_message="ledger.actividad_asset.errors.acquisition_transaction_not_payment",
                context=_context(transaction_id=transaction_id),
            )
        transactions.append(transaction)
    return transactions


def _declared_total(amounts: Iterable[Decimal | None]) -> Decimal | None:
    """Add what the rows declare; one silent row leaves the total unknown, so no bound applies."""
    declared = tuple(amounts)
    if any(amount is None for amount in declared):
        return None
    return sum((amount for amount in declared if amount is not None), Decimal("0"))


def _context(**values: object) -> dict[str, object]:
    return values


def _paid_in_euro(transaction: Transaction) -> Decimal:
    if transaction.raw.currency == DEFAULT_CURRENCY:
        return transaction.raw.amount
    if transaction.value_in_eur is None:
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.acquisition_currency_unconverted",
            context=_context(currency=transaction.raw.currency),
        )
    return transaction.value_in_eur


__all__ = ["require_acquisition_in_ledger"]
