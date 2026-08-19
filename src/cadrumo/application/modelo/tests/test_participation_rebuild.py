"""Rebuild the participation index from a real finalized-revision catalogue.

Seeds a calculation-revision catalogue with finalized revisions (verified and
filed) plus a borrador, persisted through the real encrypted repositories, runs
``rebuild_participation_index``, and asserts every finalized revision's
``source_transaction_ids`` land in the rebuilt index while the borrador is
excluded and filed revisions carry their ``filing_record_id``. No mocks — the
rebuild reads the same encrypted catalogues the production write path persists.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.participation_index import TransactionParticipationIndexRepository
from ....core import CasillaId, Period, validated_casilla_id
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ModeloCode,
    ModeloRecord,
    ModeloRecordStatus,
    TransactionRevisionParticipation,
    TransactionRevisionParticipationIndex,
    WorkUnit,
    derive_calculation_revision_id,
    derive_filing_record_id,
    derive_work_unit_id,
    upsert_calculation_revision,
    upsert_filing_record,
    upsert_transaction_participation,
    upsert_work_unit,
)
from ....tests.secure_sql import isolated_runtime_profile
from .._participation_index_rebuild import rebuild_participation_index

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "1cfbce2c-6cf7-43fe-a1a0-60c2e44cd95b"  # was 'modelo-participation-rebuild'
_T0 = datetime(2024, 7, 1, 9, 0, 0, tzinfo=UTC)

_TX_FILED = "1" * 64
_TX_VERIFIED = "2" * 64
_TX_BORRADOR = "3" * 64
_TX_SHARED = "4" * 64  # touched by both the filed and the verified revision
_IVA_BASE_IMPONIBLE_CASILLA: CasillaId = validated_casilla_id(
    "iva.base-imponible",
    surface="_IVA_BASE_IMPONIBLE_CASILLA",
)


def _work_unit(*, modelo: str, period: str, revision_seed: str) -> WorkUnit:
    typed_period = Period.from_year_and_code(2024, period)
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=2024,
        period=typed_period,
        revision_id=revision_seed,
    )
    return WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(modelo),
        filing_year=2024,
        period=typed_period,
        revision_id=revision_seed,
        name=f"{modelo}-2024-{period}",
        created_at=_T0,
        updated_at=_T0,
    )


def _revision(*, work_unit: WorkUnit, state: CalculationRevisionState, txids: tuple[str, ...]) -> CalculationRevision:
    inputs = {_IVA_BASE_IMPONIBLE_CASILLA: "1000.00"}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id=inputs,
        binding_overrides={},
        casilla_values={},
        source_transaction_ids=txids,
        filing_instance_evidence=None,
    )
    verified_at: datetime | None = None
    verified_by: str | None = None
    filed_at: datetime | None = None
    filed_by: str | None = None
    if state in {CalculationRevisionState.VERIFICADO_COMPLETO, CalculationRevisionState.PRESENTADO}:
        verified_at = _T0 + timedelta(hours=1)
        verified_by = "aeat.cli.modelo.verify"
    if state is CalculationRevisionState.PRESENTADO:
        filed_at = _T0 + timedelta(hours=2)
        filed_by = "aeat.cli.modelo.file"
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=state,
        input_values_by_casilla_id=inputs,
        source_transaction_ids=txids,
        created_at=_T0,
        updated_at=_T0 + timedelta(hours=2),
        verified_at=verified_at,
        verified_by=verified_by,
        filed_at=filed_at,
        filed_by=filed_by,
        filing_instance_evidence=None,
    )


def test_rebuild_includes_finalized_excludes_borrador_and_carries_filing_record(tmp_path: Path) -> None:
    """Rebuild folds every finalized revision in, drops borrador, carries filing_record_id."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        cr_repo = CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID)
        wu_repo = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID)
        fr_repo = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_ID)

        filed_wu = _work_unit(modelo="303", period="1T", revision_seed="303")
        verified_wu = _work_unit(modelo="130", period="2T", revision_seed="130")
        borrador_wu = _work_unit(modelo="303", period="3T", revision_seed="303b")

        filed_rev = _revision(
            work_unit=filed_wu,
            state=CalculationRevisionState.PRESENTADO,
            txids=(_TX_FILED, _TX_SHARED),
        )
        verified_rev = _revision(
            work_unit=verified_wu,
            state=CalculationRevisionState.VERIFICADO_COMPLETO,
            txids=(_TX_VERIFIED, _TX_SHARED),
        )
        borrador_rev = _revision(
            work_unit=borrador_wu,
            state=CalculationRevisionState.BORRADOR,
            txids=(_TX_BORRADOR,),
        )

        work_units = wu_repo.load()
        for wu in (filed_wu, verified_wu, borrador_wu):
            work_units = upsert_work_unit(work_units, wu)
        wu_repo.save(work_units)

        revisions = cr_repo.load()
        for rev in (filed_rev, verified_rev, borrador_rev):
            revisions = upsert_calculation_revision(revisions, rev)
        cr_repo.save(revisions)

        # A filing record bound to the filed revision so rebuild can attach filing_record_id.
        filing_id = derive_filing_record_id(
            work_unit_id=filed_wu.work_unit_id,
            calculation_revision_id=filed_rev.calculation_revision_id,
            filed_by="aeat.cli.modelo.file",
        )
        filing_record = ModeloRecord(
            filing_record_id=filing_id,
            work_unit_id=filed_wu.work_unit_id,
            calculation_revision_id=filed_rev.calculation_revision_id,
            bucket_id=_BUCKET_ID,
            modelo=ModeloCode("303"),
            filing_year=2024,
            period=Period.from_year_and_code(2024, "1T"),
            filed_at=_T0 + timedelta(hours=2),
            filed_by="aeat.cli.modelo.file",
            status=ModeloRecordStatus.VIGENTE,
        )
        fr_repo.save(upsert_filing_record(fr_repo.load(), filing_record))

        stats = rebuild_participation_index(bucket_id=_BUCKET_ID)

        participation_repo = TransactionParticipationIndexRepository(bucket_id=_BUCKET_ID)
        index_filed = participation_repo.load(_TX_FILED)
        index_verified = participation_repo.load(_TX_VERIFIED)
        index_borrador = participation_repo.load(_TX_BORRADOR)
        index_shared = participation_repo.load(_TX_SHARED)

    # Two finalized revisions folded in (borrador excluded).
    assert stats.revision_count == 2
    # Four transaction objects gained at least one entry: filed, verified, shared (borrador excluded).
    assert stats.transaction_count == 3
    # filed(2 tx) + verified(2 tx) = 4 participation entries.
    assert stats.participation_count == 4

    # Borrador transaction has no entry.
    assert index_borrador.participations == ()

    # Filed revision entry carries filing_record_id.
    (filed_entry,) = index_filed.participations
    assert filed_entry.revision_state == "presentado"
    assert filed_entry.filing_record_id == filing_id

    # Verified revision entry has no filing_record_id.
    (verified_entry,) = index_verified.participations
    assert verified_entry.revision_state == "verificado_completo"
    assert verified_entry.filing_record_id is None

    # Shared transaction carries BOTH revisions' participations.
    shared_revisions = {p.calculation_revision_id for p in index_shared.participations}
    assert shared_revisions == {filed_rev.calculation_revision_id, verified_rev.calculation_revision_id}


