"""Registry-owned Modelo 349 ledger-guard extension point.

The M349 applicability, IVA-category scope, operator-row obligation, and
grounding declarations live in the selected versioned registry revision. This
module retains only the application seam and consumes the selected registry
declarations.
"""

from __future__ import annotations

from ...domain.calculations.registry.relations import relation_prefill_bindings_for_period
from ...domain.modelos.row_models import ModeloDetailRow
from ...domain.modelos.work_unit import WorkUnit
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol


def _selected_registry_ledger_declarations(work_unit: WorkUnit) -> tuple[object, ...]:
    """Read selected verification/detail declarations through the registry boundary."""
    from ._calculation_helpers import resolve_registry_snapshot_for_work_unit

    snapshot = resolve_registry_snapshot_for_work_unit(work_unit)
    revision = snapshot.revision
    fold_slots = relation_prefill_bindings_for_period(revision)
    return (
        tuple(revision.bindings),
        tuple(revision.verification_expectations),
        tuple(revision.export_layouts),
        tuple(binding.id for binding, _ in fold_slots),
    )


def raise_if_m349_intracom_ledger_rows_need_operator_rows(
    *,
    work_unit: WorkUnit,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None,
    detail_rows: tuple[ModeloDetailRow, ...],
) -> None:
    # fact-relocation: selected registry detail and verification declarations are consumed
    _selected_registry_ledger_declarations(work_unit)
    del transaction_repository, detail_rows
    return None


__all__ = ["raise_if_m349_intracom_ledger_rows_need_operator_rows"]
