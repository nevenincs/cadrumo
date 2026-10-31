"""Run one ledger row through the real IVA ledger classifier."""

from __future__ import annotations

from collections.abc import Sequence

from ....core.period import Period
from ....domain.calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from ....domain.transactions.models import Transaction, TransactionCatalogue
from .iva_authority_support import aggregate_iva_ledger_observations


def aggregate_row(transaction: Transaction, period: Period) -> tuple[Sequence[IvaLedgerObservation], list[str]]:
    """Return the observations the classifier produced and the reasons it refused rows."""
    catalogue = TransactionCatalogue.model_validate({"transactions": {transaction.transaction_id: transaction}})
    aggregation = aggregate_iva_ledger_observations(catalogue, period=period)
    return aggregation.observations, [issue.reason.value for issue in aggregation.issues]
