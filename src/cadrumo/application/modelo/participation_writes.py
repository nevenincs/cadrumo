"""Co-emitted participation-index writes for one finalized calculation revision."""

from __future__ import annotations

from ...core.secure_object_write import SecureObjectWrite
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos.participation_index import TransactionRevisionParticipation, upsert_transaction_participation
from ...domain.modelos.protocols import TransactionParticipationIndexRepositoryProtocol
from ...domain.modelos.work_unit import WorkUnit


def build_participation_writes(
    *,
    revision: CalculationRevision,
    work_unit: WorkUnit,
    revision_state: CalculationRevisionState,
    filing_record_id: str | None = None,
    participation_index_repository: TransactionParticipationIndexRepositoryProtocol,
) -> tuple[SecureObjectWrite, ...]:
    """Return one index write per contributing transaction, for the caller to co-commit.

    Each transaction's participation for this revision is upserted, so the filed
    entry replaces the verified one in place. A revision with no contributing
    transactions yields no writes.
    """
    writes: list[SecureObjectWrite] = []
    for transaction_id in revision.source_transaction_ids:
        index = participation_index_repository.load(transaction_id)
        participation = TransactionRevisionParticipation(
            calculation_revision_id=revision.calculation_revision_id,
            work_unit_id=work_unit.work_unit_id,
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            revision_state=revision_state.value,
            filing_record_id=filing_record_id,
        )
        updated = upsert_transaction_participation(index, participation)
        writes.append(participation_index_repository.to_secure_object_write(updated))
    return tuple(writes)


__all__ = ["build_participation_writes"]
