"""Modelo 349 raw-ledger safety guard.

Modelo 349 operator rows require counterparty identity fields that raw ledger
transactions do not carry. The supported source paths are business invoices or
explicit operador detail rows, so raw intra-community ledger classifications must
fail closed instead of producing a zero-row declaration. The guard reads the
bucket transaction catalogue through
:class:`~aeat.domain.transactions.TransactionCatalogueRepository` only to detect
that refusal condition; it does not resolve registry binding values itself.
"""

from __future__ import annotations

from ...core import Modelo
from ...domain.iva import IvaCategory
from ...domain.modelos import Modelo349OperadorRow, ModeloDetailRow, WorkUnit
from ...domain.period import period_end_date, period_start_date
from ...domain.transactions import (
    TransactionCatalogueRepository,
    TransactionCatalogueRepositoryProtocol,
    TransactionLifecycleState,
)
from ._action_errors import ModeloAggregationBindingError

_M349_INTRACOM_LEDGER_CATEGORIES = frozenset(
    {
        IvaCategory.INTRA_COMMUNITY_SUPPLY,
        IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        IvaCategory.INTRA_COMMUNITY_TRIANGULATION,
    },
)


def raise_if_m349_intracom_ledger_rows_need_operator_rows(
    *,
    work_unit: WorkUnit,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None,
    detail_rows: tuple[ModeloDetailRow, ...],
) -> None:
    """Refuse M349 calculation when raw ledger rows lack declarable operator rows."""
    if str(work_unit.modelo) != Modelo.M349.value:
        return
    if any(isinstance(row, Modelo349OperadorRow) for row in detail_rows):
        return

    repository = transaction_repository or TransactionCatalogueRepository(bucket_id=work_unit.bucket_id)
    period_start = period_start_date(work_unit.filing_year, work_unit.period.registry_token)
    period_end = period_end_date(work_unit.filing_year, work_unit.period.registry_token)
    transaction_ids = tuple(
        sorted(
            transaction.transaction_id
            for transaction in repository.load().transactions.values()
            if transaction.lifecycle_state is TransactionLifecycleState.ACTIVE
            and transaction.iva_category in _M349_INTRACOM_LEDGER_CATEGORIES
            and period_start <= (transaction.raw.value_date or transaction.raw.booked_date) <= period_end
        ),
    )
    if not transaction_ids:
        return

    raise ModeloAggregationBindingError(
        "Modelo 349 calculation found intra-community ledger transactions, but no declarable operator rows "
        "were available. Raw ledger classifications cannot safely produce Modelo 349 operator records; add "
        "business invoices or pass operador detail rows with country, VAT number, legal name, clave, and amount.",
        context={
            "modelo": Modelo.M349.value,
            "filing_year": work_unit.filing_year,
            "period": work_unit.period.registry_token,
            "transaction_count": len(transaction_ids),
            "sample_transaction_ids": transaction_ids[:3],
        },
        suggestion="aeat app ledger invoice add --help",
    )


__all__ = ["raise_if_m349_intracom_ledger_rows_need_operator_rows"]
