"""Modelo 349 raw-ledger safety guard.

Modelo 349 operator rows require counterparty identity fields that raw ledger
transactions do not carry. The supported source paths are business invoices or
explicit operador detail rows, so raw intra-community ledger classifications must
fail closed instead of producing a zero-row declaration. The guard reads the
bucket transaction catalogue through
:class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository` only to detect
that refusal condition; it does not resolve registry binding values itself.
"""

from __future__ import annotations

from typing import NoReturn

from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core.modelo import Modelo
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...core.period import Period
from ...domain.iva.schema import IvaCategory
from ...domain.modelos.row_models import Modelo349OperadorRow, ModeloDetailRow
from ...domain.modelos.work_unit import WorkUnit
from ...domain.transactions.enums import TransactionLifecycleState
from ...domain.transactions.models import Transaction
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from .action_errors import ModeloAggregationBindingError
from .preconditions import build_modelo_precondition_failure

_M349_INTRACOM_LEDGER_CATEGORIES = frozenset(
    {
        IvaCategory.INTRA_COMMUNITY_SUPPLY,
        IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        IvaCategory.INTRA_COMMUNITY_TRIANGULATION,
    },
)


def _m349_requires_operator_rows(work_unit: WorkUnit, detail_rows: tuple[ModeloDetailRow, ...]) -> bool:
    """Return whether this work unit has no declarable M349 operator rows."""
    if str(work_unit.modelo) != Modelo.M349.value:
        return False
    return not any(isinstance(row, Modelo349OperadorRow) for row in detail_rows)


def _is_active_intracom_transaction_in_period(transaction: Transaction, period: Period) -> bool:
    """Return whether a transaction belongs to the guarded M349 ledger slice."""
    if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        return False
    if transaction.iva_category not in _M349_INTRACOM_LEDGER_CATEGORIES:
        return False
    return period.contains(transaction.raw.value_date or transaction.raw.booked_date)


def _m349_intracom_transaction_ids(
    repository: TransactionCatalogueRepositoryProtocol,
    period: Period,
) -> tuple[str, ...]:
    """Return active in-period intracom ledger ids in deterministic order."""
    return tuple(
        sorted(
            transaction.transaction_id
            for transaction in repository.load().transactions.values()
            if _is_active_intracom_transaction_in_period(transaction, period)
        ),
    )


def _raise_m349_operator_rows_refusal(work_unit: WorkUnit, transaction_ids: tuple[str, ...]) -> NoReturn:
    """Raise the grounded refusal for raw intracom ledger rows without operator rows."""
    raise ModeloAggregationBindingError(
        translated_message="errors.error.error_modelo_aggregation_binding",
        context={
            "modelo": Modelo.M349.value,
            "filing_year": work_unit.filing_year,
            "period": work_unit.period.registry_token,
            "transaction_count": len(transaction_ids),
            "sample_transaction_ids": transaction_ids[:3],
        },
        precondition_failure=build_modelo_precondition_failure(
            subject_leaf_key="modelo.work.calculate",
            condition_id="modelo.work.calculate.m349.operator_rows.present",
            scenario_id="modelo.work.calculate.m349.operator_rows.intracom_ledger_without_operator_rows",
            evidence_id="modelo.work.calculate.m349.operator_rows",
            evidence_values={
                "work_unit_id": work_unit.work_unit_id,
                "modelo": Modelo.M349.value,
                "year": work_unit.filing_year,
                "period": work_unit.period.registry_token,
                "transaction_count": len(transaction_ids),
                "sample_transaction_ids": "|".join(transaction_ids[:3]),
            },
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        ),
    )


def raise_if_m349_intracom_ledger_rows_need_operator_rows(
    *,
    work_unit: WorkUnit,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None,
    detail_rows: tuple[ModeloDetailRow, ...],
) -> None:
    """Refuse M349 calculation when raw ledger rows lack declarable operator rows."""
    if not _m349_requires_operator_rows(work_unit, detail_rows):
        return

    repository = transaction_repository or TransactionCatalogueRepository(bucket_id=work_unit.bucket_id)
    transaction_ids = _m349_intracom_transaction_ids(repository, work_unit.period)
    if not transaction_ids:
        return

    _raise_m349_operator_rows_refusal(work_unit, transaction_ids)


__all__ = ["raise_if_m349_intracom_ledger_rows_need_operator_rows"]