def test_rebuild_on_empty_catalogue_writes_nothing(tmp_path: Path) -> None:
    """An empty revision catalogue rebuilds to zero participations."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        stats = rebuild_participation_index(bucket_id=_BUCKET_ID)

    assert stats.revision_count == 0
    assert stats.transaction_count == 0
    assert stats.participation_count == 0
    assert stats.stale_removed_count == 0


def test_rebuild_prunes_participation_absent_from_the_regenerated_catalogue(tmp_path: Path) -> None:
    """A persisted entry the catalogue no longer records is removed, not left readable.

    The index is a derived cache over the finalized-revision catalogue, so a
    rebuild must REPLACE rather than upsert: an entry whose revision has since
    been discarded has no regenerated row, and leaving its secure object in place
    would keep surfacing a participation the authority dropped.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        participation_repo = TransactionParticipationIndexRepository(bucket_id=_BUCKET_ID)

        # A genuine persisted participation whose revision is absent from the
        # (empty) catalogue the rebuild will read.
        stale_wu = _work_unit(modelo="303", period="4T", revision_seed="303stale")
        stale_rev = _revision(
            work_unit=stale_wu,
            state=CalculationRevisionState.PRESENTADO,
            txids=(_TX_BORRADOR,),
        )
        participation_repo.save(
            upsert_transaction_participation(
                TransactionRevisionParticipationIndex(transaction_id=_TX_BORRADOR),
                TransactionRevisionParticipation(
                    calculation_revision_id=stale_rev.calculation_revision_id,
                    work_unit_id=stale_wu.work_unit_id,
                    modelo=stale_wu.modelo,
                    filing_year=stale_wu.filing_year,
                    period=stale_wu.period,
                    revision_state=CalculationRevisionState.PRESENTADO.value,
                ),
            ),
        )
        assert participation_repo.exists(_TX_BORRADOR)

        stats = rebuild_participation_index(bucket_id=_BUCKET_ID)

        pruned_exists = participation_repo.exists(_TX_BORRADOR)
        pruned_index = participation_repo.load(_TX_BORRADOR)

    assert stats.stale_removed_count == 1
    assert pruned_exists is False
    assert pruned_index.participations == ()


def test_rebuild_prunes_only_transactions_the_catalogue_dropped(tmp_path: Path) -> None:
    """Pruning is scoped to absent keys: a still-finalized transaction round-trips intact."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        cr_repo = CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_ID)
        wu_repo = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID)
        participation_repo = TransactionParticipationIndexRepository(bucket_id=_BUCKET_ID)

        kept_wu = _work_unit(modelo="130", period="2T", revision_seed="130keep")
        kept_rev = _revision(
            work_unit=kept_wu,
            state=CalculationRevisionState.VERIFICADO_COMPLETO,
            txids=(_TX_VERIFIED,),
        )
        wu_repo.save(upsert_work_unit(wu_repo.load(), kept_wu))
        cr_repo.save(upsert_calculation_revision(cr_repo.load(), kept_rev))

        # A stale object for a transaction no revision references any more.
        participation_repo.save(TransactionRevisionParticipationIndex(transaction_id=_TX_BORRADOR))

        stats = rebuild_participation_index(bucket_id=_BUCKET_ID)

        kept_index = participation_repo.load(_TX_VERIFIED)
        dropped_exists = participation_repo.exists(_TX_BORRADOR)

    assert stats.stale_removed_count == 1
    assert dropped_exists is False

    # The retained transaction survives the replace with its real participation.
    (kept_entry,) = kept_index.participations
    assert kept_entry.calculation_revision_id == kept_rev.calculation_revision_id
    assert kept_entry.work_unit_id == kept_wu.work_unit_id
    assert kept_entry.revision_state == CalculationRevisionState.VERIFICADO_COMPLETO.value
    assert kept_entry.filing_record_id is None
