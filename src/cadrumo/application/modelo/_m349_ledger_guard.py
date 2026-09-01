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

from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core.modelo import Modelo
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.iva.schema import IvaCategory
from ...domain.modelos.row_models import Modelo349OperadorRow, ModeloDetailRow
from ...domain.modelos.work_unit import WorkUnit
from ...domain.transactions.enums import TransactionLifecycleState
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
    period = work_unit.period
    transaction_ids = tuple(
        sorted(
            transaction.transaction_id
            for transaction in repository.load().transactions.values()
            if transaction.lifecycle_state is TransactionLifecycleState.ACTIVE
            and transaction.iva_category in _M349_INTRACOM_LEDGER_CATEGORIES
            and period.contains(transaction.raw.value_date or transaction.raw.booked_date)
        ),
    )
    if not transaction_ids:
        return

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


__all__ = ["raise_if_m349_intracom_ledger_rows_need_operator_rows"]
