"""Ledger date semantics: which dates a transaction can file an observation under.

A period-scoped ledger read has to decide, for one stored transaction,
whether it can contribute anything to a filing window. That question has two
answers and they are not the same date. Most rows file on their ledger
filing date, but an IVA criterio-de-caja row's devengo and collection dates
are set by law independently of when the movement was booked, so a row
booked in one quarter can carry an observation in another.

These are the single owners of both answers. The plaintext routing index
(:class:`~adapters.persistence.storage.sql.TransactionDateIndexRow`) records
what they return, and the period partition selects candidates by overlap
against the span rather than by equality against the filing date.

See Also:
    :class:`~domain.transactions.Transaction`
        Ledger row whose cash-accounting timing facts these read.
    :class:`~domain.transactions.LedgerDatePartition`
        Partition contract the eligible span feeds.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from ..iva.schema import IvaCashAccountingTreatment

if TYPE_CHECKING:  # pragma: no cover — typing-only import
    from .models import Transaction

__all__ = ["transaction_eligible_date_span", "transaction_filing_date"]


def transaction_filing_date(transaction: Transaction) -> date:
    """Return the ledger filing date: ``value_date`` when present, else ``booked_date``.

    This is the date every period-scoped ledger aggregator without a
    tax-timing override filters on, and the date the plaintext routing index
    records per transaction.
    """
    return transaction.raw.value_date or transaction.raw.booked_date


def transaction_eligible_date_span(transaction: Transaction) -> tuple[date, date]:
    """Return the inclusive ``(earliest, latest)`` span of every date this row can file under.

    A period-scoped read cannot select candidates on
    :func:`transaction_filing_date` alone. Under the IVA criterio de caja
    (LIVA art. 163 *decies* and following) one transaction produces
    observations on dates independent of its ledger filing date: the art. 75
    devengo ``operation_date``, each
    ``cash_accounting_payment_evidence`` collection date, and the 31 December
    statutory fallback of the year following the operation. A row booked in
    Q2 can therefore carry a Q1 observation, and selecting on the filing date
    alone drops it with no diagnostic.

    The span is a deliberately CONSERVATIVE superset: it always covers the
    filing date, and for a cash-accounting row it stretches to the statutory
    fallback date without re-deriving the settlement remainder arithmetic
    that decides whether that date actually carries a part. Over-selection
    costs one extra decrypt that the consuming aggregator's own date gate
    then rejects; under-selection is a silent under-declaration, so the
    asymmetry is resolved in favour of the wider span.

    Returns:
        The inclusive ``(earliest, latest)`` date span, both equal to the
        filing date for a row with no cash-accounting timing override.
    """
    filing_date = transaction_filing_date(transaction)
    operation_date = transaction.operation_date
    if operation_date is None:
        return filing_date, filing_date
    candidates = [filing_date, operation_date]
    if transaction.cash_accounting_treatment is not IvaCashAccountingTreatment.NONE:
        # Both extras are criterio-de-caja constructs and must not widen a
        # general-regime row. That row files on its art. 75 devengo date, full
        # stop: it settles in one movement, so there is no collection series
        # and no art. 163 quinquiesdecies year-end fallback to reach for.
        candidates.append(date(operation_date.year + 1, 12, 31))
        candidates.extend(evidence.payment_date for evidence in transaction.cash_accounting_payment_evidence)
    return min(candidates), max(candidates)
