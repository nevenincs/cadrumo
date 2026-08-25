"""Rebuild the transaction participation index from the revision catalogue.

The participation index is a derived, read-side cache co-written atomically with
revision persistence; the calculation-revision catalogue is the authoritative
source of truth. This module regenerates the index from scratch by iterating the
full finalized-revision catalogue, so a stale or corrupt index can be replaced
without data loss, in line with the
``aeat-ledger-contract`` project rule.

The rebuild reads the :class:`CalculationRevisionCatalogue` (the finalized
revisions and their ``source_transaction_ids``), the work-unit catalogue (for the
``modelo`` / ``filing_year`` / ``period`` axis per revision), and the
:class:`ModeloRecordCatalogue` / :class:`ModeloRecord` rows (to attach the
``filing_record_id`` and any justificante reference to filed participations).
Borrador and discarded revisions are excluded — the index records only the
finalized audit surface.

See Also:
    :class:`TransactionRevisionParticipationIndex`:
        Per-transaction secure object rebuilt by this module.
    :func:`cadrumo.application.modelo._verification_actions._build_participation_writes`:
        Write-time co-emission path that keeps the index current during
        verification persistence.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.identity import CalculationRevisionId
from ...domain.modelos import (
    CalculationRevisionCatalogueRepositoryProtocol,
    CalculationRevisionState,
    ExternalEvidence,
    ModeloRecord,
    ModeloRecordCatalogue,
    ModeloRecordCatalogueRepositoryProtocol,
    TransactionRevisionParticipation,
    TransactionRevisionParticipationIndex,
    upsert_transaction_participation,
)
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol

_FINALIZED_REVISION_STATES = frozenset(
    {
        CalculationRevisionState.VERIFICADO_COMPLETO,
        CalculationRevisionState.PRESENTADO,
        CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
    },
)


class ParticipationRebuildStats(BaseModel):
    """Outcome of one participation-index rebuild pass.

    Attributes:
        transaction_count: Number of distinct ledger transactions that gained at
            least one participation entry.
        participation_count: Total number of (transaction, finalized-revision)
            participation entries written across all transactions.
        revision_count: Number of finalized revisions folded into the index.
        stale_removed_count: Number of previously persisted participation objects
            removed because the regenerated catalogue no longer records them —
            the transactions whose finalized revisions were discarded, removed,
            or reverted to borrador since the last rebuild.
    """

    model_config = _STRICT_FROZEN

    transaction_count: int = Field(ge=0)
    participation_count: int = Field(ge=0)
    revision_count: int = Field(ge=0)
    stale_removed_count: int = Field(ge=0)


def _filing_record_for_revision(
    calculation_revision_id: CalculationRevisionId,
    filings: ModeloRecordCatalogue,
) -> ModeloRecord | None:
    """Return the filing record bound to ``calculation_revision_id``, if any."""
    for record in filings.records.values():
        if record.calculation_revision_id == calculation_revision_id:
            return record
    return None


def _justificante_reference(record: ModeloRecord | None) -> str | None:
    """Return the imported justificante reference from a filing record, if present."""
    evidence: ExternalEvidence | None = record.external_evidence if record is not None else None
    return evidence.reference_id if evidence is not None else None


def rebuild_participation_index(
    *,
    bucket_id: str | None = None,
    calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    work_unit_repository: WorkUnitCatalogueRepositoryProtocol | None = None,
    filing_repository: ModeloRecordCatalogueRepositoryProtocol | None = None,
    participation_index_repository: TransactionParticipationIndexRepository | None = None,
) -> ParticipationRebuildStats:
    """Regenerate the participation index from the finalized-revision catalogue.

    Iterates every finalized :class:`CalculationRevision`, resolves its
    ``modelo`` / ``filing_year`` / ``period`` from the work-unit catalogue and its
    ``filing_record_id`` from the filing-record catalogue, and writes one
    :class:`TransactionRevisionParticipationIndex` per contributing transaction.
    Borrador and discarded revisions are excluded.

    The regenerated set REPLACES the persisted index rather than being upserted
    over it: a transaction whose finalized revisions have since been discarded or
    removed contributes no entry here, and its stale secure object is pruned in
    the same atomic batch. Without that prune a removed revision would stay
    visible through the derived cache while the authoritative catalogue no longer
    records it. Returns a :class:`ParticipationRebuildStats` summary.
    """
    cr_repo = calculation_repository or CalculationRevisionCatalogueRepository(bucket_id=bucket_id)
    wu_repo = work_unit_repository or WorkUnitCatalogueRepository(bucket_id=bucket_id)
    fr_repo = filing_repository or ModeloRecordCatalogueRepository(bucket_id=bucket_id)
    participation_repo = participation_index_repository or TransactionParticipationIndexRepository(
        bucket_id=bucket_id,
    )

    revisions = cr_repo.load()
    work_units = wu_repo.load()
    filings = fr_repo.load()

    rebuilt: dict[str, TransactionRevisionParticipationIndex] = {}
    participation_count = 0
    revision_count = 0

    for revision in revisions.values():
        if revision.state not in _FINALIZED_REVISION_STATES:
            continue
        work_unit = work_units.get(revision.work_unit_id)
        if work_unit is None:
            continue
        revision_count += 1
        is_filed = revision.state in {
            CalculationRevisionState.PRESENTADO,
            CalculationRevisionState.PRESENTADO_SUPERSEDIDO,
        }
        filing_record = _filing_record_for_revision(revision.calculation_revision_id, filings) if is_filed else None
        participation = TransactionRevisionParticipation(
            calculation_revision_id=revision.calculation_revision_id,
            work_unit_id=work_unit.work_unit_id,
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            revision_state=revision.state.value,
            filing_record_id=filing_record.filing_record_id if filing_record is not None else None,
            justificante_reference=_justificante_reference(filing_record),
        )
        for transaction_id in revision.source_transaction_ids:
            current = rebuilt.get(transaction_id) or TransactionRevisionParticipationIndex(
                transaction_id=transaction_id,
            )
            rebuilt[transaction_id] = upsert_transaction_participation(current, participation)
            participation_count += 1

    stale_removed_count = participation_repo.replace_all(rebuilt.values())

    return ParticipationRebuildStats(
        transaction_count=len(rebuilt),
        participation_count=participation_count,
        revision_count=revision_count,
        stale_removed_count=stale_removed_count,
    )


__all__ = [
    "ParticipationRebuildStats",
    "rebuild_participation_index",
]
