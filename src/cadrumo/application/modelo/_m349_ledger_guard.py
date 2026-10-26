"""Modelo 349 raw-ledger safety guard.

Modelo 349 operator rows require counterparty identity fields that raw ledger
transactions do not carry. The supported source paths are business invoices or
explicit operador detail rows, so raw intra-community ledger classifications must
fail closed instead of producing a zero-row declaration.

The IVA categories that make a ledger row intra-community are not restated here:
the IVA category catalogue declares them as the ``m349_raw_ledger_guard``
projection (RIVA art. 79, Orden EHA/769/2010 art. 1).
"""

from __future__ import annotations

from typing import NoReturn

from ...core.modelo import Modelo
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...core.period import Period
from ...domain.calculations.registry.iva_category_catalogue import registry_category_projection
from ...domain.iva.schema import IvaCategory
from ...domain.modelos.row_models import Modelo349OperadorRow, ModeloDetailRow
from ...domain.modelos.work_unit import WorkUnit
from ...domain.transactions.enums import TransactionLifecycleState
from ...domain.transactions.models import Transaction
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from .action_errors import ModeloAggregationBindingError
from .preconditions import build_modelo_precondition_failure


def _guarded_ledger_categories(work_unit: WorkUnit) -> frozenset[IvaCategory]:
    """Return the intra-community IVA categories guarded for a Modelo 349 work unit."""
    if str(work_unit.modelo) != Modelo("349").value:
        return frozenset[IvaCategory]()
    return registry_category_projection("m349_raw_ledger_guard", effective_date=work_unit.period.end_date)


def _is_active_guarded_transaction_in_period(
    transaction: Transaction,
    period: Period,
    categories: frozenset[IvaCategory],
) -> bool:
    """Return whether a transaction belongs to the guarded M349 ledger slice."""
    if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        return False
    if transaction.iva_category not in categories:
        return False
    return period.contains(transaction.raw.value_date or transaction.raw.booked_date)


def _raise_m349_operator_rows_refusal(work_unit: WorkUnit, transaction_ids: tuple[str, ...]) -> NoReturn:
    """Raise the grounded refusal for raw intracom ledger rows without operator rows."""
    modelo = str(work_unit.modelo)
    raise ModeloAggregationBindingError(
        translated_message="errors.error.error_modelo_aggregation_binding",
        context={
            "modelo": modelo,
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
                "modelo": modelo,
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
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    detail_rows: tuple[ModeloDetailRow, ...],
) -> None:
    """Refuse M349 calculation when raw ledger rows lack declarable operator rows."""
    if any(isinstance(row, Modelo349OperadorRow) for row in detail_rows):
        return
    categories = _guarded_ledger_categories(work_unit)
    if not categories:
        return
    transaction_ids = tuple(
        sorted(
            transaction.transaction_id
            for transaction in transaction_repository.load().transactions.values()
            if _is_active_guarded_transaction_in_period(transaction, work_unit.period, categories)
        ),
    )
    if transaction_ids:
        _raise_m349_operator_rows_refusal(work_unit, transaction_ids)


__all__ = ["raise_if_m349_intracom_ledger_rows_need_operator_rows"]
