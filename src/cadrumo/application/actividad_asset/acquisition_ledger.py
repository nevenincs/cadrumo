"""Check an asset revision's acquisition against the ledger transaction it names."""

from __future__ import annotations

from decimal import Decimal

from ...core.external_constants import DEFAULT_CURRENCY
from ...domain.renta.actividad_asset.errors import ActividadAssetValidationError
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.transactions.enums import TransactionDirection
from ...domain.transactions.models import Transaction
from .ports import AcquisitionLedgerReader


def require_acquisition_in_ledger(revision: ActivityAssetRevision, ledger: AcquisitionLedgerReader) -> Transaction:
    """Refuse a revision whose acquisition the ledger does not bear out.

    The observed transaction must exist and be a payment.  The cost the basis
    states, price plus non-deductible IVA, cannot exceed what the transaction
    paid, and the price and the non-deductible IVA cannot exceed the base and
    the IVA the row itself declares.  The comparisons are bounds, not
    equalities: a row can pay for more than one thing, and a business-allocated
    basis is already reduced to the taxpayer's share.

    Returns:
        The acquisition transaction.

    Raises:
        ActividadAssetValidationError: When the transaction is absent, is not a
            payment, has no EUR amount, or is smaller than the stated cost.
    """
    transaction_id = revision.acquisition.observed_transaction_id
    transaction = ledger.load_by_ids((transaction_id,)).transactions.get(transaction_id)
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
    basis = revision.basis
    paid = _paid_in_euro(transaction)
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
    if transaction.raw.currency != DEFAULT_CURRENCY:
        return transaction
    if transaction.taxable_base is not None and basis.basis_amount > transaction.taxable_base:
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.acquisition_price_exceeds_base",
            context=_context(price=basis.basis_amount, taxable_base=transaction.taxable_base),
        )
    if transaction.iva_amount is not None and basis.non_deductible_iva > transaction.iva_amount:
        raise ActividadAssetValidationError(
            translated_message="ledger.actividad_asset.errors.acquisition_iva_exceeds_transaction_iva",
            context=_context(non_deductible_iva=basis.non_deductible_iva, iva_amount=transaction.iva_amount),
        )
    return transaction


def _context(**values: object) -> dict[str, str]:
    return {name: str(value) for name, value in values.items()}


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
